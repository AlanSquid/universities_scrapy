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
    not_found_list = []
    
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
        
        print(f'找到{len(bachelor_cards)}個Bachelor課程')
        
        # 提取card裡面的url
        for bachelor_card in bachelor_cards:
            course_url = bachelor_card.css('a::attr(href)').get()

            # 進入課程頁面
            yield SeleniumRequest(url=course_url, callback=self.parse_course_detail)
            

    def parse_course_detail(self, response):
        if response.css('#feesScholarshipsInt').get():
            # 取得課程名稱
            course_name = response.css('h1.heading-l::text').get().strip()

            
            # 取得學費
            tuition_fee_raw = response.css('#feesScholarshipsInt ul li strong::text').get()
            tuition_fee = re.search(r'\d+(?:,\d+)*', tuition_fee_raw).group(0).replace(',', '')
            
            # 英文門檻
            english_requirement = ''
            
            # 先找內文
            requirement_first_content = response.css('#accordion__englishInt p::text').get()      
            if requirement_first_content and 'IELTS' in requirement_first_content:
                ielts_match = re.search(r'IELTS Academic.*?of (\d+\.\d+)', requirement_first_content)
                if ielts_match:
                    ielts_score = ielts_match.group(1)
                    english_requirement = f'IELTS Academic: {ielts_score}'
            # 再找列表
            else:
                requirement_list = response.css('#accordion__englishInt ul li')
                for requirement in requirement_list:
                    row_text = requirement.css('::text').get()
                    if 'IELTS' in row_text:
                        ielts_raw = row_text
                        ielts_match = re.search(r'(IELTS Academic).*?(\d+\.\d+)', ielts_raw)
                        if ielts_match:
                            ielts_type = ielts_match.group(1)
                            ielts_score = ielts_match.group(2)
                            english_requirement = f'{ielts_type}: {ielts_score}'     

            
            # 取得校區
            location_list = []
            location_infos = response.css('.info-table.info-table-availability tbody tr')
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
            university['course_name'] = course_name
            university['tuition_fee'] = tuition_fee
            university['location'] = location
            university['english_requirement'] = english_requirement
            university['course_url'] = response.url

            yield university
            
        else:
            course_name = response.css('h1.heading-l::text').get().strip()
            location_raw = response.css('.event-details span:nth-of-type(2)::text').get().strip()
            location = location_raw.replace('Venue:', '').strip().split()[0] + ' ' + location_raw.replace('Venue:', '').strip().split()[1]
            
            print(f'{course_name}\n{response.url}\n找不到學費資訊可能代表該課程不支持國際生\n')

            course = {}
            course['course_name'] = course_name
            course['course_url'] = response.url
            course['location'] = location
            self.not_found_list.append(course)
            

        
                       
    def closed(self, reason):
        print(f'Edith Cowan University 爬蟲完成!')
        print(f'找不到資訊的url共{len(self.not_found_list)}個')
        
       
            
        
            