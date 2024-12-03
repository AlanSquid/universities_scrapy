import scrapy
from universities_scrapy.items import UniversityScrapyItem
import re

class FlindersSpiderSpider(scrapy.Spider):
    name = "flinders_spider"
    allowed_domains = ["www.flinders.edu.au", "flinders.edu.au"]
    start_urls = ["https://www.flinders.edu.au/international"]
    course_urls = []

    def parse(self, response):
        study_areas_urls = response.xpath('//section/div/div[@class="section"][7]').css('.cta-button a::attr(href)').getall()
        for relative_url in study_areas_urls:
            url = response.urljoin(relative_url)
            yield scrapy.Request(url, callback=self.extract_course_url)
            
    def extract_course_url(self, response):
        urls = response.xpath('//div[@class="course_list_component"]//div[@class="accordion_item"][1]')\
        .css('ul.course_list li a::attr(href)').getall()

        for url in urls:
            yield scrapy.Request(url, callback=self.parse_course_page, meta=dict(
                playwright = True,
            ))
        
        self.course_urls += urls
        self.course_urls = list(set(self.course_urls))
            
    def parse_course_page(self, response):
        # 抓課程名稱
        course_name = response.css('h1.yellow_heading::text').get()
        
        info = response.css('.ff-tab-content.international_content div.col-lg-8.col-md-6:nth-of-type(2) div.col-md-12.col-lg-6:nth-of-type(1)')
        
        # 抓取地區
        location_list_raw = info.css('div.col-sm-6:nth-of-type(2) ul.content_list li::text').getall()
        location_list = [l.strip('– ') for l in location_list_raw]
        location = ', '.join(location_list)
          
        # 抓取學制
        duration = info.css('div.col-sm-6:nth-of-type(3) p.content_detail::text').get().strip()
        
        # 抓取學費
        tuition_fee_raw = response.css('.ff-tab-content.international_content div.col-lg-8.col-md-6:nth-of-type(2) div.col-md-12.col-lg-6:nth-of-type(2) ul.content_list li::text').get()
        match = re.search(r'\$(\d{1,3}(?:,\d{3})*)', tuition_fee_raw)
        if match:
            tuition_fee = match.group(1).replace(',', '')
            
        
        # 抓取英文門檻
        english_requirement = 'IELTS ' + response.css('.english-reqs.content_container :nth-child(1) .english-reqs__summary .english-reqs__score.english-reqs__score--large::text').get()
        
        # print(course_name)
        # print(response.url)
        # print(tuition_fee)
        # print(english_requirement)
        # print(duration)
        # print(location)
        # print('\n')
        
        # 存入UniversityScrapyItem
        item = UniversityScrapyItem()
        item['name'] = 'Flinders University'
        item['ch_name'] = '弗林德斯大學'
        item['course_name'] = course_name
        item['course_url'] = response.url
        item['min_tuition_fee'] = tuition_fee
        item['duration'] = duration
        item['english_requirement'] = english_requirement
        item['location'] = location
        
        yield item
        
    def closed(self, reason):
        print(f'{self.name}爬蟲完成!')
        print(f'弗林德斯大學，共有 {len(self.course_urls)} 筆資料\n')

