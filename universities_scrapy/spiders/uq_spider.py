import re
import time
import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from universities_scrapy.items import UniversityScrapyItem

class UqSpiderSpider(scrapy.Spider):
    name = "uq_spider"
    allowed_domains = ["uq.edu.au"]
    start_urls = ["https://study.uq.edu.au/study-options/programs?type=program&level%5BUndergraduate%5D=Undergraduate/"]
    all_course_url = []
    start_time = time.time()

    def start_requests(self):
        url = self.start_urls[0]
        yield SeleniumRequest(
            url=url,
            callback=self.parse_undergraduate,
            wait_time=10,
            wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, "button.button--transparent.student-location.js-modal-trigger.icon--standard--region-international.icon--primary.gtm-processed.modal-processed"))
        )

    def parse_undergraduate(self, response):
        # 抓取當前頁面的所有課程卡片
        all_course_cards = response.css('a.card__link.gtm-processed')
        for card in all_course_cards:
            category_card_name = card.css('::text').get()
            category_card_url = card.css('::attr(href)').get()
            category_card_url = response.urljoin(category_card_url)
            self.all_course_url.append(category_card_url)

        # 查找下一頁按鈕
        next_page_button = response.css('li.pager__item.pager__item--next a[title="Go to page "]::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            # print(f"Navigating to next page: {next_page_url}")
            yield SeleniumRequest(
                url=next_page_url,
                callback=self.parse_undergraduate,
                wait_time=10,
                wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, 'a[title="Go to page "]'))
            )
        else:
            # 取得所有課程後，查找各課程細節
            for url in self.all_course_url:
                yield SeleniumRequest(
                    url=url,
                    callback=self.parse_course_detail,
                    wait_time=10,
                    wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, "button.button--transparent.student-location.js-modal-trigger.icon--standard--region-international.icon--primary.gtm-processed.modal-processed"))
                )
                
    def parse_course_detail(self, response):
        course_url = response.url
        # 科系名稱
        course_name = response.css("div.hero__text h1::text").get().strip()
        
        # 學費
        try:
            tuition_fee = response.css("dl dd a[href='#fees-scholarships']::text").get().strip().replace("A$", "")
        except:
            tuition_fee = "此科系還沒有公布學費"
    
        # 校區
        location = response.css("dt:contains('Location') + dd::text").get().strip()
        
        # 修課時間
        duration = response.css("dt:contains('Duration') + dd::text").get().strip()
        
        # 英文門檻
        entry_requirements_url = response.url + "#entry-requirements"
        yield SeleniumRequest(
            url=entry_requirements_url, 
            callback=self.parse_eng_requirement,
            meta={'course_url': course_url, 'course_name': course_name, 'tuition_fee': tuition_fee, 'location': location, 'duration': duration},
            wait_time=10,
            wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, "section.section--narrow-floated.section--mobile-accordion.accordion.processed")),
            dont_filter=True,
        )
    
    def parse_eng_requirement(self, response):
        course_url = response.meta['course_url']
        course_name = response.meta['course_name']
        tuition_fee = response.meta['tuition_fee']
        location = response.meta['location']
        duration = response.meta['duration']
        
        # 英文門檻
        paragraphs = response.css('div.field.field-description.field-type-text-long.field-label-hidden p::text').getall()
        IELTS_grade_result = ''
        
        for text in paragraphs:
            if 'IELTS' in text:
                IELTS_grade = text.split(';')[0].strip()
                match = re.search(r"(IELTS)\s.*?(\d+\.\d+|\d+)", IELTS_grade)
                IELTS_grade_result = f"{match.group(1)} {match.group(2)}"
                
        
        university = UniversityScrapyItem()
        university['name'] = "University of Queensland"
        university['ch_name'] = "昆士蘭大學"
        university['course_name'] = course_name
        university['min_tuition_fee'] = tuition_fee
        university['english_requirement'] = f'{IELTS_grade_result}'
        university['location'] = location
        university['course_url'] = course_url
        university['duration'] = duration
        yield university
        
    def close(self):
        print(f'\n{self.name}爬蟲完畢！\n昆士蘭大學，共{len(self.all_course_url)}筆資料\n')
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'{elapsed_time:.2f}', '秒')