import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait  # 用於設定智能等待機制   會在指定時間內持續檢查條件是否滿足

class LawyersSpider(scrapy.Spider):

    name = 'demo_lawyers'
    start_urls = ['https://lawyercard.ai/lawyerCard']

    
 
    def start_requests(self):
        url = 'https://lawyercard.ai/lawyerCard'
        yield SeleniumRequest(url=url, callback=self.parse)
    
    def parse(self, response):
        driver = response.meta['driver']
        wait = WebDriverWait(driver, 10)
        
        # 設定要爬取的頁數
        max_pages = 4
        current_page = 1
        

        # 循環處理每一頁
        while current_page <= max_pages:
            # 等待頁面加載
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.lawyer-card-v2")))
            time.sleep(2)
            
            # 獲取當前頁面內容並創建Selector對象           
            page = scrapy.Selector(text=driver.page_source)
            lawyers = page.css("div.lawyer-card-v2")
            
            for lawyer in lawyers:
                yield {
                    'name': lawyer.css("h2.lawyer-card-name-v2__lawyerName::text").get().strip()
                }
            

            # 等待下一頁按鈕可點擊
            next_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#page-next"))
            )
            # 使用JavaScript點擊下一頁按鈕
            next_button.click()
            current_page += 1
            
            