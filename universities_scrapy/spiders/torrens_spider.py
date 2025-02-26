import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re
import cloudscraper
from scrapy.http import HtmlResponse


class TorrensSpiderSpider(scrapy.Spider):
    name = "torrens_spider"
    allowed_domains = ["www.torrens.edu.au"]
    start_urls = [
        "https://www.torrens.edu.au//sxa/search/results/?s={17C98AA6-04B6-450B-9765-8BF45ABD465B}&itemid={FCA1B352-C90A-40AF-914E-2A5385A9BF1D}&sig=&autoFireSearch=true&study%20level%20grouped=Undergraduate%7C%7CPostgraduate&study%20method=On%20campus%7C%7CBlended&v=%7B746C2D27-34EE-4644-AFE3-5F481179A4B0%7D&p=10&e=0"
    ]
    custom_settings = {
        "HTTPERROR_ALLOWED_CODES": [403],
    }
    keywords = ["Bachelor of", "Master of"]
    # exclude_keywords = [
    #     "(Honours)",
    #     "/",
    # ]
    course_count = 0
    scraper = cloudscraper.create_scraper()

    def parse(self, response):
        response = self.scraper.get(response.url)
        json_data = response.json()
        data_count = json_data["Count"]
        results_count = len(json_data["Results"])
        # 先取得總數量，如果總數大於12，修改size並重新發送請求
        if data_count > results_count:
            new_url = self.start_urls[0].replace("p=10&e=0", f"p={data_count}&e=0")
            yield scrapy.Request(new_url, self.parse)
        else:
            all_course = json_data["Results"]
            for course in all_course:
                url = course["Url"]
                course_url = f"https://www.torrens.edu.au{url}"
                yield scrapy.Request(course_url, self.parse_course)

    def parse_course(self, response):
        course_name = None
        eng_req = None
        eng_req_info = None
        campus = None
        duration = None
        duration_info = None
        fees = None
        
        response = self.url_transfer_to_scrapy_response(response.url)
        
        # 課程名稱
        course_name = response.css(".hero-banner__course h1::text").get()
        
        # 特殊處理
        if not course_name:
            course_name = response.css("h1.field-coursename::text").get()
            if not course_name:
                return

            course_name = course_name.strip()
            info = response.css(".course-summary__course-card-box")
            # 學區
            campus = info.css(
                ".course-card__campus-locations .course-card__value span::text"
            ).get()
            # 學期制
            duration_info_text = info.css(
                ".course-card__duration .course-card__value::text"
            ).get()
            pattern = r".*(full[-\s]*time)"
            match = re.search(pattern, duration_info_text)
            if match:
                duration_info = match.group(0)
                duration = re.search(r"\d+(\.\d+)?", duration_info).group()
            # 英文門檻
            eng_req_info = response.css(
                "//div[1]/main/div/div/div[2]/div[2]/div/div/div[2]/div/div/div[3]/div/div/div/div/div/div/div[2]/div/div/div/div/div[3]/div/div[2]/div[2]/div/div[3]/div/div/div[3]/div/div/div[2]/div/div[2]/text()"
            ).get()
            eng_req = re.search(r"\d+(\.\d+)?", eng_req_info).group()

            # 把資料存入 university Item
            university = UniversityScrapyItem()
            university["university_name"] = "Torrens University Australia"
            university["name"] = course_name
            university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
            university["min_fee"] = fees
            university["max_fee"] = fees
            university["eng_req"] = eng_req
            university["eng_req_info"] = eng_req_info
            university["campus"] = campus
            university["duration"] = duration
            university["duration_info"] = duration_info
            university["course_url"] = response.url
            self.course_count += 1
            yield university

        else:
            course_name = course_name.strip()
            if (
                any(keyword in course_name for keyword in self.keywords)
                and sum(course_name.count(keyword) for keyword in self.keywords) == 1
            ):
                mode = None

                # 學費
                fees = self.lookup_fee_by_course_name(course_name)

                info_elements = response.css(
                    ".component.course-card-panel .component-content .course-card-panel__item"
                )
                for info in info_elements:
                    label = info.css(".course-card-panel__label::text").get().strip()
                    if "Study mode" in label:
                        mode = info.css(".course-card-panel__value::text").get().strip()
                        if "Online" == mode:
                            return
                    elif "Student" in label:
                        student_roles = info.css(
                            ".course-card-panel__value .field-value::text"
                        ).getall()
                        student_roles = [
                            role.strip() for role in student_roles if role.strip()
                        ]
                        if "International" not in student_roles:
                            return
                    # 學區
                    elif "Campus" in label:
                        campus = (
                            info.css(".course-card-panel__value::text").get().strip()
                        )
                        if "Online" == campus:
                            return
                        campus = campus.replace(", Online", "")
                    # 學期制
                    elif "duration" in label:
                        duration_info_text = (
                            info.css(".course-card-panel__value::text").get().strip()
                        )
                        pattern = r".*(full[-\s]*time)"
                        match = re.search(pattern, duration_info_text)
                        if match:
                            duration_info = match.group(0)
                            duration = re.search(r"\d+(\.\d+)?", duration_info).group()
                        else:
                            pattern = pattern = r"Full[-\s]*time:\s*\d+\s*year"
                            match = re.search(pattern, duration_info_text)
                            if match:
                                duration_info = match.group(0)
                                duration = re.search(
                                    r"\d+(\.\d+)?", duration_info
                                ).group()

                # 英文門檻
                ielts_text = response.xpath(
                    '//div[contains(@class, "admission-criteria")]//div[contains(@class, "admission-criteria__item")][contains(., "IELTS")]//text()'
                ).getall()
                if ielts_text:
                    eng_req_info = "".join(ielts_text).strip()
                    eng_req_info = re.split(r";", eng_req_info)[0]  # 取 `;` 前的部分

                    match = re.search(r"IELTS.*?(\d+(?:\.\d+)?)", eng_req_info)
                    if match:
                        eng_req = match.group(1)

                # print(course_name)
                # print(response.url)
                # print(eng_req)
                # print(eng_req_info)
                # print(duration)
                # print(duration_info)
                # print(campus)
                # print("\n")

                # 把資料存入 university Item
                university = UniversityScrapyItem()
                university["university_name"] = "Torrens University Australia"
                university["name"] = course_name
                university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
                university["min_fee"] = fees
                university["max_fee"] = fees
                university["eng_req"] = eng_req
                university["eng_req_info"] = eng_req_info
                university["campus"] = campus
                university["duration"] = duration
                university["duration_info"] = duration_info
                university["course_url"] = response.url
                self.course_count += 1
                yield university

    def url_transfer_to_scrapy_response(self, url):
        response = self.scraper.get(url)
        scrapy_response = HtmlResponse(
            url=url,
            body=response.text,
            encoding="utf-8",
        )
        return scrapy_response

    def lookup_fee_by_course_name(self, course_name):
        # fee_detail = "https://cdn.intelligencebank.com/au/share/RyzZ/ZVeZX/dr4yK/original/2025+International+Fee+Schedule"
        fees_list = [
            {"course": "Bachelor of Commerce (Accounting)", "fees": 29800},
            {"course": "Bachelor of Business", "fees": 29800},
            {"course": "Bachelor of Business Information Systems", "fees": 29800},
            {"course": "Bachelor of Business (Entrepreneurship)", "fees": 29800},
            {"course": "Bachelor of Business (Event Management)", "fees": 28980},
            {
                "course": "Bachelor of Business (Hospitality and Tourism Management)",
                "fees": 28980,
            },
            {"course": "Bachelor of Business (Marketing)", "fees": 29800},
            {"course": "Bachelor of Business (Sport Management)", "fees": 29800},
            {"course": "Master of Professional Accounting", "fees": 33900},
            {"course": "Master of Professional Accounting (Advanced)", "fees": 33900},
            {"course": "Master of Business Administration", "fees": 33900},
            {"course": "Master of Business Administration (Advanced)", "fees": 33900},
            {
                "course": "Master of Business Administration & Master of Global Project Management",
                "fees": 33900,
            },
            {"course": "Master of Business Analytics", "fees": 33900},
            {"course": "Master of Business Analytics (Advanced)", "fees": 33900},
            {"course": "Master of Business Information Systems", "fees": 33900},
            {"course": "Master of Engineering Management", "fees": 33900},
            {
                "course": "Graduate Certificate of Global Project Management",
                "fees": 16950,
            },
            {"course": "Master of Global Project Management", "fees": 33900},
            {"course": "Master of Global Project Management (Advanced)", "fees": 33900},
            {
                "course": "Master of Business Administration & Master of Global Project Management",
                "fees": 33900,
            },
            {
                "course": "Master of Business Administration (Sport Management) (Advanced)",
                "fees": 39150,
            },
            {"course": "Bachelor of Communication Design", "fees": 35400},
            {"course": "Bachelor of Branded Fashion Design", "fees": 35400},
            {"course": "Bachelor of Fashion Marketing and Enterprise", "fees": 35400},
            {"course": "Bachelor of Interior Design (Commercial)", "fees": 35400},
            {"course": "Bachelor of Interior Design (Residential)", "fees": 35400},
            {"course": "Bachelor of Architectural Technology", "fees": 35400},
            {"course": "Bachelor of 3D Design and Animation", "fees": 35400},
            {"course": "Master of Design", "fees": 33800},
            {"course": "Bachelor of Information Technology", "fees": 29800},
            {"course": "Bachelor of Cybersecurity", "fees": 35400},
            {"course": "Master of Cybersecurity", "fees": 37800},
            {
                "course": "Bachelor of Software Engineering (Artificial Intelligence)",
                "fees": 35400,
            },
            {
                "course": "Master of Software Engineering (Artificial Intelligence, Advanced)",
                "fees": 37800,
            },
            {"course": "Bachelor of Performing Arts (Stage and Screen)", "fees": 32450},
            {"course": "Bachelor of Nursing", "fees": 33300},
            {"course": "Master of Public Health", "fees": 30000},
            {"course": "Master of Public Health (Advanced)", "fees": 30000},
            {"course": "Master of Education (Advanced)", "fees": 26500},
            {
                "course": "Master of Education (Leadership and Innovation)",
                "fees": 26500,
            },
            {"course": "Master of Education (Inclusive Literacies)", "fees": 26500},
            {"course": "Master of Education (Inclusive Education)", "fees": 26500},
            {"course": "Master of International Hotel Management", "fees": 32250},
            {"course": "Master of Information Technology", "fees": 33900},
            {"course": "Master of Information Technology (Advanced)", "fees": 33900},
            {"course": "Master of Cybersecurity", "fees": 37800},
            {"course": "Master of Cybersecurity (Advanced)", "fees": 37800},
            {"course": "Bachelor of Health Science", "fees": 31500},
            {"course": "Bachelor of Health Science (Aesthetics)", "fees": 31500},
            {"course": "Bachelor of Health Science (Chinese Medicine)", "fees": 27650},
            {"course": "Bachelor of Health Science (Naturopathy)", "fees": 27650},
            {
                "course": "Bachelor of Health Science (Clinical Nutrition)",
                "fees": 27650,
            },
            {
                "course": "Bachelor of Health Science (Western Herbal Medicine)",
                "fees": 27650,
            },
            {
                "course": "Bachelor of Health Science (Clinical Myotherapy)",
                "fees": 27650,
            },
            {"course": "Bachelor of Game Design and Development", "fees": 35400},
            {"course": "Bachelor of Community Services", "fees": 27650},
        ]

        for detail in fees_list:
            if course_name in detail["course"]:
                return detail["fees"]
        return None

    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!\n")
        print(f"澳洲托倫斯大學, 共有 {self.course_count} 筆資料\n")
