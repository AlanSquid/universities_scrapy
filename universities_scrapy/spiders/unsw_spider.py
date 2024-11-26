import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem
import time
import re
import json

class UnswSpiderSpider(scrapy.Spider):
    name = "unsw_spider"
    allowed_domains = ["www.unsw.edu.au"]
    start_urls = ["https://www.unsw.edu.au/study/find-a-degree-or-course/degree-search-results?international=true&undergraduate=true&postgraduate=false&delivery-mode-campus=false&delivery-mode-online=false&study-mode-full-time=false&study-part-time=false&double=false&single=true&commonwealth=false&sort=title"]
    full_link_list=[]

    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(
                url=url,
                callback=self.parse,
                wait_time=8
            )
    
    def parse(self, response):
        driver = response.meta['driver']
        wait = WebDriverWait(driver, 8)

        while True:
            try:
                time.sleep(0.5)

                courses = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".cmp-degree-search__results__list__card"))
                )
                self.courses_url(courses)

                # 檢查是否有下一頁
                next_button = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'button[aria-label="Goto Next Page"]'))
                )
                if "enabled" in next_button.get_attribute("class") and next_button.get_attribute("aria-disabled") != "true":
                    driver.execute_script("arguments[0].click();", next_button)
                    wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                else:
                    print(f'共有 {len(self.full_link_list)} 筆資料')
                    for link in self.full_link_list:
                        yield SeleniumRequest(url=link, callback=self.page_parse, meta={'link': link})
                    break
                
            except Exception as e:
                print(f"發生錯誤: {str(e)}")
                break
 

    def page_parse(self, response):
   
        course_name = response.css('h1.cmp-degree-detail-hero__title::text').get()
        
        # 取得學費
        tuition_fee = response.css('div.js-cmp-degree-detail-hero-fee-international::text').get()
        fees_section = response.css('div.cmp-degree-detail-hero__col-left__details__col2__list__item')
        tuition_fee = fees_section.css('dt:has(div.cmp-contentfragment__element--internationalAnnual) + dd::text').get()
        if tuition_fee:
            tuition_fee = tuition_fee.replace('$', '').replace(',', '').replace('*', '').strip()
            tuition_fee = int(tuition_fee)

        # 取得區間
        duration = response.css('dt:contains("Duration") + dd::text').get().strip()

        # 取得校區
        location = response.css('dt:contains("Campus") + dd div::text').get()
        if location == " -":
            location = None
        
        # 取得英文門檻
        # 提取 <script> 標籤的內容
        script_content = response.css('script:contains("window.engRequirementsConfig")::text').get()
        # 提取 JSON 字串部分
        json_start = script_content.find('{')
        json_end = script_content.rfind('}') + 1
        raw_json_data = script_content[json_start:json_end]
        # 將轉義的字符轉為正常的 JSON 格式
        valid_json_data = raw_json_data.encode('utf-8').decode('unicode_escape')
        eng_requirements = json.loads(valid_json_data)
        ielts_requirement = eng_requirements.get('ielts')
        ielts_requirement = ielts_requirement.strip()
        match = re.match(r"(\d+\.\d|\d) overall \(min\.? (.+)\)", ielts_requirement)
        if match:
            overall_score = match.group(1)  # 總分
            subtest_requirements = match.group(2)  # 單科要求描述

            # 處理「所有項目分數一致」的情況
            all_subtests_match = re.match(r"(\d+\.\d|\d) in (listening, reading, writing, and speaking|each subtest)", subtest_requirements)
            if all_subtests_match:
                min_score = all_subtests_match.group(1)
                english_requirement = f"IELTS {overall_score} (單科不低於 {min_score})"
            else:
                reading_writing_match = re.search(r"(\d+\.\d|\d) in writing & reading", subtest_requirements)
                speaking_listening_match = re.search(r"(\d+\.\d|\d) in speaking & listening", subtest_requirements)

                if reading_writing_match and speaking_listening_match:
                    reading_writing_min = reading_writing_match.group(1)
                    speaking_listening_min = speaking_listening_match.group(1)
                    english_requirement = f"IELTS {overall_score} (閱讀和寫作單項不低於 {reading_writing_min}，聽力和口語不低於 {speaking_listening_min})"
                else:
                    english_requirement = f"IELTS {overall_score} (詳細要求: {subtest_requirements})"
        else:
            print(f"{course_name}的英文格式不匹配，無法解析。{ielts_requirement}")
            english_requirement = None
        
        university = UniversityScrapyItem()
        university['name'] = 'University of New South Wales'
        university['ch_name'] = '新南威爾斯大學'
        university['course_name'] = course_name
        university['tuition_fee'] = tuition_fee
        university['english_requirement'] = english_requirement
        university['location'] = location
        university['duration'] = duration
        university['course_url'] = response.url
        # university['english_requirement_url'] = 'https://www.unsw.edu.au/study/how-to-apply/english-language-requirements'
        yield university
    
    def courses_url(self, courses):
        for course in courses:
            course_url = course.find_element(By.CSS_SELECTOR, "h2.cmp-degree-search__results__list__card__content_header a").get_attribute("href")
            self.full_link_list.append(course_url)

    def closed(self, reason):
        print('University of New South Wales 爬蟲完成!')