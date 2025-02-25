import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
from urllib.parse import urlparse
import re


class EcuSpiderSpider(scrapy.Spider):
    name = "ecu_spider"
    allowed_domains = ["www.ecu.edu.au", "myfees.ecu.edu.au"]
    start_urls = [
        "https://www.ecu.edu.au/degrees/postgraduate",
        "https://www.ecu.edu.au/degrees/undergraduate",
    ]
    not_found_list = []
    course_cards = []

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", "#coursesYouCanStudyHere")
                    ],
                ),
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        buttons = await page.query_selector_all("button.accordion-title")
        for button in buttons:
            await button.click()
        updated_page = scrapy.Selector(text=await page.content())
        await page.close()
        cards = updated_page.css(".info-card")
        # 篩選包含 'Bachelor of' 的卡片
        titles = set()
        keywords = ["Bachelor of", "Master of"]
        exclude_keywords = ["/", "Honours", "Honors", "Online"]
        for card in cards:
            title = card.css("a h3.heading-xxs::text").get()
            if (
                title
                and any(keyword in title for keyword in keywords)
                and all(keyword not in title for keyword in exclude_keywords)
                and title not in titles
            ):
                self.course_cards.append(card)
                titles.add(title)

        # 提取card裡面的url
        for course_card in self.course_cards:
            course_url = course_card.css("a::attr(href)").get()

            # 進入課程頁面
            yield scrapy.Request(course_url, callback=self.parse_course_detail)

    def parse_course_detail(self, response):
        # print(f"=============== {response.url}")
        if response.css("#feesScholarshipsInt").get():
            # 取得課程名稱
            course_name = response.css("h1.heading-l::text").get().strip()
            # print(f"課程名稱: {course_name}")
            # 取得學費
            tuition_fee_raw = response.css(
                "#feesScholarshipsInt ul li strong::text"
            ).get()
            tuition_fee = (
                re.search(r"\d+(?:,\d+)*", tuition_fee_raw).group(0).replace(",", "")
            )
            # print(f"學費: {tuition_fee}")
            # 英文門檻
            english_requirement = ""

            # 先找內文
            requirement_first_content = response.css(
                "#accordion__englishInt p::text"
            ).get()
            if requirement_first_content and "IELTS" in requirement_first_content:
                ielts_match = re.search(
                    r"IELTS Academic.*?of (\d+\.\d+)", requirement_first_content
                )
                if ielts_match:
                    ielts_score = ielts_match.group(1)
                    english_requirement = f"IELTS Academic: {ielts_score}"
            # 再找列表
            else:
                requirement_list = response.css("#accordion__englishInt ul li")
                for requirement in requirement_list:
                    row_text = requirement.css("::text").get()
                    if "IELTS" in row_text:
                        ielts_raw = row_text
                        ielts_match = re.search(
                            r"(IELTS Academic).*?(\d+\.\d+)", ielts_raw
                        )
                        if ielts_match:
                            ielts_type = ielts_match.group(1)
                            ielts_score = ielts_match.group(2)
                            english_requirement = f"{ielts_type}: {ielts_score}"
            # print(f"英文門檻: {english_requirement}")
            # 取得校區
            location_list = []
            location_infos = response.css(
                ".info-table.info-table-availability tbody tr"
            )
            for location_info in location_infos:
                location_name = location_info.css("th::text").get().strip()

                # 檢查 semester1 和 semester2 是否包含其他元素
                if (
                    location_info.css("td:nth-of-type(1) span *").get()
                    or location_info.css("td:nth-of-type(2) span *").get()
                ):
                    if (
                        location_name not in location_list
                        and "Online" not in location_name
                    ):
                        location_list.append(location_name)
            

            # 列表轉字串
            location = ", ".join(location_list)
            if location == "":
                return
            
            # print(f"校區: {location}")
            duration = response.css('h3:contains("Duration") + p::text').re_first(
                r"(\d+\s+years?\s+full-?time)"
            )
            if duration:
                duration = duration.replace("full-time", "").strip()
            # print(f"學制: {duration}\n")

            # 把資料存入 university Item
            university = UniversityScrapyItem()
            university["university_id"] = 40
            university["degree_level_id"] = (
                1
                if "Bachelor of" in course_name
                else 2 if "Master of" in course_name else None
            )
            university["name"] = course_name
            university["min_fee"] = tuition_fee
            university["max_fee"] = tuition_fee
            university["campus"] = location
            if english_requirement:
                university["eng_req"] = (
                    re.search(r"\d+(\.\d+)?", english_requirement).group()
                    if english_requirement and re.search(r"\d+(\.\d+)?", english_requirement)
                    else None
                )
                university["eng_req_info"] = english_requirement
            if duration:
                university["duration"] = (
                    re.search(r"\d+(\.\d+)?", duration).group()
                    if re.search(r"\d+(\.\d+)?", duration)
                    else None
                )
                university["duration_info"] = duration + ' year' if duration == '1' else duration + ' years'
            university["course_url"] = response.url

            yield university

        else:
            course_name = response.css("h1.heading-l::text").get().strip()
            location_raw = (
                response.css(".event-details span:nth-of-type(2)::text").get().strip()
                if response.css(".event-details span:nth-of-type(2)::text").get()
                else None
            )
            location = (
                location_raw.replace("Venue:", "").strip().split()[0]
                + " "
                + location_raw.replace("Venue:", "").strip().split()[1]
            )

            # print(f'{course_name}\n{response.url}\n找不到學費資訊可能代表該課程不支持國際生\n')

            course = {}
            course["course_name"] = course_name
            course["course_url"] = response.url
            course["campus"] = location
            self.not_found_list.append(course)

    def closed(self, reason):
        print(f"{self.name}爬蟲完成!")
        print(
            f"伊迪斯科文大學, 共有 {len(self.course_cards) - len(self.not_found_list)} 筆資料(已排除不支援國際生)"
        )
        print(f"不支援國際生的共{len(self.not_found_list)}個\n")
