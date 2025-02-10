import re
import scrapy
from scrapy import Selector
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from universities_scrapy.items import UniversityScrapyItem

class RmitSpiderSpider(scrapy.Spider):
    name = "rmit_spider"
    allowed_domains = ["www.rmit.edu.au"]
    # start_urls = ["https://www.rmit.edu.au/study-with-us/international-students/programs-for-international-students/courses-for-international-students-by-study-area?activeTab=All"]
    start_urls = ["https://www.rmit.edu.au/content/rmit/au/en/study-with-us/international-students/programs-for-international-students/courses-for-international-students-by-study-area/jcr:content/body-gridcontent/tabs/all/rmitprogramlist_copy.model.json?t=1739160669494&data=yes&facetFilter=rmit:study_type/undergraduate_degree","https://www.rmit.edu.au/content/rmit/au/en/study-with-us/international-students/programs-for-international-students/courses-for-international-students-by-study-area/jcr:content/body-gridcontent/tabs/all/rmitprogramlist_copy.model.json?t=1739161591376&data=yes&facetFilter=rmit:study_type/postgraduate_study"]
    all_course_url = []
    
    def parse(self, response):
        data = response.json()  
        for item in data['programs']['programs']:
            course_url = item['programUrl']
            course_name = item['programName']
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            keywords = ["bachelor-degrees", "masters-by-coursework" ,"Bachelor of" , "Master of", "major"]
            if not course_url  or sum(course_name.count(keyword) for keyword in keywords) >= 2 or sum(course_url.count(keyword) for keyword in keywords) < 1:
                # print('跳過:',course_name)
                continue
            self.all_course_url.append(course_url)

            yield response.follow(course_url, self.page_parse)
   
    def page_parse(self, response):
        course_name = response.css("div.header-gridcontent h1::text").get()
        # 去除前後空白字符
        if course_name:
            course_name = course_name.strip()
            
        if "bachelor" in response.url:
            degree_level_id = 1
        elif "master" in response.url: 
            degree_level_id = 2

        # 費用
        fee_info = response.css('div.quickfacts div.b-international dd.qf-int-fee p::text').get()
        tuition_fee = None
        if fee_info and "AU$" in fee_info:
            fee = fee_info.strip()
            # 使用正則表達式匹配 "AU$" 後的數字
            pattern = r"AU\$\s*(\d[\d,]*)"  # 匹配 AU$ 後的數字，允許逗號
            match = re.search(pattern, fee)
            if match:
                tuition_fee = match.group(1).replace(",", "")  # 去掉逗號
        
        # 英文門檻
        eng_req = eng_req_info = None
        eng_req_li = response.css('div.intl-par.responsivegrid.international div#english-language-requirments-experiencefragment li::text').getall()
        for li_text in eng_req_li:
            if 'IELTS' in li_text:
                eng_req_info = li_text
                pattern = r"IELTS\s*\((.*?)\)\s*[:：]\s*.*?(\d+(\.\d+)?)"
                match = re.search(pattern, li_text)
                if match:
                    eng_req = match.group(2)  # 提取數字部分

        # 校區
        locations = response.xpath('//dt[text()=" Location:"]/following-sibling::dd[@class="desc qf-int-location"]/text()').getall()
        locations = [all_location.strip() for all_location in locations]
        location = ', '.join(locations)

        # 學制(期間)
        durations = response.xpath('//dt[text()=" Duration:"]/following-sibling::dd[@class="desc qf-int-duration"]/text()').getall()
        durations = [all_duration.strip() for all_duration in durations]
        duration_info = ', '.join(durations)
        pattern = r"(\d+(\.\d+)?)"
        match = re.search(pattern, duration_info)
        if match:
            first_number = match.group(1)
            duration=first_number
        else:
            duration=None

        university = UniversityScrapyItem()
        university['university_id'] = 32
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee            
        university['eng_req'] = eng_req       
        university['eng_req_info'] = eng_req_info
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id        
        university['course_url'] = response.url
        yield university
   
    def close(self):
        print(f"墨爾本皇家理工大學({self.name})總共{len(self.all_course_url)}個科系")
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'爬蟲時間: {elapsed_time:.2f}', '秒')