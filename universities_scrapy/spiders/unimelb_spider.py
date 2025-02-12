import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem
import re


class UnimelbSpiderSpider(scrapy.Spider):
    name = "unimelb_spider"
    allowed_domains = ["www.unimelb.edu.au", "study.unimelb.edu.au"]
    start_urls = [
        "https://study.unimelb.edu.au/find/?collection=find-a-course&profile=_default&query=%21showall&num_ranks=12&start_rank=1&f.Tabs%7CtypeCourse=Courses&f.Study+mode%7CcourseStudyMode=in+person"
    ]
    course_detail_urls = []
    course_count = 0
    no_international_count = 0

    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(
                url=url,
                callback=self.parse,
                wait_time=5,
                wait_until=lambda driver: WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".search-result__card.card.course")
                    )
                ),
            )

    def parse(self, response):
        courses = response.css(".search-result__card.card.course")
        keywords = ["Bachelor of", "Master of"]
        exclude_keywords = ["/", "Honours"]

        for course in courses:
            # 抓取課程名稱
            course_name = course.css(".card-header--wrapper h4::text").get()
            if any(keyword in course_name for keyword in keywords) and all(
                exclude_keyword not in course_name
                for exclude_keyword in exclude_keywords
            ):
                # 抓取課程網址
                course_url = course.css(".card-body a:nth-of-type(1)::attr(href)").get()
                # 將課程網址存入列表
                self.course_detail_urls.append(course_url)

        # 處理換頁
        next_relative_url = response.css(
            "a.page-link.page-link--next::attr(href)"
        ).get()
        if next_relative_url is not None:
            next_url = response.urljoin(next_relative_url)
            # 換頁請求
            yield SeleniumRequest(
                url=next_url,
                callback=self.parse,
                wait_time=5,
                wait_until=EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".search-result__card.card.course")
                ),
            )

        # 沒有下一頁後開始爬取各課程詳細資訊
        else:
            for course_url in self.course_detail_urls:
                driver = response.request.meta["driver"]
                wait = WebDriverWait(driver, 10)
                # print('course_url:', course_url)
                driver.get(course_url)
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".key-facts-section__main")
                    )
                )

                # 居住地要選擇International student
                residency_element = driver.find_elements(
                    By.CSS_SELECTOR, "span.residency--title"
                )
                residency = (
                    residency_element[0].text.strip() if residency_element else None
                )

                # 如果不是International student，則點擊切換按鈕
                if residency and residency != "International student":
                    change_btn = driver.find_element(
                        By.CSS_SELECTOR, "a.btn--toggle.btn--toggle-alt"
                    )
                    driver.execute_script("arguments[0].click();", change_btn)

                # 給scrapy解析頁面
                page = scrapy.Selector(text=driver.page_source)

                # 取得課程名稱
                course_name = page.css("#page-header::text").get().strip()
                # print('course_name:', course_name)
                # 取得學費、學制、英文門檻、校區
                tuition_fee = None
                duration = None
                english_requirement = None
                location = None
                info = page.css(".key-facts-section__main")
                info_items = info.css(".key-facts-section__main--item")
                for item in info_items:
                    title = (
                        item.css(".key-facts-section__main--title::text").get().strip()
                    )
                    if "Fees" in title:
                        tuition_fee_raw = item.css(
                            ".key-facts-section__main--value::text"
                        ).get()
                        tuition_fee = self.extract_fee_range(tuition_fee_raw)
                        # print('tuition_fee:', tuition_fee)
                    if "Duration" in title:
                        duration = item.css(
                            "div.key-facts-section__main--value::text"
                        ).get()
                        full_time_match = re.search(
                            r"(\d+(\.\d+)?)\s*(year|years|months)\s*full time",
                            duration,
                            re.IGNORECASE,
                        )
                        if full_time_match:
                            duration_value = float(full_time_match.group(1))
                            duration_unit = full_time_match.group(3).lower()

                            if duration_unit == "months":
                                duration_value /= 12
                                duration_value = round(
                                    duration_value, 2
                                )  # 確保浮點數精度

                            duration = (
                                f"{duration_value} year"
                                if duration_value == 1
                                else f"{duration_value} years"
                            )

                        # duration = ", ".join([d.strip() for d in duration.split("/")])
                        # duration = re.search(r"\d+(\.\d+)?", duration)
                        # print('duration:', duration)
                    if "English" in title:
                        english_requirement_raw = item.css(
                            ".key-facts-section__main--value::text"
                        ).get()
                        english_requirement = self.extract_ielts_requirement(
                            english_requirement_raw
                        )
                        # print('english_requirement:', english_requirement)
                    if "Location" in title:
                        location_raw = item.css(
                            ".key-facts-section__main--value::text"
                        ).get()
                        match = re.search(r"\((.*?)\)", location_raw)
                        if match:
                            location = match.group(1)
                            # print('location:', location)

                if duration and "part time" in duration.lower():
                    continue

                if tuition_fee:
                    # 把資料存入 university Item
                    university = UniversityScrapyItem()
                    university["university_id"] = 30
                    university["name"] = course_name
                    university["degree_level_id"] = (
                        1
                        if "Bachelor of" in course_name
                        else 2 if "Master of" in course_name else None
                    )
                    university["min_fee"] = tuition_fee[min]
                    university["max_fee"] = (
                        tuition_fee[max] if tuition_fee[max] else tuition_fee[min]
                    )
                    if english_requirement:
                        university["eng_req"] = re.search(
                            r"\d+(\.\d+)?", english_requirement
                        ).group()
                        university["eng_req_info"] = english_requirement
                    university["campus"] = location
                    if duration:
                        university["duration"] = re.search(
                            r"\d+(\.\d+)?", duration
                        ).group()
                        university["duration_info"] = duration
                    university["course_url"] = course_url

                    self.course_count += 1
                    yield university

                # 沒有學費的代表不開放國際生
                else:
                    # print(f'{course_name}不開放國際生\n{course_url}')
                    self.no_international_count += 1

    # 提取學費範圍或單個金額
    def extract_fee_range(self, fee_string):
        # 匹配範圍金額的正則表達式
        range_pattern = re.compile(r"\$([\d,]+)-\$([\d,]+)")
        # 匹配單個金額的正則表達式
        single_pattern = re.compile(r"\$([\d,]+)")

        range_match = range_pattern.search(fee_string)
        if range_match:
            return {
                min: range_match.group(1).replace(",", ""),
                max: range_match.group(2).replace(",", ""),
            }
        single_match = single_pattern.search(fee_string)
        if single_match:
            return {min: single_match.group(1).replace(",", ""), max: None}

        return ""

    # 提取英文門檻(IELTS)
    def extract_ielts_requirement(self, ielts_string):
        if ielts_string is None:
            return "IELTS 6.5"
        # 匹配帶有子分數的正則表達式
        pattern_with_bands = re.compile(
            r"IELTS (\d+(\.\d+)?) with no band(s)? less than (\d+(\.\d+)?)"
        )
        # 匹配没有子分數的正則表達式
        pattern_without_bands = re.compile(r"IELTS (\d+(\.\d+)?)")

        match_with_bands = pattern_with_bands.search(ielts_string)
        if match_with_bands:
            return f"IELTS {match_with_bands.group(1)} (單科不低於{match_with_bands.group(4)})"

        match_without_bands = pattern_without_bands.search(ielts_string)
        if match_without_bands:
            return f"IELTS {match_without_bands.group(1)}"

    def closed(self, reason):
        print(f"{self.name}爬蟲完成!")
        print(
            f"墨爾本大學, 共有 {self.course_count } 筆資料(已排除不支援國際生)"
        )
        print(f"不支援國際生的共{self.no_international_count}個\n")
