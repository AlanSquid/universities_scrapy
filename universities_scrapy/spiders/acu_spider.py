import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re
import time


class AcuSpiderSpider(scrapy.Spider):
    name = "acu_spider"
    allowed_domains = ["www.acu.edu.au"]
    start_urls = ["https://www.acu.edu.au/study-at-acu/find-a-course/course-search-result?CourseType=Undergraduate"]
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                ),
            )

    async def parse(self, response):
        page = response.meta['playwright_page']
        # 調整網頁篩選器
        filter = await page.query_selector('section.primary-filter.desktop-width')
        
        postgraduate_btn = await filter.query_selector('ul.primary-filter__filter-search li a[data-track-label="Postgraduate"]')
        await postgraduate_btn.click()
        
        full_time_btn = await filter.query_selector('label[for="Full-time"]')
        await full_time_btn.click()
        
        international_btn = await filter.query_selector('label[for="International"]')
        await international_btn.click()
        time.sleep(1)
        result_e = await page.query_selector('.col-md-12.loading p')
        result = await result_e.text_content()
        print(result)
        
        updated_page = scrapy.Selector(text=await page.content())
        cards = updated_page.css('#courseitem')
        for card in cards:
            course_name = card.css('h5::text').get()
            print('course_name', course_name)
            
  
        
