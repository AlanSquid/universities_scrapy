import re
import time
import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem

class QutSpiderSpider(scrapy.Spider):
    name = "qut_spider"
    allowed_domains = ["www.qut.edu.au"]
    start_urls = ["https://www.qut.edu.au/study/international/"]
    seen_urls = set()
    start_time = time.time()

    def start_requests(self):
        # 用 response.follow 發送起始請求
        url = self.start_urls[0]
        yield SeleniumRequest(url=url, callback=self.parse)

    # 到 https://www.qut.edu.au/study/international 頁面找到15個課程大類
    def parse(self, response):
        urls = response.css('ul.study-area-links li.list-links a.arrow-link::attr(href)').getall()
        for url in urls:
            if url:
                # 跟隨連結進入新的頁面
                yield response.follow(url, callback=self.parse_areas)

    # 進入各課程大類共三種狀況 1. 需先選擇undergraduate 或 postgraduate。(e.g. Justice) 2. 有分不同的課程類型。(e.g. Business) 3. 直接有課程
    # 第3種狀況中的又有Create Arts的部分比較特殊，又進一步細分小類別
    def parse_areas(self, response):
        # 檢查是否存在 "Explore our undergraduate courses"
        undergraduate_button = response.css('a.button.blue.button--blue-outline.arrow.mb-3.study-area-list-buttons.w-100')
        course_links = response.css('ul.study-area-links li.list-links a.arrow-link')
        bachelor_courses = response.css('.row .col-lg-4')
        
        # 處理第一種狀況
        if undergraduate_button:
            button_text = undergraduate_button.css('::text').get()
            if button_text and 'Explore our undergraduate courses' in button_text:
                url = undergraduate_button.attrib.get('href')
                yield response.follow(
                    url=response.urljoin(url),
                    callback=self.parse_course_link,
                )

        # 第二種狀況
        elif course_links:
            for link in course_links:
                course_name = link.css('::text').get().strip()
                url = link.css('::attr(href)').get()
                yield response.follow(
                    url=response.urljoin(url),
                    callback=self.parse_course_link,
                )

        # 第三種狀況
        elif bachelor_courses:
            for course in bachelor_courses:
                course_name = course.css('h3::text').get(default='').strip()
                
                if 'Bachelor' in course_name:
                    course_link = course.css('a.arrow-link::attr(href)').get()
                    
                    # 如果是art中的creative art類別，要到parse_creative_art_course再進一層解析
                    if "creative-art" in str(course_link):
                        art_course_group_link = course_link
                        yield response.follow(
                            url=response.urljoin(art_course_group_link),
                            callback=self.parse_creative_art_course,
                        )
                        
                    # 如果有連結，進行資料返回    
                    elif course_link:
                        yield response.follow(
                            url=response.urljoin(course_link) + "?international",
                            callback=self.parse_course_page,
                            meta={'course': course_name, 'url': response.urljoin(course_link) + "?international"},
                        )
    # 專門處理creative art小類別的url的function
    def parse_creative_art_course(self, response):
        art_course_names = response.css('li.no-list-bullets a::text').getall()
        art_course_links = response.css('li.no-list-bullets a::attr(href)').getall()
        for i in range(len(art_course_names)):
            if 'Bachelor' in art_course_names[i]:
                art_course_name = art_course_names[i].strip()
                art_course_link = art_course_links[i].strip()
                if art_course_link in self.seen_urls:
                    continue
                
                # 如果是新的 URL，就加入集合並進行 yield
                self.seen_urls.add(art_course_link)
                yield response.follow(
                    url=response.urljoin(art_course_link),
                    callback=self.parse_course_page,
                    meta={'course': art_course_name, 'url': response.urljoin(art_course_link) + "?international"},
                )
    # 除了creative art小類別，蒐集其他網頁的課程url
    def parse_course_link(self, response):
        bachelor_courses = response.css('div.col-md-12 a.course-page-link.qut-course-page-link')
        
        if bachelor_courses:
            for course in bachelor_courses:
                course_name = course.css('::text').get().strip()
                course_link = course.attrib.get('href')
                if course_name and course_link and 'Bachelor' in course_name:
                    # 如果 URL 已經被處理過，則跳過這個項目
                    if course_link in self.seen_urls:
                        continue
                    
                    # 如果是新的 URL，就加入集合並進行 yield
                    self.seen_urls.add(course_link)
                    yield response.follow(
                        url=response.urljoin(course_link) + "?international",
                        callback=self.parse_course_page,
                        meta={'course': course_name, 'url': response.urljoin(course_link) + "?international"},
                    )
                    
    # 在課程網頁中抓取資料
    def parse_course_page(self, response):

        meta_data = response.meta 
        course = meta_data['course']
        url = meta_data['url']
        
        # 費用處理
        tuition_fee = ''
        fees_all = response.css('div.box-wrap.col-sm-6 div.box-content p::text').getall()
        for fee in fees_all:
            if "CSP" in fee:
                continue
            if "2025" in fee:  # 檢查是否包含 2025
                match = re.search(r'\$(\d{1,3}(?:,\d{3})*)', fee)  # 使用正則表達式抓取費用
                if match:
                    tuition_fee = match.group(1).replace(',', '')  # 去掉千位分隔符
                    break
        
        # 校區處理
        locations = response.css('ul[data-course-map-key="quickBoxDeliveryINT"] li::text').getall()
        location = ', '.join(locations)
        
        # 英文門檻
        english_requirement = ''
        english_requirements = response.css('table#int-elt-table td#elt-overall::text').getall()
        for number in english_requirements:
            if type(number) == str:
                english_requirement = number.strip()
                break
        
        if tuition_fee and location and english_requirement:
            university = UniversityScrapyItem()
            university['name'] = "Queensland University of Technology"
            university['ch_name'] = "昆士蘭科技大學"
            university['course_name'] = course
            university['tuition_fee'] = tuition_fee
            university['english_requirement'] = f'IELTS (Academic) {english_requirement}'
            university['location'] = location
            university['course_url'] = url
            yield university

        end_time = time.time()
        elapsed_time = end_time - self.start_time
        print(f'{elapsed_time:.2f}', '秒')