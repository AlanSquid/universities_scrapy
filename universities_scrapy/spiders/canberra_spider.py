import scrapy
import json
from universities_scrapy.items import UniversityScrapyItem  
import re

class CanberraSpiderSpider(scrapy.Spider):
    name = "canberra_spider"
    allowed_domains = ["www.canberra.edu.au"]
    start_urls = "https://www.canberra.edu.au/services/ws/search/course/all.json"
    # all_course_url=['https://www.canberra.edu.au/course/364JA/2/2025','https://www.canberra.edu.au/course/HLB001/2/2025','https://www.canberra.edu.au/course/132JA/3/2025','https://www.canberra.edu.au/course/EDM101/1/2025','https://www.canberra.edu.au/course/772AA/6/2025',"https://www.canberra.edu.au/course/SCM501/1/2025"]
    all_course_url=[]
    def start_requests(self):
        payload = {
            "filters": {
                "cohort_category": ["Undergraduate", "Postgraduate"], 
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

            # 跳過 Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor", "Honours", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of"]
            if 2025 in item['admission_years'] and not any(keyword in course_name for keyword in skip_keywords) and sum(course_name.count(keyword) for keyword in keywords) < 2: 
                course_url = f'https://www.canberra.edu.au{item['external_url']}/2025'
                if "Undergraduate" in item['cohort_category'] :
                    degree_level_id=1
                elif "Postgraduate" in item['cohort_category']:
                    degree_level_id=2
                self.all_course_url.append(course_url)
                yield response.follow(course_url, self.page_parse,   meta={'degree_level_id': degree_level_id})
            # for url in self.all_course_url:
            #     yield response.follow(url, self.page_parse,   meta={'degree_level_id': 1})
    
    def page_parse(self, response):
        course_name = response.css('h1.text-white::text').get()
        if course_name:
            course_name = course_name.strip()
            course_name = re.sub(r'\(.*?\)', '', course_name).strip()
        else:
            course_name = None
        
        
        # 取得所有 value="2025" 的 input 標籤
        inputs = response.css('input[value="2025"]')
        # 過濾 id 內含 "year" 的 input
        year_input = next((inp for inp in inputs if "year" in inp.attrib.get('id', '')), None)
        # 檢查是否找到符合條件的 input
        if year_input:
            year_id = year_input.attrib['id']  # 例如：'7-year'
            target_id = year_id.replace("year", "eftsl-international")  # 變成 '7-eftsl-international'
            # 取得對應 input 的 value
            tuition_fee = response.css(f'input#{target_id}::attr(value)').get()
        else:
            tuition_fee = None
       

        table_info = response.css('#tab-272896911944500-item-1-content table')
        # 去除空白標題，過濾掉空白字符
        headers = table_info.css('table#custom-table-css thead th::text').getall()
        headers = [header.strip() for header in headers if header.strip()]
        location = None
        if 'Location' in headers:
            location_th_index = headers.index('Location')
            location = table_info.css(f'table#custom-table-css tbody tr td:nth-child({location_th_index + 1})::text').get()
            if location:
                location = location.strip()
            if location == "":
                location = None
                
        if 'Duration' in headers:
            duration_th_index = headers.index('Duration')
            duration_info = table_info.css(f'table#custom-table-css tbody tr td:nth-child({duration_th_index + 1})::text').get()
            if duration_info:
                duration_info = duration_info.strip()
                match = re.search(r'\d+(\.\d+)?', duration_info)  # 使用正則表達式查找數字
                if match:
                    duration = float(match.group())  # 提取匹配內容並轉換為 float
                else:
                    duration = None  # 如果沒有匹配到數字
            else:
                duration_info = None
                duration = None 
        language_modal = response.css('#languageRequirementsModalInternational div.modal-content.p-4 div.mb-2 p::text').getall()
        english = self.english_requirement(language_modal)

        university = UniversityScrapyItem()
        university['university_id'] = 2
        university['name'] = course_name  
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = response.meta['degree_level_id']
        university['course_url'] = response.url

        yield university


    def english_requirement(self, language_modal):
        english_requirement = None
        ielts_paragraph = None  # 初始化變量
        eng_req = None
        if len(language_modal) == 1:
            ielts_paragraph = language_modal[0]
        elif len(language_modal) == 2:
            ielts_paragraph = language_modal[0]
        elif len(language_modal) == 3: #Bachelor of Midwifery為了這個課程寫的例外
            ielts_paragraph = language_modal[1]
        elif len(language_modal) == 4: #Bachelor of Nursing為了這個課程寫的例外
            ielts_paragraph = language_modal[2]
        
        if ielts_paragraph:
            # print("==== Extracted IELTS Paragraph ====")
            # print(ielts_paragraph)
                             
            # 標準 IELTS 要求模式
            overall_pattern = r'IELTS\s*Academic?\s*score\s*of\s*(\d+(\.\d+)?)\s*overall.*?(?:,?\s*with\s*no\s*band\s*score\s*below\s*(\d+(\.\d+)?))?'
            match_overall = re.search(overall_pattern, ielts_paragraph)
            if match_overall:
                overall_score = match_overall.group(1)
                band_score = match_overall.group(3)
                # english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"
                english_requirement = f"IELTS {overall_score} overall, with no band score below {band_score}."
                eng_req = overall_score

            additional_pattern = r'(?i)IELTS\s*score\s*of\s*(\d+(\.\d+)?)\s*with\s*no\s*band\s*score\s*less\s*than\s*(\d+(\.\d+)?)'
            match_additional = re.search(additional_pattern, ielts_paragraph)  
            if match_additional:
                score = match_additional.group(1)
                band_score = match_additional.group(3)
                # english_requirement = f"IELTS {score} (單項不低於 {band_score})"
                english_requirement = f"IELTS {score} overall, with no band score below {band_score}."
                eng_req = score
            
            ielts_pattern = r'overall?\s*IELTS\s*Academic\s*score\s*(?:\(or\s*equivalent\))?\s*of\s*(\d+(\.\d+)?)\s*(?:,?\s*with\s*no\s*band\s*score\s*(?:less\s*than|below)\s*(\d+(\.\d+)?))?'
            match = re.search(ielts_pattern, ielts_paragraph)
            if match:
                score = match.group(1)  
                eng_req=score
                band_score = match.group(3) 
                additional_conditions = re.search(r'with\s*(.*?)(?:\s*and\s*no\s*band\s*score\s*below|\.)', ielts_paragraph)
                additional_conditions = additional_conditions.group(1).strip() if additional_conditions else ""
                speaking_listening_pattern = r'a score of not less than (\d+(\.\d+)) in both (speaking and listening|reading and writing),.*?no band score below (\d+(\.\d+)?)'
                match_speaking_listening = re.search(speaking_listening_pattern, ielts_paragraph)
                            
                if match_speaking_listening:
                    specific_skills_score = match_speaking_listening.group(1)
                    band_score = match_speaking_listening.group(4)
                    # skill_translation = "口說和聽力"
                    # english_requirement = f"IELTS {score} ({skill_translation}成績均不低於 {specific_skills_score}，單項不低於 {band_score})"
                    skill_translation = "speaking and listening"
                    english_requirement = f"IELTS {score} (a score of not less than {specific_skills_score} in both {skill_translation}, and no band score below {band_score})"
                else:
                    # 如果有 band score 限制，則加入條件
                    if band_score:
                        # english_requirement = f"IELTS {score} (單項不低於 {band_score.strip()})"                        
                        english_requirement = f"IELTS {score} overall, with no band score below {band_score.strip()}."
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
                    eng_req = overall_score
                    specific_skills_score = match.group(3)
                    skill_types = match.group(5)
                    band_score = match.group(6) 
                    if specific_skills_score and skill_types:
                        skill_translations = {
                            # "reading and writing": "閱讀和寫作",
                            # "speaking and listening": "口說和聽力"
                            "reading and writing": "reading and writing",
                            "speaking and listening": "speaking and listening"
                        }
                        skill_translation = skill_translations.get(skill_types, skill_types)
                        english_requirement = (
                            # f"IELTS {overall_score} ({skill_translation}成績均不低於 {specific_skills_score}，單項不低於 {band_score})"
                            f"IELTS {overall_score} (a score of not less than {specific_skills_score} in both {skill_translation}, with no band score below {band_score})"
                        )
                    else:
                        # english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"
                        english_requirement = f"IELTS {overall_score} (with no band score below {band_score})"
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
                        eng_req = overall_score
                        band_score = match_1.group(3) 
                        # english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"   
                        english_requirement = f"IELTS {overall_score} (with no band score below {band_score})"   
                    if match_2:
                        overall_score = match_2.group(1) 
                        eng_req = overall_score
                        band_score = match_2.group(3) 
                        # english_requirement = f"IELTS {overall_score} (單項不低於 {band_score})"                                  
                        english_requirement = f"IELTS {overall_score} (with no band score below {band_score})"          
        else:
            english_requirement = None
            eng_req = None
        # print("Final Output -> eng_req:", eng_req, "eng_req_info:", english_requirement)

        return  {"eng_req":eng_req,"eng_req_info":english_requirement}


    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n坎培拉大學，共{len(self.all_course_url)}筆資料\n')