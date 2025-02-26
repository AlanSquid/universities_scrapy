import scrapy
from universities_scrapy.items import UniversityScrapyItem
import re

class LatrobeSpiderSpider(scrapy.Spider):
    name = "latrobe_spider"
    allowed_domains = ["www.latrobe.edu.au", "www.cloudflare.com"]
    # start_urls = ["https://www.latrobe.edu.au/courses/a-z"] 
    start_urls = ["https://www.latrobe.edu.au/courses?collection=course-search&query=Bachelor","https://www.latrobe.edu.au/courses?collection=course-search&query=Master"]
    eng_req_url = "https://www.latrobe.edu.au/international/applying/entry-requirements"

    all_course_url = []
    except_count = 0
    eng_req= 6
    eng_req_info = "IELTS Overall 6.0, no band less than 6.0"
    custom_settings = {
        'CONCURRENT_REQUESTS': 1
    }

    def parse(self, response):
        cards = response.css("div.search-result")

        for card in cards: 
            course_name = card.xpath("normalize-space(.//a[@class='local'])").get()
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "Double Masters"]

            # 確定要出現才可以
            keywords = ["Bachelor of", "Master of", "bachelor-of", "master-of"]
            url = card.css("a.local::attr(href)").get()
            if not course_name or \
                any(keyword in course_name for keyword in skip_keywords) or \
                sum(course_name.count(keyword) for keyword in keywords) >= 2 or  \
                not any(keyword in course_name for keyword in keywords):
                    # print('跳過course:',course_name)
                    continue
            url = (url + "#/overview?location=BU&studentType=int&year=2025")
            # print('course:',course_name,",url:",url)
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
            try:
               await page.wait_for_selector('div.ds-block', timeout=60000)
            except Exception as e:
                # print(f'超時: {e}，course: {course_name}')
                return
            page_content = scrapy.Selector(text=await page.content())
            fee_text = page_content.css('.fees-estimates p span::text').re_first(r'A\$(\d+(?: \d+)*)')
            if fee_text:
                tuition_fee = fee_text.replace(' ', '').replace(',', '')  
            else:
                tuition_fee = None

            except_text = page_content.css("h2.section-heading::text").get()
            # 跳過不開分申請的課程不開分申請的課程
            if except_text and "This course is not available to international students" in except_text and tuition_fee == None:
                # print(f'{course_name}\n{response.url}\n此課程目前不開放申請\n')
                self.except_count += 1
                return
            # 出現course-list的頁面不是單一課程，需要跳過
            if page_content.css("div.course-list"):
                self.except_count += 1
                # print('頁面不是單一課程，跳過',course_name,',url:',response.url)
                return
            if page_content.css("div.breadcrumbs"):
                self.except_count += 1
                # print('頁面不是單一課程，跳過',course_name,',url:',response.url)
                return
            fee_text = page_content.css('.fees-estimates p span::text').re_first(r'A\$(\d+(?: \d+)*)')
            if fee_text:
                tuition_fee = fee_text.replace(' ', '').replace(',', '')  
            else:
                tuition_fee = None

            duration_info = page_content.xpath('//table//tr[th[contains(text(), "Duration")]]/td/text()').get()
            duration_info = duration_info.strip() if duration_info else None
            # 提取 full time 前的數字
            pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full-time"
            match = re.search(pattern, duration_info)
            if match:
                duration = match.group(1)
            else:
                duration = None
            location = page_content.xpath('//table//tr[th[contains(text(), "Available locations")]]/td/text()').get()
            location = location.strip() if location else None
            if location and location.lower() == "online":
                self.except_count += 1
                return

            if course_name is None:
                return
            else:
                # name = re.sub(r'\b(master of|bachelor of)\b', '', course_name, flags=re.IGNORECASE).strip()
                if "bachelor" in course_name.lower():
                    degree_level_id = 1
                elif "master" in course_name.lower(): 
                    degree_level_id = 2
                    
            university = UniversityScrapyItem()
            university['university_name'] = "La Trobe University"
            university['name'] = course_name  
            university['min_fee'] = tuition_fee
            university['max_fee'] = tuition_fee
            university['eng_req'] = self.eng_req
            university['eng_req_info'] = self.eng_req_info
            university['campus'] = location
            university['duration'] = duration
            university['duration_info'] = duration_info
            university['degree_level_id'] = degree_level_id
            university['course_url'] = response.url
            university['eng_req_url'] = self.eng_req_url
            yield university
            
        except Exception as e:
            # print(f'{response.url}\n此課程錯誤: {e}\n')
            self.except_count += 1

        finally:
            # 確保頁面被正確關閉
            if page:
                await page.close()

    def closed(self, reason):   
        print(f'{self.name}爬蟲完成!\n樂卓博大學, 共有 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')
        
