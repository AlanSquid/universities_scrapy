import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem
from selenium.common.exceptions import TimeoutException 
from selenium.common.exceptions import NoSuchElementException
import re
import time

class SydneySpiderSpider(scrapy.Spider):
    name = "sydney_spider"
    allowed_domains = ["www.sydney.edu.au"]
    start_urls = ["https://www.sydney.edu.au/courses/search.html?search-type=course&page=1&keywords=bachelor&level=uc&coursecitizenship=INT&years=2025&sort=relevance"]
    course_urls = []
    
    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(url=url, callback=self.parse)
    
    def parse(self, response):
        driver = response.request.meta['driver']
        # 提取課程連結
        self.extract_course_urls(response)
        
        # 換頁
        pagination = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="pagination"]')
        next_btn = pagination.find_element(By.CSS_SELECTOR, 'button[data-testid="pagination-next-button"]')
        
        while True:
            try:
                # 換頁
                pagination = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="pagination"]')
                next_btn = pagination.find_element(By.CSS_SELECTOR, 'button[data-testid="pagination-next-button"]')
                
                link = driver.find_element(By.CSS_SELECTOR, 'section.m-content.m-course-card a')
                old_link_href = link.get_attribute("href")
                driver.execute_script("arguments[0].click();", next_btn)

                # 等待a標籤的href屬性改變
                wait = WebDriverWait(driver, 10)
                wait.until(self.href_changes((By.CSS_SELECTOR, 'section.m-content.m-course-card a'), old_link_href))

                # 把更新後的頁面傳給scrapy來解析
                updated_cards = scrapy.Selector(text=driver.page_source)
                
                # 提取課程連結
                self.extract_course_urls(updated_cards)

            # NoSuchElementException: 找不到元素時可以catch異常做處理，而不會報錯
            except NoSuchElementException:
                # 如果沒有下一頁，跳出循環
                break

        print(f'共有{len(self.course_urls)}個課程連結')
        
        # 爬取課程頁面
        for course in self.course_urls:
            driver.get(course['url'])
            print(f'正在爬取課程: {course['name']}\n{course['url']}\n')
            wait = WebDriverWait(driver, 10)
            try: 
                # 等待.m-key-information__list__fees-info元素(資訊欄)加載，如果超時則拋出異常
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-key-information__list__fees-info .m-key-information__list__right-fees-info-content')))
            except TimeoutException:
                # 爬不到資訊欄例外處理
                course_detail = self.except_course_process(driver)

                print(f'課程: {course['name']}')
                print(f'課程url: {course['url']}')
                print(f'學費: {course_detail['tuition_fee']}')
                print(f'英文門檻: {course_detail['english_requirement']}')
                print(f'校區: {course_detail['location']}')
                print(f'學制: {course_detail['duration']}')
                print('\n')
                
                # 把資料存入 university Item
                item = UniversityScrapyItem()
                item['name'] = 'University of Sydney'
                item['ch_name'] = '雪梨大學'
                item['course_name'] = course['name']
                item['course_url'] = course['url']
                item['min_tuition_fee'] = course_detail['tuition_fee']
                item['english_requirement'] = course_detail['english_requirement']
                item['location'] = course_detail['location']
                item['duration'] = course_detail['duration']
        
                yield item
                continue
            
            # 處理modal
            modal = driver.find_element(By.CSS_SELECTOR, '.m-csp-modal-content') if driver.find_elements(By.CSS_SELECTOR, '.m-csp-modal-content') else None
            if modal:
                self.modal_process(driver, wait)
                    
            
            # 丟給scrapy解析
            course_page = scrapy.Selector(text=driver.page_source)
            
            # 抓資訊欄
            info = course_page.css('.m-key-information__list')
            if not info:
                print(f'注意!!!\n{course['name']}沒有找到.m-key-information__list元素\n{course['url']}\n')
                continue
        
            # 抓取學費
            tuition_fee_raw = info.css('.m-key-information__list__fees-info .m-key-information__list__right-fees-info-content-list--price::text').get()
            if tuition_fee_raw is not None:
                tuition_fee = tuition_fee_raw.strip().replace('A$', '').replace(',', '').replace('*', '')
                if tuition_fee == '-':
                    tuition_fee = None
                    
            # 抓校區
            location = info.css('.m-key-information__list__right-location span::text').get()
            
            # 抓學制
            info_other_list = info.css('.m-key-information__list__other-info')
            for info_other in info_other_list:
                title = info_other.css('.m-key-information__list__left h4::text').get()
                if 'Duration' in title:
                    duration = info_other.css('.m-key-information__list__right :nth-child(1) *::text').get()
                    
            # 抓英文門檻
            # 切換Admissions招生頁面
            admissions = driver.find_element(By.CSS_SELECTOR, '.m-nav-tabs__button.m-nav-tabs__button--selected')
            admissions.click()
            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.m-eng-lang-req-list')))

                # 展開選單需點擊'English is NOT my first language'選項
                eng_req_block = driver.find_element(By.CSS_SELECTOR, '.m-eng-lang-req-list')
                
                dropdown_options = eng_req_block.find_elements(By.CSS_SELECTOR, '.m-accordion__slide-btn.m-accordion--ds__slide-btn')
                for dropdown_option in dropdown_options:
                    if 'NOT' in dropdown_option.find_element(By.CSS_SELECTOR, '.m-eng-lang-req__title-text.m-grid__cell').get_attribute('textContent'):
                        driver.execute_script("arguments[0].click();", dropdown_option)
                        break
                    
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-accordion__slide-content.m-accordion--ds__slide-content')))
            except TimeoutException:
                print(f'注意!!!\n{course['name']}頁面加載超時: {course['url']}\n')
            
            # 丟給scrapy解析
            english_requirement = None
            admissions_page = scrapy.Selector(text=driver.page_source)
            
            english_requirements_list = admissions_page.css('.m-rich-content.m-rich-content--ds table tr')
            for english_requirement_item in english_requirements_list:
                title = english_requirement_item.css('td:nth-of-type(1) strong::text').get()
                # 找IELTS的英文門檻
                if title and 'IELTS' in title:
                    english_requirement_raw = english_requirement_item.css('td:nth-child(2)::text').get()
                    # 格式化文字
                    english_requirement = self.extract_ielts_requirement_str(english_requirement_raw)
                    break
                    
            # 輸出資訊
            print(f'課程: {course['name']}')
            print(f'課程url: {course['url']}')
            print(f'學費: {tuition_fee}') 
            print(f'英文門檻: {english_requirement}')
            print(f'校區: {location}')
            print(f'學制: {duration}')
            print(f'\n')
            
            # 把資料存入 university Item
            item = UniversityScrapyItem()
            item['name'] = 'University of Sydney'
            item['ch_name'] = '雪梨大學'
            item['course_name'] = course['name']
            item['course_url'] = course['url']
            item['min_tuition_fee'] = tuition_fee
            item['english_requirement'] = english_requirement
            item['location'] = location
            item['duration'] = duration
            
            yield item             
                      
    
    # 判斷href是否有改變
    class href_changes(object):
        def __init__(self, locator, old_href):
            self.locator = locator
            self.old_href = old_href

        def __call__(self, driver):
            element = driver.find_element(*self.locator)
            new_href = element.get_attribute("href")
            return new_href != self.old_href
        
    # 提取課程連結
    def extract_course_urls(self, response):
        cards = response.css("section.m-content.m-course-card")
        for card in cards:
            course_name = card.css('h3.m-title.m-course-card__link-title::text').get()
            course_url = card.css('a.m-link.m-link--default::attr(href)').get()
            
            # 這個課程連結是否已經在列表中
            is_course_url_in_list = any(course['url'] == course_url for course in self.course_urls)
            
            if is_course_url_in_list:
                continue
            
            self.course_urls.append({'name': course_name, 'url': course_url}) 

    
    # 處理modal
    def modal_process(self, driver, wait):
        # 點擊國際學生按鈕
        international_btn = driver.find_element(By.CSS_SELECTOR, '.m-grid.m-grid--horizontal--mobile-down > :nth-child(2) button')
        international_btn.click()
        
        # 點擊下拉選單
        dropdown_btn = driver.find_element(By.CSS_SELECTOR, '.m-dropdown.m-dropdown--ds')
        dropdown_btn.click()
        
        # 點擊下拉選單項目(2025)
        dropdown_option_btn = driver.find_element(By.CSS_SELECTOR, '.m-dropdown__panel.m-dropdown--ds__panel  > :nth-child(1)')
        dropdown_option_btn.click()
        
        # 點擊Get started按鈕
        get_started_btn = driver.find_element(By.CSS_SELECTOR, '.m-csp-modal__btn-continue-wrapper__button')
        get_started_btn.click()
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-key-information__list__fees-info .m-key-information__list__right-fees-info-content-list')))
            
               
    # 爬取課程頁面
    def parse_course_page(self, response):
        yield print(f'正在爬取課程: {response.url}')
        
    # 提取IELTS英文門檻
    def extract_ielts_requirement_str(self, ielts_string):
        # 使用正則表達式進行替換
        pattern = r"A minimum result of (\d+\.\d+) overall and a minimum result of (\d+\.\d+) in each band"
        match = re.search(pattern, ielts_string)
        
        if match:
            if match.group(2):
                replacement = f"IELTS {match.group(1)} (單科不低於{match.group(2)})"
            else:
                replacement = f"IELTS {match.group(1)}"
        else:
            replacement = ielts_string  # 如果沒有匹配到，返回原始字符串
        
        return replacement
    
    # 爬不到資訊欄例外處理
    def except_course_process(self, driver):
        print('正在處理例外情況...')
        # 選擇身分為國際生
        role_dropdown = driver.find_elements(By.CSS_SELECTOR, '.col-xs-10 .b-dropdown-simple__option-wrapper a')
        for role_option in role_dropdown:
            if 'International' in role_option.get_attribute('textContent'):
                driver.execute_script("arguments[0].click();", role_option)
                break
        
        page = scrapy.Selector(text=driver.page_source)
        
        # 抓取學費
        tuition_fee_raw = page.css('.dual-title.b-text--bold::text').get()
        pattern = r":\s*\$([\d,]+)"
        match = re.search(pattern, tuition_fee_raw)
    
        if match:
            tuition_fee = match.group(1).replace(',', '')
            
        else:
            tuition_fee = None
        
        # 抓取英文門檻
        english_requirement_raw = page.css('.b-paragraph.b-box--slightly-transparent.b-box--compact.b-box--mid-grey.b-component--tighter::text').get()
        english_requirement = self.extract_ielts_requirement_str(english_requirement_raw)
        
        course_details = page.css('.b-box.b-box--bordered-thin-grey.b-details-panel__box::text').getall() 
        location = ''
        duration = ''
        for course_detail in course_details:
            # 抓取校區
            if 'Location' in course_detail:
                location = course_detail.strip().replace('Location: ', '')
                
            # 抓取學制
            if 'Duration full time' in course_detail:
                duration = course_detail.strip().replace('Duration full time: ', '').replace(' for Domestic and International students', '')
            
            if location and duration:
                break
        
        return {'tuition_fee': tuition_fee, 'english_requirement': english_requirement, 'location': location, 'duration': duration}

            
        


