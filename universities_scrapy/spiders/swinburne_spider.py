import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re


class SwinburneSpiderSpider(scrapy.Spider):
    name = "swinburne_spider"
    allowed_domains = ["www.swinburne.edu.au"]
    start_urls = ["https://www.swinburne.edu.au/courses/find-a-course/"]
    categories = []
    courses = []
    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = ["Honours", "Online"]
    count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, self.parse)

    def parse(self, response):
        ul = response.xpath(
            "//div/div[2]/article/div/div/div/section[2]/div/div/div[2]/div/ul"
        )
        cards = ul.css(".card")
        for card in cards:
            # title = card.css('.card-title::text').get().strip()
            link = card.css(".card-link.btn.btn-secondary-charcoal::attr(href)").get()
            url = response.urljoin(link)
            yield scrapy.Request(url, self.categorize_url)

    # 分類url
    def categorize_url(self, response):
        h2_elements = response.css("#content-area section h2::text").getall()
        if any("Explore our" in h2 for h2 in h2_elements):
            links = (
                response.css("#content-area h2")
                .xpath("../following-sibling::div[1]")
                .css("ul li a.card")
            )
            for link in links:
                url = response.urljoin(link.css("::attr(href)").get())
                if "/course/" in url or "/courses/" in url:
                    if "find-a-course" in url:
                        self.categories.append(url)
                    else:
                        name = link.css(".card-title::text").get().strip()
                        if any(
                            name.count(keyword) == 1 for keyword in self.keywords
                        ) and all(
                            exclude_keyword not in name
                            for exclude_keyword in self.exclude_keywords
                        ):
                            self.courses.append(url)
        else:
            self.categories.append(response.url)

        # 去重複
        self.categories = list(set(self.categories))
        for category_url in self.categories:
            yield scrapy.Request(
                category_url,
                self.extract_course_url,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", ".results-list")
                    ],
                ),
            )

    # 提取課程url
    async def extract_course_url(self, response):
        page = response.meta["playwright_page"]

        while True:
            try:
                view_more_btn = await page.query_selector(
                    "#content-area footer.results-list__footer button"
                )
                await view_more_btn.click()
                await page.wait_for_selector("a.results-item")
            except:
                break
        updated_page = scrapy.Selector(text=await page.content())
        await page.close()

        course_urls = updated_page.css("#content-area .results-list div:not([class]) a")

        for url in course_urls:
            course_url = url.css("::attr(href)").get()
            course_name = url.css(".results-column--title.h6::text").get()
            sub_name = url.css(".results-column--title.h6 em::text").get()
            if sub_name:
                course_name += sub_name
            if any(
                course_name.count(keyword) == 1 for keyword in self.keywords
            ) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):
                # print("course_name:", course_name)
                # print("course_url:", course_url)
                # print("\n")
                self.courses.append(course_url)

        # 去除重複
        self.courses = list(set(self.courses))

        for course_url in self.courses:
            yield scrapy.Request(
                course_url,
                self.parse_courses,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                ),
            )

    # 提取課程資訊
    async def parse_courses(self, response):
        page = response.meta["playwright_page"]
        # 課程名稱
        # course_name = (
        #     response.css(".course-details__title h1::text").get().strip()
        #     if response.css(".course-details__title h1::text").get()
        #     else None
        # )
        course_name_element = await page.query_selector(".course-details__title h1")
        course_name = (await course_name_element.text_content()).strip() if course_name_element else None
        # print("course_name", course_name)
        # print(response.url)
        
        # 學位
        if "Bachelor of" in course_name:
            degree_level_id = 1
        elif "Master of" in course_name:
            degree_level_id = 2
            
        # role = response.css(".course-details__availability .student-toggle::text").get()
        role_e = await page.query_selector(".course-details__availability .student-toggle")
        if not role_e:
            # text = response.css(".course-details__availability p::text").get().strip()
            # print('text', text)
            return
        role = await role_e.text_content()

        if "international" not in role:
            change_btn = await page.query_selector("#change-student-type-btn")
            await change_btn.click()
            international_btn = await page.query_selector(
                ".course-student-type__modal .course-student-type__selection-box #student-toggle--international"
            )
            await international_btn.click()
            apply_btn = await page.query_selector("#btn-apply-student-type")
            await apply_btn.click()

        updated_page = scrapy.Selector(text=await page.content())

        # info = updated_page.css(".course-details__summary-container")
        info = await page.query_selector(".course-details__summary-container")

        # 學制
        # duration = info.css(
        #     ".course-details__summary-item.course-details__duration .international::text"
        # ).get()
        duration_e = await info.query_selector(".course-details__summary-item.course-details__duration .international")
        duration = await duration_e.text_content()
        
        if not duration or not duration.strip():
            return
        duration = duration.strip().replace(" full-time", "").replace(" full time", "")
        if duration == "Full-time only":
            duration = "3 years"
        # print("duration", duration)
        
        # 學區
        # campus = info.css(
        #     ".course-details__summary-item.course-details__campus div:nth-of-type(2)::text"
        # ).get()
        campus_e = await info.query_selector(".course-details__summary-item.course-details__campus div:nth-of-type(2)")
        campus = await campus_e.text_content()
        if campus:
            campus = campus.strip()
        # print("campus", campus)

        # 英文門檻
        await page.click("#customtabs-item-entry-requirements-tab button")
        # updated_page = scrapy.Selector(text=await page.content())
        # eng_req_text = updated_page.css(
        #     "#customtabs-item-entry-requirements .contentblock.spacing-vertical-level-1-bottom.international.container .parsys_column.row div:nth-of-type(2) ul li:first-of-type::text"
        # ).get()
        eng_req_e = await page.query_selector("#customtabs-item-entry-requirements .contentblock.spacing-vertical-level-1-bottom.international.container .parsys_column.row div:nth-of-type(2) ul li:first-of-type")
        eng_req_info = await eng_req_e.text_content()
        eng_req = re.search(r"\d+(\.\d+)?", eng_req_info).group()
        # print("eng_req", eng_req["num"])
        # print("eng_req_info", eng_req["str"])

        # 學費
        await page.click("#customtabs-item-fees---scholarships-tab button")
        # updated_page = scrapy.Selector(text=await page.content())
        # fees = updated_page.css(
        #     "#customtabs-item-fees---scholarships .course-fees__block.international p.course-fees__total::text"
        # ).get()
        fees_e = await page.query_selector("#customtabs-item-fees---scholarships div.course-fees__block.international:first-of-type p.course-fees__total")
        fees = await fees_e.text_content()
        if fees:
            fees = fees.strip().replace("$", "").replace(",", "").replace(".00", "")
            # print("fees", fees)
            
        await page.close()
            
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_name"] = "Swinburne University of Technology"
        university["name"] = course_name
        university["degree_level_id"] = degree_level_id
        university["min_fee"] = fees
        university["max_fee"] = fees
        university["eng_req"] = eng_req
        university["eng_req_info"] = eng_req_info
        university["campus"] = campus
        if duration:
            university["duration"] = re.search(
                r"\d+(\.\d+)?", duration
            ).group()
            university["duration_info"] = duration
        university["course_url"] = response.url

        self.count += 1
        yield university

    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(f"斯威本理工大學, 共有 {self.count} 筆資料\n")
