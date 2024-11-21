import scrapy
from universities_scrapy.items import UniversityScrapyItem 

class AnuSpiderSpider(scrapy.Spider):
    name = "anu_spider"
    allowed_domains = ["www.anu.edu.au", "study.anu.edu.au", "programsandcourses.anu.edu.au"]
    start_urls = ["https://study.anu.edu.au/apply/international-applications"]
    english_requirement_url = 'https://policies.anu.edu.au/ppl/document/ANUP_000408'
    academic_requirement_url = 'https://study.anu.edu.au/apply/undergraduate-program-indicative-entry-requirements'
    english_requirement = 'IELTS Academic: 6.5'
    location = 'canberra'
    
    detail_url_list = []
    
    def parse(self, response):
        # 發送form request
        return scrapy.FormRequest.from_response(
            response,
            formid='views-exposed-form-campaign-course-page-block-5',
            formdata={'combine': 'Bachelor'},
            callback=self.after_search
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
        course_name = response.css('h1.intro__degree-title span::text').get()
        
        # 取得學費
        tuition_fee_raw = response.css('#indicative-fees__international dl dd::text').get()
        tuition_fee = tuition_fee_raw.replace('$', '').replace(',', '').replace('.00', '').strip()
        
        
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university['name'] = 'Australian National University'
        university['ch_name'] = '澳洲國立大學'
        university['course_name'] = course_name
        university['course_url'] = response.url
        university['tuition_fee'] = tuition_fee
        university['english_requirement'] = self.english_requirement
        university['english_requirement_url'] = self.english_requirement_url
        university['location'] = self.location
        
        yield university 
        
    def closed(self, reason):    
        print(f'Australian National University爬蟲完成!\n共有 {len(self.detail_url_list)} 筆資料')
        