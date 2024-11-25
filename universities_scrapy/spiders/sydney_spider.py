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
        
        for course in self.course_urls:
            # print(f'{course['name']}\n{course['url']}\n')
            driver.get(course['url'])
            print(f'正在爬取課程: {course['name']}\n{course['url']}')
            wait = WebDriverWait(driver, 20)
            try:
                wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                
                try:
                    # 等待.m-key-information__list__fees-info元素加載，如果超時則拋出異常
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-key-information__list__fees-info .m-key-information__list__right-fees-info-content')))
                    
                    modal = driver.find_element(By.CSS_SELECTOR, '.m-csp-modal-content')
                    if modal:
                        print('有modal')
                        # 處理modal
                        self.modal_process(driver, wait)
                        
                except NoSuchElementException:
                    print('沒有modal')
                # 丟給scrapy解析
                course_page = scrapy.Selector(text=driver.page_source)
                    
                info = course_page.css('.m-key-information__list')
                if not info:
                    print(f'注意!!!\n{course['name']}沒有找到.m-key-information__list元素\n{course['url']}\n')
                    continue
            
                # 抓取學費
                tuition_fee_raw = info.css('.m-key-information__list__fees-info .m-key-information__list__right-fees-info-content-list--price::text').get()
                if tuition_fee_raw is not None:
                    tuition_fee = tuition_fee_raw.strip().replace('A$', '').replace(',', '').replace('*', '')
                    print(f'{tuition_fee}\n')
                
            except TimeoutException:
                print(f'注意!!!\n{course['name']}頁面加載超時: {course['url']}\n')
                continue

            
    
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
        


