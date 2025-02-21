import scrapy
import re
from universities_scrapy.items import UniversityScrapyItem 

class DivinitySpiderSpider(scrapy.Spider):
    name = "divinity_spider"
    allowed_domains = ["www.divinity.edu.au", 'divinity.edu.au']
    start_urls = ["https://divinity.edu.au/courses/?_sfm_aqf_level=09","https://divinity.edu.au/courses/?_sfm_aqf_level=07"]
    all_course_url = []
    eng_req_url = "https://divinity.edu.au/study/apply/"
    eng_req_info = "IELTS Academic 6.5 with no band below 6.0"
    eng_req = 6.5

    def parse(self, response):
        cards = response.css("main#genesis-content article")
        for card in cards:
            course_name = card.css("header.entry-header div.card-header::text").get()
            course_url = card.css("li a::attr(href)").get()
            self.all_course_url.append(course_url)
            yield response.follow(course_url, self.page_parse)

    def page_parse(self, response):
        course_name = response.xpath('//h1[@class="entry-title"]//text()').getall()
        course_name = ''.join(course_name).strip() if course_name else None

        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2

        fee_info = response.css("div#qf-fees p::text").get()
        tuition_fee = None
        if fee_info and "AU$" in fee_info:
            fee = fee_info.strip()
            # 使用正則表達式匹配 "AU$" 後的數字
            pattern = r"AU\$\s*(\d[\d,]*)"  # 匹配 AU$ 後的數字，允許逗號
            match = re.search(pattern, fee)
            if match:
                tuition_fee = match.group(1).replace(",", "")  # 去掉逗號
        duration = None
        duration_info = None
        duration_info = response.css("div#qf-duration p::text").get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full-time"
            match = re.search(pattern, duration_info)            
            if match:
                duration = float(match.group(1))  

        location_info = response.css("div#overseas-colleges li div.card-header a::text").getall()
        location = ', '.join(location_info).strip() if location_info else None
        
        university = UniversityScrapyItem()
        university['university_id'] = 38
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['campus'] = location
        university['eng_req'] = self.eng_req
        university['eng_req_info'] = self.eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        university['eng_req_url'] = self.eng_req_url

        yield university
    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n神學大學，共 {len(self.all_course_url)} 筆資料')
