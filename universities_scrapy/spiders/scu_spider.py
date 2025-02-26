import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class ScuSpiderSpider(scrapy.Spider):
    name = "scu_spider"
    allowed_domains = ["site-search.scu.edu.au", "www.scu.edu.au"]
    start_urls = ["https://site-search.scu.edu.au/s/search.html?f.Tabs%7Cscu%7Edep-courses=Courses&collection=scu%7Escu-dep&f.Study+level%7Cstudylevel=Undergraduate&f.Study+level%7Cstudylevel=Postgraduate"]
    # start_urls = ["https://site-search.scu.edu.au/s/search.html?f.Tabs%7Cscu%7Edep-courses=Courses&collection=scu%7Escu-dep"]
    all_course_url = []
    except_count = 0
    custom_settings = {
        'HTTPERROR_ALLOWED_CODES': [204,404,403 ,304,302,500,400] , 
        'RETRY_TIMES' : 3
    }
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta=dict(
                playwright = True,
            ))
            
    def parse(self, response):
        cards = response.css("div.search-content__block div.search-content__block-item")
        for card in cards:
            course_name = card.css("h3.course-card__title a::text").get()
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2 or sum(course_name.count(keyword) for keyword in keywords) < 0:
                # print('跳過:',course_name)
                continue
            self.all_course_url.append(course_name)
            # course_name = course_name.replace('\n', '').replace('  ', '').strip() if course_name else None
            # course_name = re.sub(r"- \(.*?\) - \d{4}", "", course_name).strip()
            course_url = card.attrib.get('data-fb-result')
            yield scrapy.Request(course_url, callback=self.page_parse)
        next_button = response.css("ul.pagination li.next a::attr(href)").get()
        if next_button:
            next_page_url = response.urljoin(next_button)
            yield scrapy.Request(next_page_url, callback=self.parse, meta=dict(
                playwright = True,
            ))

    def page_parse(self, response): 
        # 檢查有沒國際生
        location_div = response.xpath('//div[./select[@id="course-location"]]')
        if location_div.xpath('@style').get() == 'display:none':
            # print("不開放國際生，", response.url)
            self.except_count += 1
            return

        course_name = response.css("div.course-masthead__text h1.course-masthead__title::text").get()
        course_name = course_name.strip() if course_name else None

        int_course_info = response.css("section.course-snapshot div.js-course-selector-content[data-course='international']")
        duration_info = int_course_info.xpath("//li[@class='course-snapshot__item'][.//h4[contains(text(), 'Duration')]]//div[@class='course-snapshot__text']/p/text()").get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full-time"
            match = re.search(pattern, duration_info)
            if match:
                duration = float(match.group(1))  
            else:
                duration = None 
        else:
            duration_info = None

        campus = int_course_info.xpath("//li[@class='course-snapshot__item'][.//h4[contains(text(), 'Location')]]//div[@class='course-snapshot__text']/p/text()").get()
        campus = campus.strip()  if campus else None
        if campus and campus.lower() == "online":
            self.except_count += 1
            return

        course_section = response.xpath("//span[@id='course-requirements']/following-sibling::section[@class='course-content panel-m']")
        scores = course_section.xpath(".//h4[text()='Language requirements']/following-sibling::table[@class='table']/tbody//tr")
        eng_req_info = None
        eng_req = None
        eng_req_info = ", ".join([
            f"{(row.xpath('./td[1]/text()').get() or '').strip()} {(row.xpath('./td[2]/text()').get() or '').strip()}"
            for row in scores
        ])
        if eng_req_info:
            match = re.search(r'Overall.*?(\d+(?:\.\d+)?)', eng_req_info)
            if match:
                eng_req = match.group(1)

        fee = response.css("div#overview-collapseAvailability div.js-course-selector-content[data-course='international']")
        fee_texts = fee.xpath('.//table//td[contains(text(), "$")]/text()').getall()
        fees = []
        for fee_text in fee_texts:
            match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', fee_text)
            if match:
                fee_amount = float(match.group(1).replace(',', ''))
                fees.append(fee_amount)
        min_fee = min(fees) if fees else None
        max_fee = max(fees) if fees else None

        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2

        university = UniversityScrapyItem()
        university['university_name'] = "Southern Cross University"
        university['name'] = course_name
        university['min_fee'] = min_fee
        university['max_fee'] = max_fee
        university['campus'] = campus
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n南十字星大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)\n')
