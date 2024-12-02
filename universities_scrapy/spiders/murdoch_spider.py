import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem


class MurdochSpiderSpider(scrapy.Spider):
    name = "murdoch_spider"
    allowed_domains = ["www.murdoch.edu.au", "search.murdoch.edu.au"]
    start_urls = ["https://search.murdoch.edu.au/course-finder/?size=n_36_n&filters%5B0%5D%5Bfield%5D=study_level&filters%5B0%5D%5Bvalues%5D%5B0%5D=Undergraduate&filters%5B0%5D%5Btype%5D=any&filters%5B1%5D%5Bfield%5D=curriculum_item_type&filters%5B1%5D%5Bvalues%5D%5B0%5D=Course&filters%5B1%5D%5Btype%5D=any"]
    english_requirement_url = 'https://www.murdoch.edu.au/study/how-to-apply/entry-requirements/english-proficiency-tests'
    english_requirement = 'IELTS Academic 6.0 (單科不低於6.0)'
    courses = []

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, self.parse, meta=dict(
                playwright=True,
                playwright_include_page=True,
                playwright_page_methods=[
                    PageMethod('wait_for_selector', 'ul.search-results a.card')
                ]
            ))
    
    
    async def parse(self, response):
        page = response.meta['playwright_page']
        self.extract_course_url(response)
        while True:
            try: 
                next_page = await page.wait_for_selector('ul.pagination .page-item span.fal.fa-arrow-right', state='visible', timeout=1000)
            except :
                # 沒有下一頁就跳出迴圈
                break
            
            # 點擊下一頁
            await next_page.click()
            
            # 等待頁面內容更新
            await page.wait_for_function(self.wait_for_content_update_script)
            updated_page = scrapy.Selector(text=await page.content())
            self.extract_course_url(updated_page)
            
        await page.close()
        
        # 進入課程頁面抓取細節
        for course in self.courses:
            yield scrapy.Request(course['url'], self.parse_course_page, meta=dict(
                course_name=course['name'],
                playwright=True,
                playwright_include_page=True,
                playwright_page_methods=[
                    PageMethod('click', 'label.international')
                ]
            ))
    
    # 提取課程內容
    async def parse_course_page(self, response):
        page = response.meta['playwright_page']
        await page.close()
        course_name = response.meta['course_name']
        course_url = response.url
        # print(f'正在抓取{course_name}\n{course_url}')
        
        # 抓取學費
        tuition_fee_raw = response.xpath('//div[@class="is-international"][2]/dd/text()').get()
        tuition_fee = tuition_fee_raw.replace('$', '').replace(',', '') if tuition_fee_raw else None
        
        # 抓取學制
        duration = response.xpath('//dl[@class="course-info"]/div[3]/dd/text()').get()
        
        # 抓地區，護理學位在Mandurah，其餘在Perth
        location = 'Perth'
        if 'Nursing' in course_name:
            location = 'Mandurah'
            
        # 存入item
        item = UniversityScrapyItem()
        item['name'] = 'Murdoch University'
        item['ch_name'] = '梅鐸大學'
        item['course_name'] = course_name
        item['course_url'] = course_url
        item['min_tuition_fee'] = tuition_fee
        item['english_requirement'] = self.english_requirement
        item['english_requirement_url'] = self.english_requirement_url
        item['location'] = location
        item['duration'] = duration
        
        yield item
        
        
    
    # 提取課程名稱與URL
    def extract_course_url(self, response):
        cards = response.css('ul.search-results a.card')
        for card in cards:
            course_name = card.css('::attr(data-value)').get()
            course_url = card.css('::attr(href)').get()
            # print(f'{course_name}\n{course_url}\n')
            self.courses.append({
                'name': course_name,
                'url': course_url
            })
            
    # Javascript語法，用來等待頁面內容更新
    wait_for_content_update_script = """
    () => {
        const oldContent = document.querySelector('ul.search-results').innerHTML;
        const checkContent = () => {
            return document.querySelector('ul.search-results').innerHTML !== oldContent;
        };
        return new Promise(resolve => {
            const interval = setInterval(() => {
                if (checkContent()) {
                    clearInterval(interval);
                    resolve(true);
                }
            }, 100);
        });
    }
    """
    
    def closed(self, reason):
        print(f'{self.name} 爬蟲完成!')
        print(f'梅鐸大學, 共有 {len(self.courses)} 筆資料\n')
        
            
        
