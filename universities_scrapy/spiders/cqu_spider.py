import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re
import html


class CquSpiderSpider(scrapy.Spider):
    name = "cqu_spider"
    allowed_domains = ["www.cqu.edu.au"]
    start_urls = [
        "https://www.cqu.edu.au/courses?profile=_default&collection=cqu~sp-courses&f.Study+Level|studyLevel=Undergraduate|Postgraduate&f.Domestic+or+International|audience=International&f.Study+Mode|studyModes=On+Campus"
    ]
    courses = []
    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = [
        "(Honours)",
        "/",
    ]
    exclude_count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod(
                            "wait_for_selector",
                            'a[data-testid="CourseCard"]',
                            timeout=10000,
                        ),
                    ],
                ),
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        while True:
            show_more_btn = await page.query_selector('button[aria-label="Show More"]')
            if show_more_btn and await show_more_btn.is_visible():
                await show_more_btn.click()
                await page.wait_for_timeout(2000)
            else:
                break
        updated_page = scrapy.Selector(text=await page.content())
        await page.close()

        cards = updated_page.css('a[data-testid="CourseCard"]')
        for card in cards:
            course_name = card.css('h3[data-testid="CourseName"]::text').get().strip()
            if any(keyword in course_name for keyword in self.keywords) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):
                link = card.css("::attr(href)").get()
                course_url = response.urljoin(link)
                self.courses.append({"name": course_name, "url": course_url})

        for course in self.courses:
            yield scrapy.Request(
                course["url"],
                self.parse_course,
                meta=dict(
                    # playwright=True,
                    # playwright_include_page=True,
                    course_name=course["name"]
                ),
            )

    async def parse_course(self, response):
        # 課程名稱
        course_name = response.meta["course_name"]

        #  英文門檻
        script_text = response.css('script[type="application/ld+json"]::text').get()
        eng_req_info = self.extract_eng_req(script_text)
        if eng_req_info is None:
            script_text = response.css('script#__NEXT_DATA__::text').get()
            eng_req_info = self.extract_eng_req(script_text)

        info_block = response.css('div[class*="FactBox_factSection"]')
        info_elements = info_block.css('div div div[class*="label"]')
        
        campus = None
        fees = None
        duration = None
        duration_info = None
        
        for info in info_elements:
            title = info.css("::text").get()

            # 學期制度
            if "Duration" in title:
                duration_info = info.xpath("following-sibling::div[1]//text()").get()
                if duration_info:
                    duration_info = duration_info.split(",")[0].strip()
                    duration = re.search(r"\d+(\.\d+)?", duration_info).group()
            # 學區
            elif "Location" in title:
                campus = info.xpath("following-sibling::div[1]//text()").get().strip()
                if campus == "Online":
                    campus = None
                    
            # 學費
            elif "First-year fee" in title:
                fees = info.xpath("following-sibling::div[1]/div/div//text()").get()
                if fees:
                    fees = fees.strip().replace("A$", "").replace(",", "")

        # print(course_name)
        # print(response.url)
        # print(eng_req_info)
        # print(fees)
        # print(campus)
        # print(duration)
        # print(duration_info)
        
        if not fees or not campus or not duration: 
            self.exclude_count += 1
            return  
          
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_id"] = 17
        university["name"] = course_name
        university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
        university["min_fee"] = fees
        university["max_fee"] = fees
        university["eng_req"] = re.search(r"\d+(\.\d+)?", eng_req_info).group()
        university["eng_req_info"] = eng_req_info
        university["campus"] = campus
        university["duration"] = duration
        university["duration_info"] = duration_info
        university["course_url"] = response.url
        
        yield university

    def extract_eng_req(self, text):
        # 解碼 HTML 實體
        text = html.unescape(text)
        
        # 移除 HTML 標籤
        text = re.sub(r'<[^>]+>', '', text)

        pattern = r"IELTS.*?(overall.*?(?<!\d)(?=[.;]|, or))"
        match = re.search(pattern, text)
        if match:
            result = match.group(1).strip()
            result = result.replace(".&nbsp", "")
            return result
        else:
            pattern = r"IELTS.*?(?<!\d)\.(?=[^0-9]|$)"
            match = re.search(pattern, text)
            if match:
                result = match.group(0).strip()
                return result
            
    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(f"中央昆士蘭大學, 共有 {len(self.courses) - self.exclude_count} 筆資料(已排除)")
        print(f"排除 {self.exclude_count} 筆資料")
        print("\n")
    
