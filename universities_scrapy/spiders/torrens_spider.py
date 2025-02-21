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
        response = self.url_transfer_to_scrapy_response(response.url)
        course_name = response.css(".hero-banner__course h1::text").get()

        # 特殊處理
        if not course_name:
            return
            # course_name = response.css('h1.field-coursename::text').get()
            # if not course_name:
            #     return

        if (
            any(keyword in course_name for keyword in self.keywords)
            # and sum(course_name.count(keyword) for keyword in self.keywords) == 1
            # and all(exclude_keyword not in course_name for exclude_keyword in self.exclude_keywords)
        ):
            mode = None
            campus = None
            duration_info = None
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
                    student_roles = [role.strip() for role in student_roles if role.strip()]
                    if "International" not in student_roles:
                        return
                elif "Campus" in label:
                    campus = info.css(".course-card-panel__value::text").get().strip()
                    if "Online" == campus:
                        return
                    campus = campus.replace(", Online", "")
                elif "duration" in label:
                    duration_info = info.css(".course-card-panel__value .field-value::text").get().strip()
                    
            print(course_name)
            print(response.url)
            print(duration_info)
            print(campus)
            print("\n")

    def url_transfer_to_scrapy_response(self, url):
        response = self.scraper.get(url)
        scrapy_response = HtmlResponse(
            url=url,
            body=response.text,
            encoding="utf-8",
        )
        return scrapy_response

        # 把資料存入 university Item
        # university = UniversityScrapyItem()
        # university["university_id"] = 27
        # university["name"] = course_name
        # university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
        # university["min_fee"] = fees
        # university["max_fee"] = fees
        # university["eng_req"] = re.search(r"\d+(\.\d+)?", eng_req_info).group()
        # university["eng_req_info"] = eng_req_info
        # university["campus"] = campus
        # university["duration"] = duration
        # university["duration_info"] = duration_info
        # university["course_url"] = response.url

    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        # print(f"澳洲托倫斯大學, 共有 {len(self.courses) - self.exclude_count} 筆資料(已排除)")
        # print(f"排除 {self.exclude_count} 筆資料")
        print("\n")
