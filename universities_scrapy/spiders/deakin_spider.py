import re
import time
import scrapy
from universities_scrapy.items import UniversityScrapyItem

class DeakinSpiderSpider(scrapy.Spider):
    name = "deakin_spider"
    allowed_domains = ["www.deakin.edu.au"]
    start_urls = ["https://www.deakin.edu.au/international-students/choosing-your-degree"]
    all_course_url = []
    start_time = time.time()
    
    def parse(self, response):
        area_cards = response.css("div.card--notched.study-area-card")
        for card in area_cards:
            area_url = card.css('h3 a::attr(href)').get()
            yield response.follow(area_url, self.parse_areas)

    def parse_areas(self, response):
        course_cards = response.xpath(
            '//h3[contains(text(), "Undergraduate") or contains(text(), "Postgraduate")]/following-sibling::div[contains(@class, "module__filter--items--container")]//div[contains(@class, "module__filter--item") and contains(@class, "related-item__tile-outer")]'
        )
        for card in course_cards:
            course_name = card.css('span.course-tile::text').get().strip()
            course_url = card.css('a.related-item__body::attr(href)').get().strip()
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma","Juris Doctor"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue
            if "-international" not in course_url:
                course_url = course_url + "-international"
            if course_url not in self.all_course_url:
                self.all_course_url.append(course_url)
            yield response.follow( course_url, callback=self.parse_courses)
    
    def parse_courses(self, response):
        
        # 取得課程名稱
        course_name = response.css('div.module__banner-title h1::text').get()
        
        # 取得degree_level_id
        degree_level_id = None
        degree_level =response.css('div.module__banner-title strong::text').get()
        if "undergraduate " in degree_level.lower():
            degree_level_id = 1
        elif "postgraduate " in degree_level.lower(): 
            degree_level_id = 2        
        
        # 費用
        fee_info = response.css('div.module__key-information--item-content--full-width::text').get().strip()
        match = re.search(r'\$([\d,]+)', fee_info)
        if match:
            tuition_fee = match.group(1).replace(",", "")  # 去掉逗號
        else:
            tuition_fee = None
        
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
        location_div = response.xpath(
            '//div[(contains(@class, "module__summary--item") or contains(@class, "module__content-panel--wrapper")) '
            'and .//h3[contains(@class, "course__subheading") and contains(text(), "Locations")]]'
        )
        location = None
        if location_div:
            location_list_1 = location_div.xpath('.//div[contains(@class, "module__content-panel--text--full-width")]//ul/li/a/text()').getall()
            location_list_2 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//ul/li/a/text()').getall()
            location_list_3 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//ul/li/text()').getall()
            location_list_4 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//p/a/text()').getall()
            location_list_5 = location_div.xpath('.//div[contains(@class, "module__summary--content")]//a/text()').getall()
            location_list_6 = location_div.xpath('.//div[contains(@class, "module__content-panel--text--full-width")]//a/text()').getall()
            location_list_7 = location_div.xpath('.//div[contains(@class, "module__content-panel--text--full-width")]//p/text()').getall()
            
            at_locations = []
            for text in location_list_7:
                if 'at ' in text:
                    # 分割文字，取 "at" 後面的部分
                    location_after_at = text.split('at ')[-1].strip()
                    # 移除結尾的句號，但保留括號內的內容
                    if location_after_at.endswith('.'):
                        location_after_at = location_after_at[:-1]
                    if location_after_at:
                        at_locations.append(location_after_at)
            # 合併所有來源的位置信息
            location_list = list(set(
                location_list_1 + 
                location_list_2 + 
                location_list_3 + 
                location_list_4 + 
                location_list_5 + 
                location_list_6 + 
                at_locations
            ))
            
            # 清理並組合位置信息
            locations = [loc.strip() for loc in location_list if loc.strip()]
            if locations:
                location = ', '.join(locations)
        
        # 學期duration
        duration_paths = [
            # Pattern 1: Looking for text in p tag within Duration section
            ('//div[contains(@class, "module__summary--item")]'
            '[.//h3[contains(text(), "Duration")]]'
            '//div[contains(@class, "module__summary--content")]//p/text()'),
            
            # Pattern 2: Looking for direct text content within Duration section
            ('//div[contains(@class, "module__summary--item")]'
            '[.//h3[contains(text(), "Duration")]]'
            '//div[contains(@class, "module__summary--content")]/text()'),
            
            # Pattern 3: Looking in full-width panel specifically for Duration section
            ('//div[contains(@class, "module__content-panel--wrapper")]'
            '[.//h3[contains(text(), "Duration")]]'
            '//div[contains(@class, "module__content-panel--text--full-width")]//p/text()')
        ]

        duration_info = None
        
        for path in duration_paths:
            content = response.xpath(path).getall()
            if content:
                duration_info = ' '.join([text.strip() for text in content if text.strip()])
                if duration_info:
                    break

        if duration_info:
            duration_info = duration_info.replace("See entry requirements below for more information.", "").strip()
            numbers = []            
            or_pattern = re.findall(r'(\d+(?:\.\d+)?)\s*(?:or|to)\s*(\d+(?:\.\d+)?)', duration_info.lower())
            if or_pattern:
                numbers.extend([float(num) for tuple_pair in or_pattern for num in tuple_pair])
            
            hyphen_numbers = re.findall(r'(\d+(?:\.\d+)?)-\s*years?', duration_info.lower())
            if hyphen_numbers:
                numbers.extend([float(num) for num in hyphen_numbers])
            
            standard_numbers = re.findall(r'(\d+(?:\.\d+)?)\s*years?', duration_info.lower())
            if standard_numbers:
                numbers.extend([float(num) for num in standard_numbers])
            
            if numbers:
                duration = min(numbers)
            else:
                duration = None
        else:
            duration = None
        

        university = UniversityScrapyItem()
        university['university_name'] = "Deakin University"
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee  
        university['eng_req'] = english_requirement
        university['eng_req_info'] = f'IELTS {english_requirement}'
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id        
        university['course_url'] = response.url
        yield university
       

    def close(self):
        print(f"迪肯大學({self.name})總共{len(self.all_course_url)}個科系\n")
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'爬蟲時間: {elapsed_time:.2f}', '秒')