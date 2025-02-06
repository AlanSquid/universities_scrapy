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
    start_urls = ["https://study.uq.edu.au/study-options/programs?type=program&level[Undergraduate]=Undergraduate&level[Postgraduate]=Postgraduate&single_dual[single]=single&year=2025&attendance[ft]=ft"]
    all_course_url = []
    start_time = time.time()

    def parse(self, response):
        # 抓取當前頁面的所有課程卡片
        # all_course_cards = response.css('a.card__link')
        all_course_cards = response.css('div.card--bordered')

        for card in all_course_cards:
            category_card_url = card.css('a.card__link::attr(href)').get()
            category_card_url = response.urljoin(category_card_url)
            card_name = card.css('div.card__header h3.card__title::text').get()
            title = card.css('div.card__header h3.card__title span.card__title__super::text').get()
            full_title = f"{title}{card_name}".strip()
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Online", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of", "Doctor of"]
            if not full_title or any(keyword in full_title for keyword in skip_keywords) or sum(full_title.count(keyword) for keyword in keywords) >= 2:
                continue 
            self.all_course_url.append(category_card_url)
    
        # 查找下一頁按鈕
        next_page_button = response.css('li.pager__item.pager__item--next a[title="Go to page "]::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            # print(f"Navigating to next page: {next_page_url}")
            yield response.follow(next_page_url, self.parse)       

        else:
            # 取得所有課程後，查找各課程細節
            for url in self.all_course_url:
                yield response.follow(url, self.parse_course_detail)       
 
    def parse_course_detail(self, response):
        course_url = response.url
        # 科系名稱
        course_name = response.css("div.hero__text h1::text").get().strip()
        degree_level = response.css("div.hero__text h1 span::text").get()
        
        degree_level_id = None
        if "bachelor" in degree_level.lower():
            degree_level_id = 1
        elif "master" in degree_level.lower(): 
            degree_level_id = 2
        # 學費
        try:
            tuition_fee = response.css("dl dd a[href='#fees-scholarships']::text").get().strip().replace("A$", "")
        except:
            tuition_fee = "此科系還沒有公布學費"
    
        # 校區
        location = response.css("dt:contains('Location') + dd::text").get().strip()
        
        # 修課時間
        duration_info = response.css("dt:contains('Duration') + dd::text").get().strip()
        match = re.search(r"(\d+(\.\d+)?)", duration_info)
        duration = float(match.group(1)) if match else None

        # 英文門檻
        entry_requirements_url = response.url + "#entry-requirements"
        yield SeleniumRequest(
            url=entry_requirements_url, 
            callback=self.parse_eng_requirement,
            meta={'course_url': course_url, 'course_name': course_name, 'tuition_fee': tuition_fee, 'location': location, 'duration_info': duration_info, 'duration': duration, 'degree_level_id':degree_level_id},
            wait_time=10,
            wait_until=EC.presence_of_element_located((By.CSS_SELECTOR, "section.section--narrow-floated.section--mobile-accordion.accordion.processed")),
            dont_filter=True,
        )
    
    def parse_eng_requirement(self, response):
        course_url = response.meta['course_url']
        course_name = response.meta['course_name']
        tuition_fee = response.meta['tuition_fee']
        location = response.meta['location']
        duration_info = response.meta['duration_info']
        duration = response.meta['duration']
        degree_level_id = response.meta['degree_level_id']
        # 英文門檻
        paragraphs = response.css('div.field.field-description.field-type-text-long.field-label-hidden p::text').getall()
        IELTS_grade_result = ''
        eng_req = None

        for text in paragraphs:
            if 'IELTS' in text:
                IELTS_grade = text.split(';')[0].strip()
                match = re.search(r"(IELTS)\s.*?(\d+\.\d+|\d+)", IELTS_grade)
                eng_req = match.group(2)
                IELTS_grade_result = f"{match.group(1)} {match.group(2)}"
                
        
        university = UniversityScrapyItem()
        university['university_id'] = 21
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['min_fee'] = tuition_fee
        university['eng_req'] = eng_req
        university['eng_req_info'] = f'{IELTS_grade_result}'
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = course_url
        yield university
                    
    def close(self):
        print(f'\n{self.name}爬蟲完畢！\n昆士蘭大學，共{len(self.all_course_url)}筆資料\n')
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'{elapsed_time:.2f}', '秒')