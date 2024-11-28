import re
import time
import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from universities_scrapy.items import UniversityScrapyItem


class DeakinSpiderSpider(scrapy.Spider):
    name = "deakin_spider"
    allowed_domains = ["www.deakin.edu.au"]
    start_urls = ["https://www.deakin.edu.au/international-students/choosing-your-degree"]
    all_course_url = []
    start_time = time.time()
    
    def start_requests(self):
        # 用 response.follow 發送起始請求
        url = self.start_urls[0]
        yield scrapy.Request(url, callback=self.parse_all)
        
    def parse_all(self, response):
        area_cards = response.css("div.card--notched.study-area-card")
        for card in area_cards:
            # area_name = card.css('h3 a::text').get().strip()
            area_url = card.css('h3 a::attr(href)').get()
            yield SeleniumRequest(
                url=area_url,
                callback=self.parse_areas,
                wait_time=10,
                wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, "div.module__tabs--content")),
            )
            
    def parse_areas(self, response):
        course_cards = response.css('h3:contains("Undergraduate") + div.module__tabs--content div.module__filter--item.related-item__tile-outer.undergrad.animate')
        for card in course_cards:
            course_name = card.css('span.course-tile::text').get().strip()
            course_url = card.css('a.related-item__body::attr(href)').get().strip()
            if "-international" not in course_url:
                course_url = course_url + "-international"
            if course_url not in self.all_course_url:
                self.all_course_url.append(course_url)
            yield response.follow(
                course_url, 
                callback=self.parse_courses, 
                meta={'course_name': course_name},
            )
    
    def parse_courses(self, response):
        course_name = response.meta['course_name']
        url = response.url
        
        # 費用
        fee_info = response.css('div.module__key-information--item-content--full-width::text').get().strip()
        match = re.search(r'\$([\d,]+)', fee_info)
        if match:
            tuition_fee = match.group(1).replace(",", "")  # 去掉逗號
        
        # 英文門檻
        eng_req_info = response.css('li::text').getall()
        
        for content in eng_req_info:
            content = content.strip()  # 去除多餘的空白
            if 'IELTS' in content:
                # 使用正則表達式來匹配 IELTS 分數
                match = re.search(r'IELTS\s+.*?(\d+(\.\d+)?)', content)
                
                if match:
                    english_requirement = match.group(1)  # 提取 IELTS 分數
                
        # 校區
        location_div = response.xpath('//div[contains(@class, "module__summary--item") and ./div/h3[contains(@class, "course__subheading") and contains(text(), "Locations")]]')
        
        if location_div:
            location_list = location_div.xpath('.//div[contains(@class, "module__summary--content")]//ul/li/a/text()').getall()
            location_list_2 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//ul/li/text()').getall()
            location_list_3 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//p/a/text()').getall()
            location_list = location_list + location_list_2 + location_list_3
            online_location = location_div.xpath('.//div[contains(@class, "module__summary--content")]/a[contains(text(), "Online")]/text()').get()
            
            # 合併校區資訊
            locations = [loc.strip() for loc in location_list]
            if online_location:
                locations.append(online_location.strip())
            
            # 格式化輸出
            location = ', '.join(locations)
        
        # 學制(期間)
        try:
            duration_div = response.xpath('//div[contains(@class, "module__summary--item") and contains(@class, "module__summary--item-bullets") and ./div/h3[contains(@class, "course__subheading") and contains(text(), "Duration")]]')
            duration = duration_div.xpath('.//p/text()').get().strip()
        # 可能沒有固定的學制時間
        except:
            duration_div = response.xpath('//div[contains(@class, "module__content-panel--title--full-width")]/h3[text()="Course duration"]/parent::div')
            duration = duration_div.xpath('following-sibling::div[contains(@class, "module__content-panel--text--full-width")]/p/text()').get()
        
        university = UniversityScrapyItem()
        university['name'] = "Deakin University"
        university['ch_name'] = "迪肯大學"
        university['course_name'] = course_name
        university['min_tuition_fee'] = tuition_fee
        university['english_requirement'] = f'IELTS {english_requirement}'
        university['location'] = location
        university['course_url'] = url
        university['duration'] = duration
        yield university
        

    def close(self):
        print(f"迪肯大學({self.name})總共{len(self.all_course_url)}個科系")
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'爬蟲時間: {elapsed_time:.2f}', '秒')