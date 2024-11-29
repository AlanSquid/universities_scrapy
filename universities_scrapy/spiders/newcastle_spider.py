import scrapy
import time
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
from urllib.parse import urlparse

class NewcastleSpiderSpider(scrapy.Spider):
    name = "newcastle_spider"
    allowed_domains = ["www.newcastle.edu.au", 'handbook.newcastle.edu.au']
    start_urls = ["https://www.newcastle.edu.au/degrees#filter=level_undergraduate,intake_international"]
    courses = []
    except_count = 0
    custom_settings = {
        'CONCURRENT_REQUESTS': 10,
    }
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta=dict(
                playwright = True,
		    ))
    
    def parse(self, response):
        rows = response.css('.uon-filtron-row.uon-card:not([style*="display: none;"])')
        for row in rows:
            course_name = row.css('.degree-title a.degree-link::text').get()
            course_url = row.css('.degree-title a.degree-link::attr(href)').get()
            course = {'name': course_name, 'url': course_url}
            if 'Bachelor' in course_name and '(pre' not in course_name:
                    self.courses.append(course)
        
        # print(f'Found {len(self.courses)} courses')
        
        for course in self.courses:
            course_url = response.urljoin(course['url'])
            parsed_url = urlparse(course_url)
            domain = parsed_url.netloc
            if domain == 'www.newcastle.edu.au':
                yield scrapy.Request(course_url, callback=self.parse_course_page, meta=dict(
                    course_name = course['name'],
                    playwright = True,
                    playwright_include_page = True,
                ))
            elif domain == 'handbook.newcastle.edu.au':
                yield scrapy.Request(course_url, callback=self.parse_handbook_course_page, meta=dict(
                    course_name = course['name'],
                    playwright = True,
                ))
                    

    
    async def parse_course_page(self, response):
        page = response.meta["playwright_page"]
        modal = response.css('#uon-preference-popup-overlay.open')
        if modal:
            await page.click('label[for="degree-popup-intake-international"]')
            await page.click('#uon-preference-save')
        course_page = scrapy.Selector(text=await page.content())
        await page.close()
        # 課程名稱
        course_name = response.meta["course_name"]
        # 抓取學費
        tuition_fee_raw = course_page.css('.bf.degree-international-fee::text').get()
        if tuition_fee_raw is None:
            self.except_count += 1
            return
        tuition_fee = tuition_fee_raw.replace('AUD', '').replace(',', '').strip() if tuition_fee_raw else None
        #抓取學制
        duration = course_page.css('.bf.degree-full-time-duration::text').get()
        #抓取英文門檻
        overall_min_value= course_page.css('.admission-info-mid .ELROverallMinValue::text').get()
        subtest_min_value = course_page.css('.admission-info-mid .ELRSubTestMinValue::text').get()
        english_requirement = f'IELTS {overall_min_value} (單科不得低於{subtest_min_value})'
        # 抓取地區
        location_list = course_page.css('#degree-location-toggles .uon-option-toggle label::text').getall()
        location = ', '.join(location_list)
        
        # print(course_name)
        # print(response.url)
        # print(tuition_fee)
        # print(duration)
        # print(english_requirement)
        # print(location, '\n')
        
        # 存入UniversityScrapyItem
        item = UniversityScrapyItem()
        item['name'] = 'Newcastle University'
        item['ch_name'] = '紐卡索大學'
        item['course_name'] = course_name
        item['min_tuition_fee'] = tuition_fee
        item['duration'] = duration
        item['english_requirement'] = english_requirement
        item['location'] = location
        item['course_url'] = response.url
        yield item
        
    def parse_handbook_course_page(self, response):
        info = response.css('.css-1dlnkq6-Box--Box-Box-Card--Card-Card-EmptyCard--EmptyCard-RHS--AttributesTable.e1tmpufd0')
        
        # 課程名稱
        course_name = response.meta["course_name"]
        
        # 學制
        duration = info.css(':nth-child(7) div .css-19qn38w-Box--Box-Box-Flex--Flex-Flex.e8qda2r1::text').get().strip() + ' years'
        
        # 地區
        location = info.css(':nth-child(11) div .css-19qn38w-Box--Box-Box-Flex--Flex-Flex.e8qda2r1::text').get().strip()
        
        
        # 英文門檻
        eng_req_info = response.css('div[aria-label="English language requirements accordions"]')
        score = eng_req_info.css('.css-apyj4p-Box--Box-Box-Card--CardBody.e12hqxty1::text').get()
        english_requirement = f'IELTS {score} (單科不得低於{score})'
        
        # print(course_name)
        # print(response.url)
        # print(duration)
        # print(english_requirement)
        # print(location, '\n')
        
        # 存入UniversityScrapyItem
        item = UniversityScrapyItem()
        item['name'] = 'Newcastle University'
        item['ch_name'] = '紐卡索大學'
        item['course_name'] = course_name
        item['min_tuition_fee'] = None # 沒有學費資訊
        item['duration'] = duration
        item['english_requirement'] = english_requirement
        item['location'] = location
        item['course_url'] = response.url
        yield item
    
    def closed(self, reason):
        print(f'{self.name}爬蟲完成!')
        print(f'紐卡索大學，共有 {len(self.courses) - self.except_count} 筆資料')
        print(f'有 {self.except_count} 筆目前不開放申請\n')
        

