import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
from urllib.parse import urlparse
import re


class NewcastleSpiderSpider(scrapy.Spider):
    name = "newcastle_spider"
    allowed_domains = ["www.newcastle.edu.au", "handbook.newcastle.edu.au"]
    start_urls = [
        "https://www.newcastle.edu.au/degrees#filter=level_undergraduate,award_master,intake_international"
    ]
    courses = []
    except_count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=dict(
                    playwright=True,
                ),
            )

    def parse(self, response):
        rows = response.css('.uon-filtron-row.uon-card:not([style*="display: none;"])')
        keywords = ["Bachelor of", "Master of"]
        exclude_keywords = ["(pre", "(Honours", "(Advanced"]

        for row in rows:
            course_name = row.css(".degree-title a.degree-link::text").get()
            course_url = row.css(".degree-title a.degree-link::attr(href)").get()
            course = {"name": course_name, "url": course_url}
            if any(course_name.count(keyword) == 1 for keyword in keywords) and all(
                except_keyword not in course_name for except_keyword in exclude_keywords
            ):
                self.courses.append(course)

        # print(f'Found {len(self.courses)} courses')

        for course in self.courses:
            course_url = response.urljoin(course["url"])
            parsed_url = urlparse(course_url)
            domain = parsed_url.netloc
            if domain == "www.newcastle.edu.au":
                yield scrapy.Request(
                    course_url,
                    callback=self.parse_course_page,
                    meta=dict(
                        course_name=course["name"],
                        playwright=True,
                        playwright_include_page=True,
                    ),
                )
            elif domain == "handbook.newcastle.edu.au":
                yield scrapy.Request(
                    course_url,
                    callback=self.parse_handbook_course_page,
                    meta=dict(
                        course_name=course["name"],
                        playwright=True,
                    ),
                )

    async def parse_course_page(self, response):
        page = response.meta["playwright_page"]
        modal = response.css("#uon-preference-popup-overlay.open")
        if modal:
            await page.click('label[for="degree-popup-intake-international"]')
            await page.click("#uon-preference-save")
        course_page = scrapy.Selector(text=await page.content())
        await page.close()
        # 課程名稱
        course_name = response.meta["course_name"]
        # 抓取學費
        tuition_fee_raw = course_page.css(".bf.degree-international-fee::text").get()
        if tuition_fee_raw is None:
            # print(f'{course_name}\n{response.url}\n此課程目前不開放申請\n')
            self.except_count += 1
            return
        tuition_fee = (
            tuition_fee_raw.replace("AUD", "").replace(",", "").strip()
            if tuition_fee_raw
            else None
        )
        # 抓取學制
        duration = course_page.css(".bf.degree-full-time-duration::text").get()
        # 抓取英文門檻
        overall_min_value = course_page.css(
            ".admission-info-mid .ELROverallMinValue::text"
        ).get()
        subtest_min_value = course_page.css(
            ".admission-info-mid .ELRSubTestMinValue::text"
        ).get()
        eng_req = f"IELTS {overall_min_value} (單科不得低於{subtest_min_value})"
        # 抓取地區
        location_list = course_page.css(
            "#degree-location-toggles .uon-option-toggle label::text"
        ).getall()
        location = ", ".join(location_list)

        # print(course_name)
        # print(response.url)
        # print(tuition_fee)
        # print(duration)
        # print(eng_req)
        # print(location, '\n')

        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_id"] = 8
        university["name"] = course_name
        university["degree_level_id"] = (
            1
            if "Bachelor of" in course_name
            else 2 if "Master of" in course_name else None
        )
        university["course_url"] = response.url
        university["min_fee"] = tuition_fee
        university["max_fee"] = tuition_fee
        university["eng_req"] = overall_min_value
        university["eng_req_info"] = eng_req
        university["duration"] = re.search(r"\d+(\.\d+)?", duration).group()
        university["duration_info"] = duration
        university["campus"] = location
        yield university

    def parse_handbook_course_page(self, response):
        main = response.css("#flex-around-rhs .main-content")
        aside = response.css(
            '#flex-around-rhs aside div[data-testid="attributes-table"]'
        )

        # 課程名稱
        course_name = response.meta["course_name"]

        # 學制
        duration = aside.css(":nth-child(7) div>div:nth-of-type(1)::text").get()

        # 地區
        campus = aside.css(":nth-child(11) div>div:nth-of-type(1)::text").get()

        # 英文門檻
        eng_req = main.css('div[id*="Overall minimum"] div div div::text').get()

        # print(course_name)
        # print(response.url)
        # print(duration)
        # print(eng_req)
        # print(campus, '\n')

        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_id"] = 8
        university["name"] = course_name
        university["degree_level_id"] = (
            1
            if "Bachelor of" in course_name
            else 2 if "Master of" in course_name else None
        )
        university["course_url"] = response.url
        university["min_fee"] = None
        university["max_fee"] = None
        university["fee_detail_url"] = (
            "https://www.newcastle.edu.au/current-students/study-essentials/fees-scholarships"
        )
        university["eng_req"] = eng_req
        university["eng_req_info"] = "IELTS " + eng_req
        university["duration"] = duration
        university["duration_info"] = duration
        university["campus"] = campus
        yield university

    def closed(self, reason):
        print(f"{self.name}爬蟲完成!")
        print(
            f"紐卡索大學，共有 {len(self.courses) - self.except_count} 筆資料(已扣除不開放申請)"
        )
        print(f"有 {self.except_count} 筆目前不開放申請\n")
