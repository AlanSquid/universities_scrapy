import scrapy
from universities_scrapy.items import UniversityScrapyItem
import re


class FlindersSpiderSpider(scrapy.Spider):
    name = "flinders_spider"
    allowed_domains = ["www.flinders.edu.au", "flinders.edu.au"]
    start_urls = ["https://www.flinders.edu.au/international"]
    course_count = 0

    def parse(self, response):
        study_areas_urls = (
            response.xpath('//section/div/div[@class="section"][7]')
            .css(".cta-button a::attr(href)")
            .getall()
        )
        for relative_url in study_areas_urls:
            url = response.urljoin(relative_url)
            yield scrapy.Request(url, callback=self.extract_course_url)

    def extract_course_url(self, response):
        courses = []
        bachelor_urls = (
            response.xpath(
                '//div[@class="course_list_component"]//div[@class="accordion_item"][1]'
            )
            .css("ul.course_list li a::attr(href)")
            .getall()
        )
        for url in bachelor_urls:
            courses.append({"degree_id": 1, "url": url})

        master_urls = (
            response.xpath(
                '//div[@class="course_list_component"]//div[@class="accordion_item"][4]'
            )
            .css("ul.course_list li a::attr(href)")
            .getall()
        )

        for url in master_urls:
            if (
                "https://handbook.flinders.edu.au/courses/engineering" not in url
                and "https://handbook.flinders.edu.au/courses/medicine" not in url
            ):
                courses.append({"degree_id": 2, "url": url})
                
        for course in courses:
            yield scrapy.Request(
                url=course["url"],
                callback=(
                    self.parse_bachelor_page
                    if course["degree_id"] == 1
                    else self.parse_master_page
                ),
                meta=dict(
                    playwright=True,
                    degree_id=course["degree_id"],
                ),
            )

    def parse_bachelor_page(self, response):
        # 抓課程名稱
        course_name = response.css("h1.yellow_heading::text").get()
        keywords = ["Bachelor"]
        exclude_keywords = ["(Honours)", "Master of"]

        if not (
            any(course_name.count(keyword) == 1 for keyword in keywords)
            and sum(course_name.count(keyword) for keyword in keywords) == 1
            and all(
                except_keyword not in course_name for except_keyword in exclude_keywords
            )
        ):
            return

        info = response.css(
            ".ff-tab-content.international_content div.col-lg-8.col-md-6:nth-of-type(2) div.col-md-12.col-lg-6:nth-of-type(1)"
        )

        # 抓取地區
        location_list_raw = info.css(
            "div.col-sm-6:nth-of-type(2) ul.content_list li::text"
        ).getall()
        location_list = [l.strip("– ") for l in location_list_raw]
        location = ", ".join(location_list)

        # 抓取學制
        duration = (
            info.css("div.col-sm-6:nth-of-type(3) p.content_detail::text").get().strip()
        )

        # 抓取學費
        tuition_fee_raw = response.css(
            ".ff-tab-content.international_content div.col-lg-8.col-md-6:nth-of-type(2) div.col-md-12.col-lg-6:nth-of-type(2) ul.content_list li::text"
        ).get()
        match = re.search(r"\$(\d{1,3}(?:,\d{3})*)", tuition_fee_raw)
        if match:
            tuition_fee = match.group(1).replace(",", "")

        # 抓取英文門檻
        english_requirement = (
            "IELTS "
            + response.css(
                ".english-reqs.content_container :nth-child(1) .english-reqs__summary .english-reqs__score.english-reqs__score--large::text"
            ).get()
        )

        # print(course_name)
        # print(response.url)
        # print(tuition_fee)
        # print(english_requirement)
        # print(duration)
        # print(location)
        # print('\n')

        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_id"] = 26
        university["name"] = course_name
        university["degree_level_id"] = response.meta["degree_id"]
        university["course_url"] = response.url
        university["min_fee"] = tuition_fee
        university["max_fee"] = tuition_fee
        university["eng_req"] = (
            re.search(r"\d+", english_requirement).group()
            if english_requirement and re.search(r"\d+", english_requirement)
            else None
        )
        university["eng_req_info"] = english_requirement
        university["duration"] = (
            re.search(r"\d+", duration).group() if re.search(r"\d+", duration) else None
        )
        university["duration_info"] = duration
        university["campus"] = location

        self.course_count += 1
        yield university

    def parse_master_page(self, response):
        # print("==========", response.url)
        tuition_fee = None
        duration = None
        duration_info = None
        campus = None
        
        course_sections = response.css(
            ".dom-int-toggle-component.parbase ~ div.section"
        )
        classname_keywords = [
            "black_container",
            "gray_dark_container",
            "gray_darker_container",
            "international_grey_container",
        ]

        target_course_section = []
        for course_section in course_sections:
            first_div_class = course_section.css("div > div::attr(class)").get()
            if any(keyword in first_div_class for keyword in classname_keywords):
                target_course_section = course_section
                break
            if target_course_section != []:
                break
        master_divs = (
            target_course_section.xpath(
                './/div[@id and contains(@class, "cmp-text")][p]'
            )
            if target_course_section != []
            else []
        )
        for div in master_divs:
            course_name = div.css(".text_size_large::text").get()
            if (
                course_name
                and "Master of" in course_name
                and " / " not in course_name
                and "(Research)" not in course_name
            ):
                # 課程名稱
                course_name = course_name.replace("\xa0", " ")

                details = div.css('p')
                if len(div.css('p')) == 1:
                    details = div.xpath('../following-sibling::div[1]/div/p')
                for detail in details:
                    strong_text = detail.css("strong::text").get()
                    second_strong_text = detail.css("strong:nth-of-type(2)::text").get()
                    # 學制
                    if strong_text and "Duration" in strong_text:
                        duration_text = detail.css("::text").getall()
                        duration_str = (
                            "".join(duration_text).replace("\xa0", "").strip()
                        )
                        duration = re.search(r"\d+(\.\d+)?", duration_str).group()
                        duration_info = (
                            (duration + " year")
                            if duration == "1"
                            else (duration + " years")
                        )
                        # print("duration:", duration)
                        # print("duration_info:", duration_info)
                    # 地區
                    elif strong_text and "Location" in strong_text:
                        location_text = detail.css("::text").getall()
                        location_text = [
                            text.strip()
                            for text in location_text
                            if text.strip() and text.strip() != strong_text
                        ]
                        campus = ", ".join(location_text)
                        # print("campus:", campus)
                    # 學費
                    elif strong_text and "fees" in strong_text or (second_strong_text and "fees" in second_strong_text):
                        fee_text = detail.css("::text").getall()
                        fee_text = (
                            "".join(fee_text)
                            .replace(strong_text, "")
                            .replace(",", "")
                            .strip()
                        )
                        match = re.search(r"\$(\d+)", fee_text)
                        if match:
                            tuition_fee = match.group(1)
                            # print("tuition_fee:", tuition_fee)

                # 把資料存入 university Item
                university = UniversityScrapyItem()
                university["university_id"] = 26
                university["name"] = course_name
                university["degree_level_id"] = 2
                university["course_url"] = response.url
                university["min_fee"] = tuition_fee 
                university["max_fee"] = tuition_fee 
                university["eng_req"] = 6.5
                university["eng_req_info"] = "IELTS 6.5"
                university["duration"] = duration
                university["duration_info"] = duration_info
                university["campus"] = campus
                university["eng_req_url"] = 'https://www.flinders.edu.au/international/apply/entry-requirements/english-language-requirements'
                self.course_count += 1
                yield university

    def closed(self, reason):
        print(f"{self.name}爬蟲完成!")
        print(f"弗林德斯大學，共有 {self.course_count} 筆資料\n")
