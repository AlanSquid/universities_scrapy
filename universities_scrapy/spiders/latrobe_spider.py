import scrapy
from universities_scrapy.items import UniversityScrapyItem


class LatrobeSpiderSpider(scrapy.Spider):
    name = "latrobe_spider"
    allowed_domains = ["www.latrobe.edu.au", "www.cloudflare.com"]
    # start_urls = ["https://www.latrobe.edu.au/courses/a-z"] 
    start_urls = ["https://www.latrobe.edu.au/courses?collection=course-search&query=Bachelor"]
    all_course_url = []
    except_count = 0
    english_requirement = "IELTS 6.0 (單項不低於 6.0)"
    english_requirement_url = "https://www.latrobe.edu.au/international/applying/entry-requirements"
    custom_settings = {
        'CONCURRENT_REQUESTS': 10,  
    }
    # def parse(self, response):
    #     urls = response.css('.ds-block.ds-block-accordion li a::attr(href)').getall()
    #     for url in urls:
    #         yield response.follow(url, self.courses_parse)
    # def courses_parse(self, response):
    #     courses = response.css('#ajax-course-list article h3')
    #     for course in courses:
    #         course_name = course.css('a::text').get()
    #         if "Bachelor" in course_name:
    #             course_url = course.css('a::attr(href)').get()
    #             url = (course_url + "#/overview?location=BU&studentType=int&year=2025")
    #             # print(url)
    #             if url not in self.all_course_url:
    #                 self.all_course_url.append(url)
    #                 yield scrapy.Request(url, callback=self.page_parse, meta=dict(
    #                     playwright = True,
    #                     download_delay=2,
    #                 ))
    def parse(self, response):
        cards = response.css("div.search-result")

        for card in cards: 
            course_name = card.xpath("normalize-space(.//a[@class='local'])").get()
            if 'Bachelor' in course_name:
                url = card.css("a.local::attr(href)").get()
                url = (url + "#/overview?location=BU&studentType=int&year=2025")
                self.all_course_url.append(url)
        # 檢查是否有下一頁
        next_page = response.css('a.fb-next-result-page.fb-page-nav::attr(href)').get()

        if next_page is not None:
            yield response.follow(next_page, self.parse)       
        else:
            for url in self.all_course_url:
                yield scrapy.Request(url, callback=self.page_parse, meta=dict(
                    playwright = True,
                    playwright_include_page = True,
                ))


    async def page_parse(self, response):   
        page = response.meta["playwright_page"]
        course_name = response.css("h1::text").get()
        try:
            await page.wait_for_selector('div.ds-grid--no-margins', timeout=10000)
            page_content = scrapy.Selector(text=await page.content())
            fee_text = page_content.css('.fees-estimates p span::text').re_first(r'A\$(\d+(?: \d+)*)')
            if fee_text:
                tuition_fee = fee_text.replace(' ', '').replace(',', '')  
            else:
                tuition_fee = None

            except_text = page_content.css("h2.section-heading::text").get()
            if except_text and "This course is not available to international students" in except_text and tuition_fee == None:
                # print(f'{course_name}\n{response.url}\n此課程目前不開放申請\n')
                self.except_count += 1
                if page:
                    await page.close() 
                return

            fee_text = page_content.css('.fees-estimates p span::text').re_first(r'A\$(\d+(?: \d+)*)')
            if fee_text:
                tuition_fee = fee_text.replace(' ', '').replace(',', '')  
            else:
                tuition_fee = None
            duration = page_content.xpath('//table//tr[th[contains(text(), "Duration")]]/td/text()').get()
            duration = duration.strip() if duration else None

            location = page_content.xpath('//table//tr[th[contains(text(), "Available locations")]]/td/text()').get()
            location = location.strip() if location else None

            university = UniversityScrapyItem()
            university['name'] = 'La Trobe University'
            university['ch_name'] = '樂卓博大學'
            university['course_name'] = course_name  
            university['min_tuition_fee'] = tuition_fee
            university['english_requirement'] = self.english_requirement
            university['location'] = location
            university['duration'] = duration
            university['course_url'] = response.url
            university['english_requirement_url'] = self.english_requirement_url
            if page:
                await page.close()            
            yield university
        except Exception as e:
            # print(f'{course_name}\n{response.url}\n此課程目前不開放申請\n')
            self.except_count += 1
            if page:
                await page.close()

    def closed(self, reason):   
        print(f'{self.name}爬蟲完成!\n樂卓博大學, 共有 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')
        
