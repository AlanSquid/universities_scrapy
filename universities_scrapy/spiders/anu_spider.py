import scrapy
from universities_scrapy.items import UniversityScrapyItem
import re

class AnuSpiderSpider(scrapy.Spider):
    name = "anu_spider"
    allowed_domains = ["www.anu.edu.au", "study.anu.edu.au", "programsandcourses.anu.edu.au"]
    start_urls = ["https://study.anu.edu.au/apply/international-applications"]
    english_requirement_url = 'https://policies.anu.edu.au/ppl/document/ANUP_000408'
    academic_requirement_url = 'https://study.anu.edu.au/apply/undergraduate-program-indicative-entry-requirements'
    english_requirement = 'IELTS Academic: 6.5'
    campus = 'canberra'
    count = 0
    
    detail_url_list = []
    
    def parse(self, response):
        # 發送form request
        yield scrapy.FormRequest.from_response(
            response,
            formid='views-exposed-form-campaign-course-page-block-5',
            formdata={'combine': 'Bachelor'},
            callback=self.after_search,
        )
    
        # 搜尋 Master
        yield scrapy.FormRequest.from_response(
            response,
            formid='views-exposed-form-campaign-course-page-block-5',
            formdata={'combine': 'Master'},
            callback=self.after_search,
        )

    
    # 搜尋Bachelor後的解析
    def after_search(self, response):
        cards = response.css('.acc-card-body')
        for card in cards:
            # 抓取課程網址
            detail_url = card.css('.acc-card-links a:nth-of-type(2)::attr(href)').get()
            self.detail_url_list.append(detail_url)
            
        # 換頁
        next_page = response.css('li.pager__item.pager__item--next a::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.after_search)
            
        else:
            # 進入課程頁面
            for url in self.detail_url_list:
                yield response.follow(url, self.parse_course_detail)
        
    
    def parse_course_detail(self, response):
        #取得課程名稱
        course_name_raw = response.css('h1.intro__degree-title span::text').get()
        if 'Bachelor of' in course_name_raw:
            degree_level_id = 1
        elif 'Master of' in course_name_raw:
            degree_level_id = 2
        
        course_name = course_name_raw.replace('Bachelor of ', '').replace('Master of ', '').strip()
        exclude_keywords = ['(Honours)', '(Advanced)', '(Special)', 'Flexible Double Masters']
        
        if any(keyword in course_name_raw for keyword in exclude_keywords):
            return
        
        self.count += 1
        
        # 取得學費
        tuition_fee_raw = response.css('#indicative-fees__international dl dd::text').get()
        tuition_fee = tuition_fee_raw.replace('$', '').replace(',', '').replace('.00', '').strip()
        
        duration_text = response.css('li.degree-summary__requirements-length span.tooltip-area::text').get()
        duration = float(re.search(r'\d+(\.\d+)?', duration_text).group())
        
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university['university_id'] = 1
        university['name'] = course_name
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['eng_req'] = 6.5
        university['eng_req_info'] = self.english_requirement
        university['eng_req_url'] = self.english_requirement_url
        university['duration'] = duration
        university['duration_info'] = duration_text
        university['acad_req_url'] = self.academic_requirement_url
        university['campus'] = self.campus
        
        yield university 
        
    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n澳洲國立大學, 共有 {self.count} 筆資料\n')
        