import re
import time
import scrapy
from scrapy import Selector
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from universities_scrapy.items import UniversityScrapyItem


class RmitSpiderSpider(scrapy.Spider):
    name = "rmit_spider"
    allowed_domains = ["www.rmit.edu.au"]
    start_urls = ["https://www.rmit.edu.au/study-with-us/international-students/programs-for-international-students/courses-for-international-students-by-study-area?activeTab=All"]
    all_course_url = []
    all_course_name = []
    retry_quota = 100
    start_time = time.time()
    
    # custom_settings = {
    #     'FEEDS': {
    #         'rmit_data.json': {
    #             'format': 'json',
    #             'encoding': 'utf-8',
    #         },
    #         'rmit_data.csv': {
    #             'format': 'csv',
    #             'encoding': 'utf-8-sig',
    #         }
    #     },
    #     'FEED_EXPORT_FIELDS': [
    #         'name', 'ch_name', 'course_name', 'min_tuition_fee',
    #         'english_requirement', 'location', 'course_url', 'duration'
    #     ],
    # }
    
    def start_requests(self):
        url = self.start_urls[0]
        yield scrapy.Request(
            url,
            meta=dict(
                playwright=True,
                playwright_include_page = True,
            ),
            callback=self.parse_all_course, 
        )
        
    async def parse_all_course(self, response):
        page = response.meta["playwright_page"]
        await page.wait_for_selector("li[role='presentation'] a.program-list-facet[data_type='rmit:study_type/undergraduate_degree']", timeout=30 * 1000)
        page_content = scrapy.Selector(text=await page.content())
        all_course_div = page_content.css('div.rmitprogramlist.aem-GridColumn.aem-GridColumn--default--12 tbody tr.lcl.intnl td.pl--programname.hidelink a')
        await page.close()
        
        for course in all_course_div:
            course_name = course.css('::text').get()
            course_url = course.css('::attr(href)').get().strip()
            course_url = response.urljoin(course_url)
            major = ""
            is_major = False
            
            if 'Bachelor' in course_name:
                # 某些科系會進一步細分類群，但主要課程資訊(費用、門檻等)一樣需要去主要科系查看
                if course_url.count('/') == 8:
                    # 使用 rsplit 去掉 URL 的最後一部分
                    course_url, major = course_url.rsplit('/', 1)  # 這裡會將 URL 的最後部分賦值給 major
                    is_major = True
                yield SeleniumRequest(
                    url=course_url,
                    dont_filter=True,
                    meta=dict(
                        course_name=course_name,
                        is_major=is_major,
                        major=major,
                    ), 
                    callback=self.parse_course, 
                )
                
    def parse_course(self, response):
        driver = response.meta["driver"]
        course_name = response.meta['course_name']
        is_major = response.meta['is_major']
        major = response.meta['major']
        url = response.url
        
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.cbResultSetData.cbResultSetNestedAlign")))
        
        page_source = driver.page_source
        selector = Selector(text=page_source)
                
        # 費用
        fee = selector.css('span.cbResultSetData.cbResultSetNestedAlign::text').get().strip()
        pattern = r"\D*(\d+[\d,]*)"  # \D* 匹配非數字字符，\d+ 匹配數字
        match = re.search(pattern, fee)
        if match:
            tuition_fee = match.group(1).replace(",", "")
        
        # 英文門檻
        eng_req_li = selector.css('div.cmp-text li::text').getall()
        for li_text in eng_req_li:
            if 'IELTS' in li_text:
                pattern = r"IELTS\s*\((.*?)\)\s*[:：]\s*.*?(\d+(\.\d+)?)"
                match = re.search(pattern, li_text)
                if match:
                    english_requirement = match.group(2)  # 提取數字部分
                
        # 校區
        locations = selector.xpath('//dt[text()=" Location:"]/following-sibling::dd[@class="desc qf-int-location"]/text()').getall()
        locations = [all_location.strip() for all_location in locations]
        location = ', '.join(locations)
        
        # 學制(期間)
        durations = selector.xpath('//dt[text()=" Duration:"]/following-sibling::dd[@class="desc qf-int-duration"]/text()').getall()
        durations = [all_duration.strip() for all_duration in durations]
        duration = ', '.join(durations)
        
        if is_major:
            url = f"{response.url}/{major}"
        else:
            url = response.url
        
        if url not in self.all_course_url and course_name not in self.all_course_name:
            self.all_course_url.append(url)
            self.all_course_name.append(course_name)
        else:
            return
        
        university = UniversityScrapyItem()
        university['name'] = "Royal Melbourne Institute of Technology"
        university['ch_name'] = "墨爾本皇家理工大學"
        university['course_name'] = course_name
        university['min_tuition_fee'] = tuition_fee
        university['english_requirement'] = f'IELTS (Academic) {english_requirement}'
        university['location'] = location
        university['course_url'] = url
        university['duration'] = duration
        yield university
            
    def close(self):
        print(f"墨爾本皇家理工大學({self.name})總共{len(self.all_course_url)}個科系")
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'爬蟲時間: {elapsed_time:.2f}', '秒')