import scrapy
import json
from universities_scrapy.items import UniversityScrapyItem  
from scrapy_playwright.page import PageMethod
import re


class CanberraSpiderSpider(scrapy.Spider):
    name = "canberra_spider"
    allowed_domains = ["www.canberra.edu.au"]
    start_urls = "https://www.canberra.edu.au/services/ws/search/course/all.json"
    all_course_url=[]
    def start_requests(self):
        payload = {
            "filters": {
                "cohort_category": ["Undergraduate"],
            }
        }
        yield scrapy.Request(
            self.start_urls,
            method="POST",
            body=json.dumps(payload),
            callback=self.parse_api_response
        )

    def parse_api_response(self, response):
        data = response.json()
        for item in data['data']['results']:
            course_name = item['title']
            if "Bachelor" in course_name: 
                if 2025 in item['admission_years']:
                     course_url = f'https://www.canberra.edu.au{item['external_url']}'
                     self.all_course_url.append(course_url)
                     yield scrapy.Request(course_url, callback=self.page_parse, meta=dict(
                        playwright = True,
                        playwright_page_methods=[
                            PageMethod('click','button#tab-272896911944500-item-1')
                        ]
                    ))

    def page_parse(self, response):
        course_name = response.css('h1.text-white::text').get()
        if course_name:
            course_name = course_name.strip()
            course_name = re.sub(r'\(.*?\)', '', course_name).strip()
        else:
            course_name = None

        tuition_fee_info = response.css('.international-fee-value').get()
        if tuition_fee_info:
            match = re.search(r'<b>2025</b> : \$([\d,]+)', tuition_fee_info)
            if match:
                tuition_fee = match.group(1).replace(',', '')  # 去掉逗號，取得數字部分
            else:
                tuition_fee = None
        else:
            tuition_fee = None

        table_info = response.css('#tab-272896911944500-item-1-content table')
        # 去除空白標題，過濾掉空白字符
        headers = table_info.css('table#custom-table-css thead th::text').getall()
        headers = [header.strip() for header in headers if header.strip()]
        location = None
        duration = None
        if 'Location' in headers:
            location_th_index = headers.index('Location')
            location = table_info.css(f'table#custom-table-css tbody tr td:nth-child({location_th_index + 1})::text').get()
            if location:
                location = location.strip()

        if 'Duration' in headers:
            duration_th_index = headers.index('Duration')
            duration = table_info.css(f'table#custom-table-css tbody tr td:nth-child({duration_th_index + 1})::text').get()
            if duration:
                duration = duration.strip()

        language_modal = response.css('#languageRequirementsModalInternational div.modal-content.p-4 div.mb-2 p::text').getall()
        english = self.english_requirement(language_modal)

        university = UniversityScrapyItem()
        university['name'] = 'University of Canberra'
        university['ch_name'] = '坎培拉大學'
        university['course_name'] = course_name  
        university['min_tuition_fee'] = tuition_fee
        university['english_requirement'] = english
        university['location'] = location
        university['duration'] = duration
        university['course_url'] = response.url

        yield university


    def english_requirement(self, language_modal):
        english_requirement = None
        if len(language_modal) == 1:
            ielts_paragraph = language_modal[0]
        elif len(language_modal) == 3: #Bachelor of Midwifery為了這個課程寫的例外
            ielts_paragraph = language_modal[1]
        elif len(language_modal) == 4: #Bachelor of Nursing為了這個課程寫的例外
            ielts_paragraph = language_modal[2]
        if ielts_paragraph:
            # 標準 IELTS 要求模式
            ielts_pattern = r'IELTS\s*Academic?\s*score\s*of\s*(\d+(\.\d+)?)\s*overall.*?(?:,?\s*with\s*no\s*band\s*score\s*below\s*(\d+(\.\d+)?))?'
            match = re.search(ielts_pattern, ielts_paragraph)
            
            if match:
                score = match.group(1)  
                band_score = match.group(3) 
                additional_conditions = re.search(r'with\s*(.*?)(?:\s*and\s*no\s*band\s*score\s*below|\.)', ielts_paragraph)
                additional_conditions = additional_conditions.group(1).strip() if additional_conditions else ""

                # 如果有 band score 限制，則加入條件
                if band_score:
                    english_requirement = f"IELTS {score} (單項不低於 {band_score.strip()})"
                else:
                    english_requirement = f"IELTS {score} ({additional_conditions})"
            else:
                non_standard_pattern = (
                    r'overall IELTS Academic score \(or equivalent\) of (\d+(\.\d+)?).*?'
                    r'(?:a score of not less than (\d+(\.\d+)) in both (speaking and listening|reading and writing),).*?'
                    r'no band score below (\d+(\.\d+)?)'
                )
                match = re.search(non_standard_pattern, ielts_paragraph)
                if match:
                    overall_score = match.group(1)  
                    specific_skills_score = match.group(3)
                    skill_types = match.group(5)
                    band_score = match.group(6) 
                    if specific_skills_score and skill_types:
                        skill_translations = {
                            "reading and writing": "閱讀和寫作",
                            "speaking and listening": "口說和聽力"
                        }
                        skill_translation = skill_translations.get(skill_types, skill_types)
                        english_requirement = (
                            f"IELTS {overall_score} ({skill_translation}成績均不低於 {specific_skills_score}，單項不低於 {band_score})"
                        )
                    else:
                        english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"
                else:
                    non_standard_pattern_1 = (
                        r'overall IELTS Academic score \(or equivalent\) of (\d+(\.\d+)?).*?'
                        r'no band score below (\d+(\.\d+)?)'
                    )
                    non_standard_pattern_2 = (
                        r'(?i)overall\s+academic?\s*IELTS\s*score\s*of\s*(\d+(\.\d+)?)\s*.*?'
                        r'no\s*band\s*score\s*below\s*(\d+(\.\d+)?)'
                    )
                    match_2 = re.search(non_standard_pattern_2, ielts_paragraph)
                    match_1 = re.search(non_standard_pattern_1, ielts_paragraph)
                    if match_1:
                        overall_score = match_1.group(1) 
                        band_score = match_1.group(3) 
                        english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"   
                    if match_2:
                        overall_score = match_2.group(1)  
                        band_score = match_2.group(3) 
                        english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"          
        else:
            english_requirement = None
        return english_requirement
    
    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n坎培拉大學，共{len(self.all_course_url)}筆資料\n')