import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re


class CsuSpiderSpider(scrapy.Spider):
    name = "csu_spider"
    allowed_domains = ["www.csu.edu.au", "study.csu.edu.au"]
    start_urls = [
        "https://study.csu.edu.au/courses?course_search_query=&filter_studentType=INT&filter_studyLevel=Undergraduate&filter_studyMode=On+Campus&filter_sessionDate=2025",
        "https://study.csu.edu.au/courses?course_search_query=&filter_studentType=INT&filter_studyLevel=Postgraduate&filter_studyMode=On+Campus&filter_sessionDate=2025",
    ]

    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = ["(Honours)", "/", "with specialisations"]
    courses = []
    exclude_count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    # playwright_page_methods=[
                    #     PageMethod(
                    #         "wait_for_selector",
                    #         '#study-course-finder-results-cards',
                    #         timeout=10000,
                    #     ),
                    # ],
                ),
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        while True:
            show_more_btn = await page.query_selector("#course-finder-show-more")
            if show_more_btn and await show_more_btn.is_visible():
                await show_more_btn.click()
                await page.wait_for_timeout(2000)
            else:
                break
        updated_page = scrapy.Selector(text=await page.content())
        await page.close()

        cards = updated_page.css(
            "#study-course-finder-results-cards .card.course-result-card"
        )
        for card in cards:
            course_name = card.css(".course-result-title a::text").get()

            if any(keyword in course_name for keyword in self.keywords) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):
                link = card.css(".course-result-title a::attr(href)").get()
                international_link = "/international" + link
                course_url = response.urljoin(international_link)
                self.courses.append({"name": course_name, "url": course_url})

        for course in self.courses:
            yield scrapy.Request(
                course["url"],
                self.parse_course,
                meta=dict(playwright=True, course_name=course["name"]),
            )

    def parse_course(self, response):
        # 課程名稱
        course_name = response.meta["course_name"]
        # print(course_name)
        # print(response.url)
        info = response.css("#key-information-content")

        # 學期制
        duration_info = info.css(".populate-duration::text").getall()
        duration_info = ", ".join(duration_info)
        duration = re.search(r"\d+(\.\d+)?", duration_info).group()

        # 學費
        fee_rows = info.css(".populate-indicative-fees p")
        for row in fee_rows:
            fee_info = row.css("::text").getall()
            if "International on campus" in fee_info[0]:
                if "Full-time" in fee_info[2]:
                    fees = (
                        fee_info[2]
                        .replace("Full-time - ", "")
                        .replace("$", "")
                        .replace(",", "")
                        .replace(".00", "")
                        .replace(" pa", "")
                    )
                    break
            else:
                self.exclude_count += 1
                return

        # 學區
        location_info = [
            info.strip()
            for info in info.css(
                ".populate-all-session-and-location-info .session-detail::text"
            ).getall()
            if info.strip()
        ]
        locations = []
        for index, item in enumerate(location_info):
            if "On Campus" in item:
                next_item = location_info[index + 1]
                next_item = next_item.split(", ")
                for location in next_item:
                    if location not in locations:
                        locations.append(location)
        #         if next_item not in location:
        #             location.append(next_item)
        #             print(location)
        campus = ", ".join(locations)

        
        # print(fees)
        # print(duration)
        # print(duration_info)
        # print(campus)
        # print("\n")
        
        undergraduate_req = 'a minimum overall score of 6.0, no individual score below 5.5'
        postgraduate_req = 'a minimum overall score of 6.0, no individual score below 6.0'
        
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_name"] = "Charles Sturt University"
        university["name"] = course_name
        university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
        university["min_fee"] = fees
        university["max_fee"] = fees
        university["eng_req"] = 6.0
        university["eng_req_info"] =  undergraduate_req if "Bachelor" in course_name else postgraduate_req
        university["campus"] = campus
        university["duration"] = duration
        university["duration_info"] = duration_info
        university["course_url"] = response.url
        
        yield university

    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(
            f"查爾斯史都華大學, 共有 {len(self.courses) - self.exclude_count} 筆資料(已排除)"
        )
        print(f"排除 {self.exclude_count} 筆資料\n")
