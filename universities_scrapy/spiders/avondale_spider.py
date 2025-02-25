import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re
import time
import cloudscraper
from scrapy.http import HtmlResponse

class AvondaleSpiderSpider(scrapy.Spider):
    name = "avondale_spider"
    allowed_domains = ["www.avondale.edu.au"]
    start_urls = "https://www.avondale.edu.au/courses/"
    fee_detail_url = "https://www.avondale.edu.au/study/fees/"
    except_count = 0
    all_course_url = []
    custom_settings = {
        'HTTPERROR_ALLOWED_CODES': [403] , 
        'RETRY_TIMES' : 3
    }
    scraper = cloudscraper.create_scraper()
    non_international_num = 0
    start_time = time.time()

    def start_requests(self):
        yield scrapy.Request(self.fee_detail_url, callback=self.fee_parse, meta=dict(
            playwright = True,
        ))

    def fee_parse(self, response):
        # 提取所有的價格
        prices = response.xpath('//div[@id="div_block-1219-28362"]//div[contains(text(), "Per Semester - 4 units (24 credit points)")]//following-sibling::div//b/text()').getall()
        # 轉換價格為數字並找出最大和最小值
        prices = [float(price.replace('$', '').replace(',', '')) for price in prices]
        # 提取的資料是一學期所以*2
        self.max_fee = max(prices) *2
        self.min_fee = min(prices) *2

        yield scrapy.Request(self.start_urls, callback=self.parse, meta=dict(
            playwright = True,
        ))

    def parse(self, response):
        response = self.url_transfer_to_scrapy_response(response.url)
        cards = response.css("div#inner_content-125-6 section#section-10-1157 a")
        for card in cards:
            course_name = card.css('div.ct-text-block::text').get()
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA", "Not available"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2 or sum(course_name.count(keyword) for keyword in keywords) < 0:
                # print('跳過:',course_name)
                continue
            url = card.css('::attr(href)').get()
            self.all_course_url.append(url)
            yield scrapy.Request(url, callback=self.page_parse)  # 使用 Scrapy 的請求機制
    
    def page_parse(self, response):
        response = self.url_transfer_to_scrapy_response(response.url)
        not_international  = response.xpath('//span[@id="span-859-28726"]//*[contains(text(), "The course is not available to international students residing in Australia")]/text()').get()
        if not_international:
            self.except_count += 1
            # print("該課程不適用於居住在澳洲的國際學生:",response.url)
            return

        course_name = response.css('h1 span::text').get()
        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2
        location = response.css('span#span-880-28726::text').get()
        duration_info = response.css('span#span-885-28726::text').get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?"
            match = re.search(pattern, duration_info)
            if match:
                duration = float(match.group(1))  
            else :
                duration = None  
        else:
            duration_info = None

        eng_req_info = response.xpath('//span[@id="span-859-28726"]//*[contains(text(), "IELTS")]/text()').get()
        if not eng_req_info:
            # 先取出包含IELTS的完整段落
            ielts = response.xpath('normalize-space(//p[contains(., "IELTS")])').get()
            ielts_info = re.search(r'achieving an overall IELTS score.*?, or', ielts)
            if ielts_info:
                eng_req_info = ielts_info.group()

        if eng_req_info:
            eng_req_info = ''.join(eng_req_info).strip().rstrip(',').rstrip(', or')
            match = re.search(r'IELTS score of.*?(\d+(?:\.\d+)?)', eng_req_info)
            if match:
                eng_req = match.group(1)
        else:
            eng_req = None
            eng_req_info = None

        university = UniversityScrapyItem()
        university['university_name'] = "Avondale University"
        university['name'] = course_name
        university['min_fee'] =self.min_fee
        university['max_fee'] =self.max_fee
        university['campus'] = location
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        university['fee_detail_url'] = self.fee_detail_url

        yield university
    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n亞芳代爾大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')

    def url_transfer_to_scrapy_response(self, url):
        response = self.scraper.get(url) # response 會包含網站的 HTML 內容，以及其他有關這次請求的元數據（如狀態碼、請求頭等）。
        scrapy_response = HtmlResponse(
            url=url, 
            body=response.text, 
            encoding="utf-8", 
        )
        return scrapy_response