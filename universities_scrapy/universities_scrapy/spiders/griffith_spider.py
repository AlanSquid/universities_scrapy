import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait  # 用於設定智能等待機制   會在指定時間內持續檢查條件是否滿足
from universities_scrapy.items import UniversityScrapyItem  
from selenium.common.exceptions import TimeoutException 


class GriffithSpider(scrapy.Spider):
    name = "griffith"
    allowed_domains = ["www.griffith.edu.au"]
    start_urls = ["https://www.griffith.edu.au/"]

    def start_requests(self):
        url = 'https://www.griffith.edu.au/study/degrees?academicCareerCode=ugrd&studentType=international'
        yield SeleniumRequest(url=url, callback=self.parse)


    def parse(self, response):
        driver = response.meta['driver']
        wait = WebDriverWait(driver, 10) 

        # 滾到最底部
        self.scroll_to_bottom(driver) 

        # 等待資料加載完成
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.result.card.trim")))

        # 獲取頁面內容並轉換為 Scrapy 的 Selector 對象
        page = scrapy.Selector(text=driver.page_source)
        cards = page.css("div.result.card.trim")

        for card in cards:
            # 提取每個卡片的連結
            degree_link = card.css("div.degree-link-wrapper p.degree a::attr(href)").get()
            if degree_link:
                # 確保鏈接是完整的URL
                full_link = response.urljoin(degree_link)

                degree_name = card.css("div.degree-link-wrapper p.degree a::text").get().strip()

                driver.get(full_link)  # 確保獲取最新的頁面

                print(f"Waiting for element on {full_link}")
                try:
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "dt.info-group-title.campus + div dd")))
                    print("Element found!")
                except TimeoutException:
                    print("Element not found for this card.")
                    continue  # 如果元素未找到，跳過當前卡片

                #取得校區
                campus_elements = driver.find_elements(By.CSS_SELECTOR, "dt.info-group-title.campus + div dd")
                campus = ', '.join([element.text.strip() for element in campus_elements]) if campus_elements else "N/A"               
                
                #取得ielts要求
                ielts_info = driver.find_element(By.CSS_SELECTOR, "dl.info-group.entry-requirement-group dd .badge").text.strip() if driver.find_elements(By.CSS_SELECTOR, "dl.info-group.entry-requirement-group dd .badge") else "N/A"
                english_requirement = ielts_info.replace('\n', ' ') if ielts_info != "N/A" else "N/A"
                
                # 取得學費
                tuition_fee = driver.find_element(By.CSS_SELECTOR, "dl.fee-group dd").text.strip() if driver.find_elements(By.CSS_SELECTOR, "dl.fee-group dd") else "N/A"
                tuition_fee = tuition_fee.replace('$', '').replace(' per year', '').replace(',', '').strip() if tuition_fee != "N/A" else "N/A"
                
                
                # 把資料存入 Item
                item = UniversityScrapyItem()
                item['name'] = 'Griffith University'
                item['ch_name'] = '格里菲斯大學'
                item['course'] = degree_name  
                item['tuition_fee'] = tuition_fee
                item['location'] = campus
                item['english_requirement'] = english_requirement

                yield item


    def scroll_to_bottom(self, driver):
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            # 滾動到頁面底部
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 等待頁面加載
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break  # 如果頁面高度不變，表示已經滾動到底部，停止滾動
            last_height = new_height
