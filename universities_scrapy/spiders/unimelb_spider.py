import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

class UnimelbSpiderSpider(scrapy.Spider):
    name = "unimelb_spider"
    allowed_domains = ["www.unimelb.edu.au", "study.unimelb.edu.au"]
    start_urls = ["https://study.unimelb.edu.au/find/?collection=find-a-course&profile=_default&query=%21showall&num_ranks=12&start_rank=1&f.Tabs%7CtypeCourse=Courses&f.Study+level%7CcourseStudyLevel=undergraduate"]
    course_detail_urls = []
    
    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(
                url=url, 
                callback=self.parse, 
                wait_time=5,
                wait_until=lambda driver: WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-result__card.card.course")))
            )

    
    def parse(self, response):
        courses = response.css(".search-result__card.card.course")
        
        for course in courses:
            # 抓取課程名稱
            course_name = course.css(".card-header--wrapper h4::text").get()
            # 抓取課程網址
            course_url = course.css(".card-body a:nth-of-type(1)::attr(href)").get()
            if 'Bachelor' in course_name:
                # 將課程網址存入列表
                self.course_detail_urls.append(course_url)
                print(f'{course_name}\n{course_url}\n')
            
        # 處理換頁
        next_relative_url = response.css('a.page-link.page-link--next::attr(href)').get()
        if next_relative_url is not None:
            next_url = response.urljoin(next_relative_url)
            # 換頁請求
            yield SeleniumRequest(
                url=next_url, 
                callback=self.parse, 
                wait_time=5,
                wait_until=EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".search-result__card.card.course"))
            )
        # 沒有下一頁
        else:
            # 爬取各課程詳細資訊
            for course_url in self.course_detail_urls:
                driver = response.request.meta['driver']
                wait = WebDriverWait(driver, 10)
                driver.get(course_url)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".key-facts-section__main")))

                
                
                          
                
                

        
    def closed(self, reason):
        print(f'總共找到{len(self.course_detail_urls)}個課程')