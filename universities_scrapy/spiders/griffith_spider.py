import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem  
from selenium.common.exceptions import TimeoutException 
import re


class GriffithSpider(scrapy.Spider):
    name = "griffith_spider"
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
            course_link = card.css("div.degree-link-wrapper p.degree a::attr(href)").get()
            if course_link:
                # 確保鏈接是完整的URL
                full_link = response.urljoin(course_link)

                course_name = card.css("div.degree-link-wrapper p.degree a::text").get().strip()

                driver.get(full_link)  # 確保獲取最新的頁面

                # print(f"Waiting for element on {full_link}")
                try:
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "dt.info-group-title.campus + div dd")))
                except TimeoutException:
                    print("Element not found for this card.")
                    continue  
                
                course_page = scrapy.Selector(text=driver.page_source)

                #取得校區              
                location_list = course_page.css("dt.info-group-title.campus + div dd::text").getall()
                location_format = ', '.join([location.strip() for location in location_list]) if location_list else None

                #取得ielts要求
                english_requirement = course_page.css("dl.info-group.entry-requirement-group dd .badge *::text").getall()
                if english_requirement:
                    english_requirement = " ".join(english_requirement).strip()  # 合并并去除首尾空格
                    english_requirement = re.sub(r"\s+", " ", english_requirement)  # 替换多余的空格为单个空格
                else:
                    english_requirement = None
                
                # 取得學費
                tuition_fee_element = course_page.css("dl.fee-group dd::text").get()
                tuition_fee = (
                    int(
                        tuition_fee_element.replace('$', '')
                        .replace(' per year', '')
                        .replace(',', '')
                        .strip()
                    )
                    if tuition_fee_element
                    else None
                )

                # 取得duration
                duration_element = course_page.css("dt.info-group-title.duration + div dd::text").getall()
                duration_raw = " ".join([d.strip() for d in duration_element]) if duration_element else None
                if duration_raw:
                    duration = duration_raw.replace(' years', ' year').replace('\xa0', ' ').strip()
                else:
                    duration = None

                # 把資料存入 university Item
                university = UniversityScrapyItem()
                university['name'] = 'Griffith University'
                university['ch_name'] = '格里菲斯大學'
                university['course_name'] = course_name
                university['tuition_fee'] = tuition_fee
                university['english_requirement'] = english_requirement
                university['location'] = location_format
                university['duration'] = duration
                university['course_url'] = full_link

                yield university
                
        print(f'Griffith University 爬蟲完成!')


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
