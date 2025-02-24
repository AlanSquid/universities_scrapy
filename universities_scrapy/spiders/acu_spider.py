import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re
import time


class AcuSpiderSpider(scrapy.Spider):
    name = "acu_spider"
    allowed_domains = ["www.acu.edu.au", "policy.acu.edu.au"]
    start_urls = [
        "https://www.acu.edu.au/study-at-acu/find-a-course/course-search-result?CourseType=Undergraduate",
    ]
    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = ["Honours", "/", "Online"]
    eng_req_dict = {
        "Band A": "Overall score: 6.0; Individual score of 5.5 in all tests",
        "Band B": "Overall score: 6.0; Individual score of: 6.0 in writing and speaking, 5.5 in listening and reading",
        "Band C": "Overall score: 6.5; Individual score of 6.0 in all tests",
        "Band D": "Overall score: 7.0; Individual score of 6.0 in all tests",
        "Band E": "Overall score: 7.0; Individual score of 6.5 in all tests",
        "Band F": "Overall score: 7.0; Individual score of: 7.0 in all tests",
        "Band G": "A minimum of 7.0 in Reading and Writing and a minimum of 7.5 in listening and speaking",
        "Band H": "No score less than 7 in reading and writing. No score less than 8 in listening and speaking",
    }
    courses = []
    count = 0

    def start_requests(self):
        # 先處理 https://policy.acu.edu.au/document/view.php?id=312#major16
        # yield scrapy.Request(
        #     "https://policy.acu.edu.au/document/view.php?id=312#major16",
        #     self.parse_eng_req_page,
        #     meta=dict(
        #         playwright=True,
        #     ),
        #     priority=1,
        # )
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                ),
                priority=0
            )

    def parse_eng_req_page(self, response):
        # title = response.css('h3#major16::text').get()
        table = response.xpath("//div[4]/div/div/div[2]/div[2]/div[2]/table[3]")
        tr_list = table.css("tbody tr")
        for tr in tr_list:
            band_level = tr.css("th div::text").get()
            if band_level is None:
                band_level = tr.css("th::text").get().strip()
                eng_reg_info = tr.css("td:first-of-type::text").get().strip()
            else:
                eng_reg_info = tr.css("td:first-of-type div::text").getall()
                eng_reg_info = ", ".join([info.strip() for info in eng_reg_info]).strip()
                
            band_level = band_level.strip()
            eng_reg_info = eng_reg_info.replace("\xa0", " ")
            eng_reg_info = re.sub(r",\s*,", ",", eng_reg_info)
            eng_reg_info = re.sub(r"(Overall score: \d+(\.\d+)?)(?!;)", r"\1;", eng_reg_info)
            self.eng_req_dict[band_level] = eng_reg_info

        #     print("band_level", band_level)
        #     print("eng_reg_info", eng_reg_info)
        # print("\n")
        # print(self.eng_req_dict)

    async def parse(self, response):
        page = response.meta["playwright_page"]
        # 調整網頁篩選器
        filter = await page.query_selector("section.primary-filter.desktop-width")

        postgraduate_btn = await filter.query_selector(
            'ul.primary-filter__filter-search li a[data-track-label="Postgraduate"]'
        )
        await postgraduate_btn.click()

        full_time_btn = await filter.query_selector('label[for="Full-time"]')
        await full_time_btn.click()

        international_btn = await filter.query_selector('label[for="International"]')
        await international_btn.click()
        time.sleep(3)
        # result_e = await page.query_selector(".col-md-12.loading p")
        # result = await result_e.text_content()

        updated_page = scrapy.Selector(text=await page.content())
        cards = updated_page.css("#courseitem")
        for card in cards:
            course_name = card.css("h5::text").get()

            if any(
                course_name.count(keyword) == 1 for keyword in self.keywords
            ) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):
                link = card.css(
                    ".search-results-scholarships__value input.hdnUrlValue::attr(value)"
                ).get()
                course_url = f"https://www.acu.edu.au{link}/?type=International"

                self.courses.append({"name": course_name, "url": course_url})
                # print("course_name", course_name)
                # print("course_name_format", course_name_format)
                # print("course_url", course_url)
                # print("\n")

        for course in self.courses:
            yield scrapy.Request(
                course["url"], self.parse_course, meta={"origin_name": course["name"]}
            )

    def parse_course(self, response):
        # 課程名稱
        course_name = response.css("h1.banner__image__cta--bg--header__h::text").get()

        # 英文門檻
        eng_req_info = self.compare_eng_req(course_name)

        # 學區
        locations = response.css("select#location option::text").getall()
        if len(locations) == 0:
            return
        campus = ", ".join(locations)

        info = response.css(".filtered-tldr")
        titles = info.css("dl dt")
        for title in titles:
            # 學制
            if "Duration" in title.css("::text").get():
                duration_info = title.xpath("following-sibling::dd[1]/text()").get()
                if not duration_info or duration_info == " ":
                    duration_info = ", ".join(
                        title.xpath("following-sibling::dd[1]/p/text()").getall()
                    )
                duration_info = duration_info.strip()
                duration_info = re.sub(r"(?<!\d)\.(?!\d)", "", duration_info)
                duration_info = duration_info.replace(" or equivalent part-time", "")
                duration = re.search(r"\d+(\.\d+)?", duration_info).group()
            # 學費
            if "Fees" in title.css("::text").get():
                fees = title.xpath("following-sibling::dd[1]/text()").get()
                fees = fees.replace("$", "")

        # print("course_name", course_name)
        # print(response.url)
        # print("fee", fee)
        # print("campus", campus)
        # print("duration", duration)
        # print("duration_info", duration_info)
        # print("\n")

        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_id"] = 3
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

        self.count += 1
        yield university

    def compare_eng_req(self, course_name):
        band_level = None
        G_keywords = [
            "Studies",
            "Primary",
            "Secondary",
            "Early Childhood and Primary",
            "Primary and Secondary",
            "Primary and Special Education",
            "Secondary and Special Education",
        ]
        D_keywords = ["Master of Education", "Master of Educational Leadership"]
        E_keywords = [
            "Laws",
            "Master of Clinical Exercise Physiology",
            "Master of Sports and Exercise Physiotherapy",
            "Master of Rehabilitation",
        ]
        F_keywords = [
            "Psychology",
            "Master of Social Work",
            "Bachelor of Nursing",
            "Bachelor of Occupational Therapy",
            "Bachelor of Physiotherapy",
            "Bachelor of Psychological Science",
            "Bachelor of Social Work",
            "Master of Dietetic Practice",
        ]

        if any(keyword in course_name for keyword in F_keywords):
            band_level = "Band F"
        elif any(keyword in course_name for keyword in E_keywords):
            band_level = "Band E"
        elif "Bachelor of Education" in course_name and any(
            keyword in course_name for keyword in G_keywords
        ):
            band_level = "Band G"
        elif "Bachelor of" in course_name:
            band_level = "Band B"
        elif any(keyword in course_name for keyword in D_keywords):
            band_level = "Band D"
        elif "Master of" in course_name:
            band_level = "Band C"

        return self.eng_req_dict[band_level]

    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(f"澳洲天主教大學, 共有 {self.count} 筆資料\n")
