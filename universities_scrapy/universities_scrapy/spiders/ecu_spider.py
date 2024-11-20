import scrapy
import scrapy.crawler
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait, Select
from universities_scrapy.items import UniversityScrapyItem  
from selenium.common.exceptions import TimeoutException 
import re

class EcuSpiderSpider(scrapy.Spider):
    name = "ecu_spider"
    allowed_domains = ["www.ecu.edu.au", "myfees.ecu.edu.au"]
    start_urls = ["https://www.ecu.edu.au/degrees/undergraduate"]
    
    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(url=url, callback=self.parse)

    
    def parse(self, response):
        driver = response.meta['driver']
        wait = WebDriverWait(driver, 5)
        
        # 等待網頁元素載入
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#coursesYouCanStudyHere")))
        
        # 抓到所有按鈕並全部點擊展開更多資訊
        buttons = driver.find_elements(By.CSS_SELECTOR, ".accordion-title")
        for button in buttons:
            driver.execute_script("arguments[0].click();", button) # 用button.click()會有element not interactable的錯誤
        
        # 給scrapy解析
        page = scrapy.Selector(text=driver.page_source)
        cards = page.css('.info-card')
        
        # 篩選包含 'Bachelor of' 的卡片
        bachelor_cards = []
        for card in cards:
            title = card.css('a h3.heading-xxs::text').get()
            if title and 'Bachelor of' in title:
                bachelor_cards.append(card)
        
        # 提取card裡面的url
        
        not_found_list = []
        print(f'找到{len(bachelor_cards)}個Bachelor課程')
        for bachelor_card in bachelor_cards:
        # for index, bachelor_card in enumerate(bachelor_cards):
        #     if index >= 20:
        #         break
            course_url = bachelor_card.css('a::attr(href)').get()
            
            # 進入課程頁面
            driver.get(course_url)
            
            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#feesScholarshipsInt")))
            except TimeoutException:
                course_name = driver.find_element(By.CSS_SELECTOR, 'h1.heading-l').text
                location_raw = driver.find_element(By.CSS_SELECTOR, '.event-details span:nth-of-type(2)').text
                location = location_raw.replace('Venue:', '').strip().split()[0] + ' ' + location_raw.replace('Venue:', '').strip().split()[1]
                
                print(f'{course_name}\n{course_url}\n找不到學費資訊可能代表該課程不支持國際生\n')

                course = {}
                course['course_name'] = course_name
                course['course_url'] = course_url
                course['location'] = location
                not_found_list.append(course)
                continue  # 如果元素未找到，跳過當前卡片
             
            # 給scrapy解析
            page = scrapy.Selector(text=driver.page_source)
            
            # 取得課程名稱
            course_raw = page.css('h1.heading-l::text').get().strip()
            course = course_raw.replace('Bachelor of ', '')
            
            # 取得學費
            tuition_fee_raw = page.css('#feesScholarshipsInt ul li strong::text').get()
            tuition_fee = re.search(r'\d+(?:,\d+)*', tuition_fee_raw).group(0).replace(',', '')
            
            # 英文門檻
            requirement_list = page.css('ul.policy-bands.english li')
            for requirement in requirement_list:
                if 'IELTS' in requirement.css('::text').get():
                    ielts_raw = requirement.css('::text').get()
                    ielts_match = re.search(r'(IELTS Academic).*?(\d+\.\d+)', ielts_raw)
                    if ielts_match:
                        ielts_type = ielts_match.group(1)
                        ielts_score = ielts_match.group(2)
            english_requirement = f'{ielts_type}: {ielts_score}'          

            
            # 取得校區
            location_list = []
            location_infos = page.css('.info-table.info-table-availability tbody tr')
            for location_info in location_infos:
                location_name = location_info.css('th::text').get().strip()
                
                # 檢查 semester1 和 semester2 是否包含其他元素
                if location_info.css('td:nth-of-type(1) span *').get() or location_info.css('td:nth-of-type(2) span *').get():
                    if location_name not in location_list:
                        location_list.append(location_name)
            
            # 列表轉字串
            location = ', '.join(location_list)    
            
            # 把資料存入 university Item
            university = UniversityScrapyItem()
            university['name'] = 'Edith Cowan University'
            university['ch_name'] = '伊迪斯科文大學'
            university['course'] = course
            university['tuition_fee'] = tuition_fee
            university['location'] = location
            university['english_requirement'] = english_requirement
            university['course_url'] = course_url

            yield university
            
        print(f'找不到資訊的url共{len(not_found_list)}個: {not_found_list}') 
        
        # if not_found_list:
        #     # 找不到的另外再去學費計算器裡找  
        #     driver.get('https://myfees.ecu.edu.au/fees/start')
        #     wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".panel.panel-primary")))
            
        #     # 填寫欄位
        #     citizenship_element = driver.find_element(By.CSS_SELECTOR, "#residency")
        #     citizenship_select = Select(citizenship_element)
        #     citizenship_select.select_by_value("IOFF")
        #     option_element = driver.find_element(By.CSS_SELECTOR, "option[value='IOFF']")
        #     option_element.click()
            
        #     wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#studyLevel option[value='UNDERGRAD']")))
        #     study_level_element = driver.find_element(By.CSS_SELECTOR, "#studyLevel")
        #     study_level_select = Select(study_level_element)
        #     study_level_select.select_by_value("UNDERGRAD")
            
        #     next_button = driver.find_element(By.CSS_SELECTOR, ".btn.btn-primary.pull-right")
            
        #     # 送出到下一頁
        #     next_button.click()
        #     wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#curriculum")))
            
        #     # 搜尋關鍵字
        #     search_intput = driver.find_element(By.CSS_SELECTOR, "#curriculum")
        #     search_btn = driver.find_element(By.CSS_SELECTOR, "#search")
        #     search_intput.send_keys('Bachelor of')
        #     search_btn.click()
        #     wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td.no-border")))
            
        #     # 給scrapy解析
        #     page = scrapy.Selector(text=driver.page_source)
        #     rows = page.css('.table.table-bordered.table-striped.table-hover tbody tr')
        #     for row in rows:
        #         course_name_raw = row.css('td:nth-of-type(1)::text').get()
        #         course_name = re.search(r'Bachelor of (.+)', course_name_raw).group(0)
        #         yield SeleniumRequest(url=course_url, callback=self.parse_calculate_fee, meta={'course_name': course_name})
        #         for course in not_found_list:
        #             if course_name == course['course_name']:
        #                 relative_course_url = row.css('td:nth-of-type(2) a::attr(href)').get()
        #                 course_url = 'https://myfees.ecu.edu.au' + relative_course_url
        #                 course['course_url'] = course_url
        #                 yield SeleniumRequest(url=course_url, callback=self.parse_calculate_fee, meta=course)
                    
    def parse_calculate_fee(self, response):
        # 取得學費
        tuition_fee_raw = response.css('#firstYearFee').get()
        tuition_fee = re.search(r'\d+(?:,\d+)*', tuition_fee_raw).group(0).replace(',', '')
        
        course_raw = response.meta["course_name"]
        course = course_raw.replace('Bachelor of ', '')
        location = response.meta['location']
        
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university['name'] = 'Edith Cowan University'
        university['ch_name'] = '伊迪斯科文大學'
        university['course'] = course
        university['tuition_fee'] = tuition_fee
        university['location'] = location
        university['english_requirement'] = 'IELTS Academic: 6.0'
        university['english_requirement_url'] = 'https://www.ecu.edu.au/future-students/course-entry/english-competency?context=international-applicant'

        yield university
        
                       
    def closed(self, reason):
        print(f'Edith Cowan University 爬蟲完成!')
        
       
            
        
            