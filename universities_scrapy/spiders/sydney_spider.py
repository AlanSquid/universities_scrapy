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
                driver.execute_script("arguments[0].click();", next_btn)


                # 等待新頁面加載
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'section.m-content.m-course-card')))

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
            print(f'正在爬取課程: {course['name']}\n{course['url']}\n')
            wait = WebDriverWait(driver, 20)
            try:
                wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-key-information__list')))
                course_page = scrapy.Selector(text=driver.page_source)
                info = course_page.css('.m-key-information__list')
                if not info:
                    print(f'注意!!!\n{course['name']}沒有找到.m-key-information__list元素\n{course['url']}\n')
                    continue
            
            # # 抓取學費
            # fee = info.css('.m-key-information__list__right-fees-info-content-list--price::text').get()
            # print(fee)
            except TimeoutException:
                print(f'{course['name']}頁面加載超時: {course['url']}\n')
                continue
            
    
        
    # 提取課程連結
    def extract_course_urls(self, response):
        cards = response.css("section.m-content.m-course-card")
        for card in cards:
            course_name = card.css('h3.m-title.m-course-card__link-title::text').get()
            course_url = card.css('a.m-link.m-link--default::attr(href)').get()
            self.course_urls.append({'name': course_name, 'url': course_url}) 

        
            
               
    # 爬取課程頁面
    def parse_course_page(self, response):
        yield print(f'正在爬取課程: {response.url}')


