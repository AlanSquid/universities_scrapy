import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class CduSpider(scrapy.Spider):
    name = "cdu_spider"
    allowed_domains = ["www.cdu.edu.au"]
    start_urls = ["https://www.cdu.edu.au/course-search?refine=&student_type=International&year=2025&field_course_level%5B215%5D=215&field_course_level%5B216%5D=216&page=0"]
    all_course_url = []
    except_count = 0
    def parse(self, response):
        cards = response.css("div.fable__body.js-shortlist div.fable__row")
        for card in cards:
            course_name = card.css("div.course-list__course-name a::text").get()
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue
            url = card.css('div.course-list__course-name a::attr(href)').get()
            course_url = response.urljoin(url) 
            self.all_course_url.append(course_url)
            yield response.follow(course_url, self.page_parse) 
        next_page_button = response.css('nav[aria-label="Pagination"] ul li.pagination__next a::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            yield response.follow(next_page_url, self.parse) 

    def page_parse(self, response): 
        course_name = response.css("h1#course-title::text").get()   
        course_name = course_name.strip() if course_name else None
        
        course_level = response.css("div#course-level::text").get()    
        course_level = course_level.strip() if course_level else None
        degree_level_id = None
        if "undergraduate" in course_level.lower():
            degree_level_id = 1
        elif "postgraduate" in course_level.lower(): 
            degree_level_id = 2
        
        # Duration
        duration_info = response.css("div.block-course-key-fact-duration div[data-student-type='international'] div::text").get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year/s\s+full-time"
            match = re.search(pattern, duration_info)
            if match:
                duration = float(match.group(1))  # 提取匹配內容並轉換為 float
            else:
                duration = None  # 如果沒有匹配到數字
        else:
            duration_info = None
 
        # Duration
        location = response.css("div.block-course-key-fact-location div[data-student-type='international']::text").get()

        requirements  = response.css('div#entry-requirements details div.accordion__content.rich-text.rich-text--contained div[data-student-type="international"].spaced-top table')
        ielts_info = requirements.xpath(".//td[contains(text(), 'IELTS')]/parent::tr/td/text()").getall()
        eng_req_info = " ".join(ielts_info)
        if eng_req_info and eng_req_info !=  "":
            match = re.search(r'overall score of (\d+(\.\d+)?)', eng_req_info)
            if match:
                eng_req = float(match.group(1))
            else:
                eng_req = None
        else:
            eng_req = None
            eng_req_info = None


        fee = None
        tuition_section = response.css('div#overview details.accordion.accordion--divided div.accordion__content.rich-text.rich-text--contained div[data-student-type="international"]')
        if tuition_section.css('h4::text').get() == "International tuition fees":
            tuition_text = tuition_section.css('p::text').get()
            match = re.search(r'AUD\s*\$([\d,]+(?:\.\d{2})?)', tuition_text)
            if match:
                annual_fee = match.group(1)
                fee = float(annual_fee.replace(',', ''))

        university = UniversityScrapyItem()
        university['university_id'] = 15
        university['name'] = course_name
        university['min_fee'] = fee
        university['max_fee'] = fee
        university['campus'] = location
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n查爾斯達爾文大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')
