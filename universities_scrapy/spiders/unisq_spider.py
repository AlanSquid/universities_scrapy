import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import json
import re

class UnisqSpiderSpider(scrapy.Spider):
    name = "unisq_spider"
    allowed_domains = ["www.unisq.edu.au"]
    # start_urls = ["https://www.unisq.edu.au/study/degrees/find-a-degree?studylevel=Undergraduate&studylevel=Postgraduate&mode=On-campus"]
    start_urls = ["https://www.unisq.edu.au/USQ/Web/ProgramFilter/GetPrograms"]
    except_count = 0
    all_course_url = []
    custom_settings = {
        'HTTPERROR_ALLOWED_CODES': [404]  # 允許 404 進入 parse()，不然會有錯誤訊息
    }
    def start_requests(self):
        headers = {
            "Content-Type": "application/json"
        }

        self.query_data = {
            "displayname": "",
            "studylevel": [
                "Undergraduate",
                "Postgraduate"
            ],
            "mode": "On-campus",
            "atar": "",
            "Take": 24,
            "skip": 0,
            "event": "program-filter-search"
        } 

        yield scrapy.Request(
            self.start_urls[0],
            headers=headers,
            method="POST",
            body=json.dumps(self.query_data),
            callback=self.parse_api_response
        )

    def parse_api_response(self, response):
        # yield response.follow('https://www.unisq.edu.au/study/degrees/bachelor-of-nursing/international', self.page_parse, meta=dict(degree_level_id = 1, campus = 1 ))
        data = response.json() 
        total_results = data['TotalResults']
        if total_results > self.query_data["Take"]:
            new_size = total_results
            self.query_data["Take"] = new_size
            # 再次發送請求，使用更新的size值
            yield scrapy.Request(
                self.start_urls[0],
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
                body=json.dumps(self.query_data),
                callback=self.parse_api_response
            )
        else:
            for item in data['Programs']:
                course_name = item['DisplayName']
                # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
                skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
                keywords = ["Bachelor of", "Master of"]
                if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2  or sum(course_name.count(keyword) for keyword in keywords) < 1:
                    # print('跳過:',course_name)
                    continue
                url = item['Url']
                course_url = f"{url}/international"
                self.all_course_url.append(course_url)
                
                study_level = item['StudyLevel']
                degree_level_id = None
                if "Undergraduate" in study_level:
                    degree_level_id = 1
                elif "Postgraduate" in study_level: 
                    degree_level_id = 2      
                
                campus = ", ".join(item['Campus'])


                yield response.follow(course_url, self.page_parse, meta=dict(degree_level_id = degree_level_id, campus = campus ))
       

    def page_parse(self, response):
        course_name = response.css('h1::text').get()
        if "404" in course_name:
            self.except_count += 1
            # print("頁面不存在，",response.url)
            return
        course_info = response.css('div.c-program-summary div.u-equal-height-columns')
        duration_info = course_info.xpath("//div[span[contains(@class, 'fa-clock')]]/following-sibling::ul[1]/li/text()").get()
        if duration_info:
            match = re.search(r'\d+(\.\d+)?', duration_info)
            if match:
                duration = float(match.group())
            else:
                duration = None 
        else:
            duration_info = None
            duration = None 
        
        # 英文門檻
        table_ielts = response.xpath("//td[contains(text(), 'IELTS (Academic)')]/following-sibling::td[1]//p/text()").get()
        if not table_ielts: 
            table_ielts = response.xpath("//td[contains(text(), 'IELTS (Academic)')]/following-sibling::td[1]/text()").get()

        # 如果第一種方式失敗，嘗試其他選擇器
        if not table_ielts:
            table_ielts = response.xpath("//tr[td[contains(text(), 'IELTS')]]/td[2]/text()").get()
            
        # 如果表格中沒有，嘗試從段落中獲取
        if not table_ielts:
            eng_req_info = response.xpath("//h3[contains(text(), 'English language requirements')]/following-sibling::ol//li//text()").getall()
            if not eng_req_info:
                eng_req_info = response.xpath("//h3[contains(text(), 'English language requirements')]/following-sibling::p[1]//text()").getall()
            eng_req_info = ' '.join(eng_req_info).strip()
        else:
            eng_req_info = table_ielts.strip()
        
        ielts_score = None
        ielts_info = None
        
        score_patterns = [
            r'overall score of\s*(\d+\.?\d+)',  # 匹配 "overall score of" 格式
            r'minimum overall score of\s*(\d+\.?\d+)',  # 匹配 "minimum overall score of" 格式
            r'IELTS.*?(\d+\.?\d+)',  # 匹配一般的 IELTS 分數
            r'minimum of IELTS\s*(\d+\.?\d+)',  # 匹配 "minimum of IELTS" 格式
        ]
        
        for pattern in score_patterns:
            score_match = re.search(pattern, eng_req_info)
            if score_match:
                ielts_score = float(score_match.group(1))
                break
        
        info_patterns = [
            r'Minimum overall score.*?(?:reading|subscore).*?',  # 匹配表格中的格式
            r'IELTS \(Academic\).*?(?:speaking|subscore)',  # 匹配到 speaking 或 subscore
            r'minimum of IELTS.*?(?:subscore|component)',   # 匹配含有 subscore 或 component 的段落
            r'IELTS.*?(?:band|subscore|component)'         # 通用匹配
        ]
        
        for pattern in info_patterns:
            info_match = re.search(pattern, eng_req_info)
            if info_match:
                ielts_info = info_match.group(0).strip()
                if ielts_info:
                    ielts_info = ielts_info.replace(' ', '')
                break

        # 取得學費
        fee_value =None
        rows = response.xpath("//table[contains(@class, 'o-details-table')]//tr")
        for row in rows:
            study_mode = row.xpath(".//td[1]//text()").get()
            fee = row.xpath(".//td[2]//text()").get()
            if  study_mode and "On-campus" in study_mode:
                fee_value = fee.strip().replace("AUD", "").strip()  # 移除 AUD 和空格


        university = UniversityScrapyItem()
        university['university_name'] = "University of Southern Queensland"
        university['name'] = course_name
        university['min_fee'] = fee_value
        university['max_fee'] = fee_value
        university['campus'] = response.meta["campus"]
        university['eng_req'] = ielts_score
        university['eng_req_info'] = ielts_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = response.meta["degree_level_id"]
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n南昆士蘭大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')