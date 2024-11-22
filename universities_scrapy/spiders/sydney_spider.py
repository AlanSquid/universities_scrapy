import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem
from selenium.common.exceptions import NoSuchElementException
import re

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
        
    
        
    # 提取課程連結
    def extract_course_urls(self, response):
        cards = response.css("section.m-content.m-course-card")
        for card in cards:
            course_url = card.css('a.m-link.m-link--default::attr(href)').get()
            self.course_urls.append(course_url)

    # 爬取課程頁面
    def parse_course_page(self, response):
        print(f'正在爬取課程: {response.url}')


