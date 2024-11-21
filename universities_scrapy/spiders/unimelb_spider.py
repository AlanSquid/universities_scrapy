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

    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(
                url=url, 
                callback=self.parse, 
                wait_time=5,
                wait_until=lambda driver: WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-result__card.card.course")))
            )
    
    def parse(self, response):
        response
        courses = response.css(".search-result__card.card.course")
        
        for course in courses:
            course_name = course.css(".card-header--wrapper h4::text").get()
            course_url = course.css(".card-body a:nth-of-type(1)::attr(href)").get()
            
            print(f'{course_name}, {course_url}\n')
