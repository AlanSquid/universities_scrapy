import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import json
import re
from urllib.parse import urlencode


class UnimelbSpiderSpider(scrapy.Spider):
    name = "unimelb_spider"
    allowed_domains = [
        "www.unimelb.edu.au",
        "study.unimelb.edu.au",
        "uom-search.squiz.cloud",
    ]
    # start_urls = [
    #     "https://study.unimelb.edu.au/find/?collection=find-a-course&profile=_default&query=%21showall&num_ranks=12&start_rank=1&f.Tabs%7CtypeCourse=Courses&f.Study+mode%7CcourseStudyMode=in+person&f.Study+level%7CcourseStudyLevel=undergraduate",
    # ]

    start_urls = ["https://uom-search.squiz.cloud/s/search.json"]
    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = ["/", "Honours", "Online", "Diploma"]
    course_detail_urls = []
    course_count = 0
    headers = {"Content-Type": "application/json"}
    payload = {
        "collection": "find-a-course",
        "profile": "_default",
        "query": "!showall",
        "num_ranks": 500,
        "start_rank": 1,
        "f.Tabs|typeCourse": " Courses",
        "f.Study mode|courseStudyMode": "in person",
        "f.Study level|courseStudyLevel": "undergraduate",
        # "f.Study level|courseStudyLevel": "graduate coursework",
    }
    req_count = 0

    def start_requests(self):

        for url in self.start_urls:
            query_string = urlencode(self.payload)
            full_url = f"{url}?{query_string}"
            yield scrapy.Request(
                full_url,
                headers=self.headers,
                method="GET",
                callback=self.parse_api_response,
            )

    def parse_api_response(self, response):
        data = response.json()
        results = data["response"]["resultPacket"]["results"]
        for result in results:
            # 跳過只開放本地生
            is_domestic_only = "true" in result.get("listMetadata", []).get("courseDomesticOnly", False)[0]
            if is_domestic_only:
                continue
            
            # 課程名稱
            course_name = result.get("metaData", {}).get("courseDisplayTitle")

            if any(keyword in course_name for keyword in self.keywords) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):  
                # 課程連結
                course_url = result.get("liveUrl")
                
                # 學費
                fees = result.get("metaData", {}).get("courseFeesInternational")
                if fees:
                    fees = (
                        fees.replace("AUD ", "")
                        .replace("$", "")
                        .replace(",", "")
                        .replace(" (2025 indicative first year fee)", "")
                    )
                    if "-" in fees:
                        min_fee, max_fee = fees.split("-")
                    else:
                        min_fee = fees
                        max_fee = fees
                else:
                    min_fee = None
                    max_fee = None

                # 學區
                campus = result.get("metaData", {}).get("courseDeliveryInternational")
                if campus:
                    campus_match = re.search(r"\((.*?)\)", campus)
                    if campus_match:
                        campus = campus_match.group(1)
                        
                # 學期制
                duration_info = result.get("metaData", {}).get(
                    "courseDurationInternational"
                )
                if duration_info:
                    pattern = r" / \d+ years part time"
                    match = re.search(pattern, duration_info)
                    if match:
                        duration_info = match.group()
                    # 處理 duration_info
                    duration_info = self.convert_duration_to_years(duration_info)
                    duration = re.search(r"\d+(\.\d+)?", duration_info).group()
                else:
                    continue
                
                # 英文門檻
                eng_req_info = (
                    result.get("metaData", {})
                    .get("courseEngReqs", "")
                    .replace("<br>", "")
                )
                
                if not eng_req_info:
                    if course_name == "Master of Business Administration":
                        eng_req_info = "Academic English test with a minimum score of 7.0 overall and with no individual band less than 6.5"
                    elif course_name == "Master of Psychiatry" or course_name == "Master of Business Analytics":
                        eng_req_info = "Academic English test with a minimum score of 7.0 overall and with no individual band less than 7.0"

                eng_req_match = re.search(r"\d+(\.\d+)?", eng_req_info)
                if eng_req_match:
                    eng_req = eng_req_match.group()
                else:
                    eng_req = None

                # print(course_name)
                # print(course_url)
                # print(min_fee)
                # print(max_fee)
                # print(eng_req_info)
                # print(campus)
                # print(duration_info)
                # print("\n")

                
                # 把資料存入 university Item
                university = UniversityScrapyItem()
                university["university_name"] = "University of Melbourne"
                university["name"] = course_name
                university["degree_level_id"] = 1 if "Bachelor" in course_name else 2
                university["min_fee"] = min_fee
                university["max_fee"] = max_fee
                university["eng_req"] = eng_req
                university["eng_req_info"] = eng_req_info
                university["campus"] = campus
                university["duration"] = duration
                university["duration_info"] = duration_info
                university["course_url"] = course_url

                self.course_count += 1
                yield university

        if self.req_count == 0:
            for url in self.start_urls:
                self.payload["f.Study level|courseStudyLevel"] = "graduate coursework"
                query_string = urlencode(self.payload)
                full_url = f"{url}?{query_string}"
                yield scrapy.Request(
                    full_url,
                    headers=self.headers,
                    method="GET",
                    callback=self.parse_api_response,
                )
            self.req_count += 1

    def convert_duration_to_years(self, duration_info):
        pattern = r"(\d+(\.\d+)?)\s*(year|years|month|months)"
        match = re.search(pattern, duration_info, re.IGNORECASE)
        if match:
            duration_value = float(match.group(1))
            duration_unit = match.group(3).lower()

            if duration_unit in ["month", "months"]:
                duration_value /= 12
                duration_value = round(duration_value, 2)  # 確保浮點數精度

            return (
                f"{duration_value} year"
                if duration_value == 1
                else f"{duration_value} years"
            )
        return duration_info

    def closed(self, reason):
        print(f"{self.name}爬蟲完成!")
        print(f"墨爾本大學, 共有 {self.course_count } 筆資料")
