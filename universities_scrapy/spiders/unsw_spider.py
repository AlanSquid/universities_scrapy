import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem
import time
import re
import json

class UnswSpiderSpider(scrapy.Spider):
    name = "unsw_spider"
    allowed_domains = ["www.unsw.edu.au","unsw-search.funnelback.squiz.cloud"]
    # 頁面
    # start_urls = ["https://www.unsw.edu.au/study/find-a-degree-or-course/degree-search-results?international=true&undergraduate=true&postgraduate=true&delivery-mode-campus=true&delivery-mode-online=false&study-mode-full-time=true&study-part-time=false&double=false&single=true&commonwealth=false&sort=title"]
    # API
    start_urls = ["https://unsw-search.funnelback.squiz.cloud/s/search.html?form=json&collection=unsw~unsw-search&profile=degrees&smeta_degreeEligibility=International&smeta_degreeType_or=%22Undergraduate%22+%22Postgraduate%22&smeta_degreeCategory=Single+Degree&smeta_degreeFullTime=true&smeta_degreeDeliveryMode=Face&query=!padrenull&start_rank=1&num_ranks=10&sort=title&gscope1=degree&cool.4=0.3"]
    all_course_url=[]
    start_rank = 1
    num_ranks = 10
    def parse(self, response):
        json_response = response.json()
        total_results = json_response["response"]["resultPacket"]["resultsSummary"]["totalMatching"]
        # 先取得總數量，如果總數大於10，修改size並重新發送請求
        if total_results > json_response["response"]["resultPacket"]["resultsSummary"]["numRanks"]:
            new_url = self.start_urls[0].replace("num_ranks=10", f"num_ranks={total_results}")
            yield scrapy.Request(new_url, self.parse)
        else:
            all_course = json_response["response"]["resultPacket"]["results"]
            for course in all_course:
                title = course["title"]
                skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "AGSM"]
                keywords = ["Bachelor of", "Master of"]
                if not title or any(keyword in title for keyword in skip_keywords) or sum(title.count(keyword) for keyword in keywords) >= 2:
                    # print("跳過:",title)
                    continue
                course_url = course["displayUrl"]
                self.all_course_url.append(course_url)
                yield scrapy.Request(
                    course_url,
                    callback=self.page_parse,
                    meta=dict(
                        playwright=True,
                    ),
                )

    def page_parse(self, response):
        postgraduate_exists = bool(response.css("nav.breadcrumbs-wrapper li.breadcrumb a::text").re("Postgraduate study"))
        undergraduate_exists = bool(response.css("nav.breadcrumbs-wrapper li.breadcrumb a::text").re("Undergraduate"))

        if undergraduate_exists:
            degree_level_id=1
        elif postgraduate_exists:
            degree_level_id=2
        else:
            degree_level_id=None

        course_name = response.css('h1.cmp-degree-detail-hero__title::text').get()
        
        # 取得學費
        tuition_fee = response.css('div.js-cmp-degree-detail-hero-fee-international::text').get()
        fees_section = response.css('div.cmp-degree-detail-hero__col-left__details__col2__list__item')
        tuition_fee = fees_section.css('dt:has(div.cmp-contentfragment__element--internationalAnnual) + dd::text').get()
        if tuition_fee:
            tuition_fee = tuition_fee.replace('$', '').replace(',', '').replace('*', '').strip()

        # 取得區間
        duration_info = response.css('dt:contains("Duration") + dd::text').get().strip()
        pattern = r"(\d+(\.\d+)?)"
        match = re.search(pattern, duration_info)
        if match:
            first_number = match.group(1)
            duration=first_number
        else:
            duration=None
        # 取得校區
        location = response.css('dt:contains("Campus") + dd div::text').get()
        if location == " -":
            location = None
        
        # # 取得英文門檻
        # # 提取 <script> 標籤的內容
        english_requirement = None
        eng_req = None
        script_content = response.css('script:contains("window.engRequirementsConfig")::text').get()
        if script_content:
        # # 提取 JSON 字串部分
            json_start = script_content.find('{')
            json_end = script_content.rfind('}') + 1
            raw_json_data = script_content[json_start:json_end]
            # 將轉義的字符轉為正常的 JSON 格式
            valid_json_data = raw_json_data.encode('utf-8').decode('unicode_escape')
            eng_requirements = json.loads(valid_json_data)
            ielts_requirement = eng_requirements.get('ielts')
            ielts_requirement = ielts_requirement.strip()
            match = re.match(r"(\d+\.\d|\d) overall \(min\.? (.+)\)", ielts_requirement)
            if match:
                overall_score = match.group(1)  # 總分
                subtest_requirements = match.group(2)  # 單科要求描述
                eng_req = overall_score
                # 處理「所有項目分數一致」的情況
                all_subtests_match = re.match(r"(\d+\.\d|\d) in (listening, reading, writing, and speaking|each subtest)", subtest_requirements)
                if all_subtests_match:
                    min_score = all_subtests_match.group(1)
                    english_requirement = f"IELTS {overall_score} overall (min. {min_score} in each subtest)"
                else:
                    reading_writing_match = re.search(r"(\d+\.\d|\d) in writing & reading", subtest_requirements)
                    speaking_listening_match = re.search(r"(\d+\.\d|\d) in speaking & listening", subtest_requirements)

                    if reading_writing_match and speaking_listening_match:
                        reading_writing_min = reading_writing_match.group(1)
                        speaking_listening_min = speaking_listening_match.group(1)
                        english_requirement = f"IELTS {overall_score} overall (min. {reading_writing_min} in writing & reading, {speaking_listening_min} in speaking & listening)"
                    else:
                        english_requirement = f"IELTS {overall_score} (Detailed requirements: {subtest_requirements})"
            # else:
            #     print(f"{course_name}的英文格式不匹配，無法解析。{ielts_requirement}")

        university = UniversityScrapyItem()
        university['university_id'] = 7
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['eng_req'] = eng_req
        university['eng_req_info'] = english_requirement
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        # university['english_requirement_url'] = 'https://www.unsw.edu.au/study/how-to-apply/english-language-requirements'
        yield university
    
    def extract_courses_url(self, course_page):
        cards = course_page.css('h2.cmp-degree-search__results__list__card__content_header a')
        for card in cards:
            title = card.css('::text').get()

            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of"]
            if not title or any(keyword in title for keyword in skip_keywords) or sum(title.count(keyword) for keyword in keywords) >= 2:
                continue
            course_url = card.css('::attr(href)').get()
            self.all_course_url.append(course_url)
        
    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n新南威爾斯大學，共{len(self.all_course_url)}筆資料\n')
