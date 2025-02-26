import scrapy
import json
import re
from universities_scrapy.items import UniversityScrapyItem  

class WesternsydneySpiderSpider(scrapy.Spider):
    name = "westernsydney_spider"
    allowed_domains = ["www.westernsydney.edu.au"]
    # 搜尋courses頁面: https://www.westernsydney.edu.au/future/study/courses 
    start_urls = ["https://www.westernsydney.edu.au/international/studying/entry-requirements"]
    course_start_urls = "https://www.westernsydney.edu.au/content/wsu-international/jcr:content/courseFilter.json?available-for=international-students&course-level=postgraduate,undergraduate"
    all_course_url=[]
    english_requirement_url = 'https://www.westernsydney.edu.au/international/studying/entry-requirements'
    ielts_data = {}
    except_count = 0
    # 確保 'others' 被初始化為字典
    def parse(self, response):
        ielts_data = {}
        
        # 確保 'others' 被初始化為字典
        ielts_data['others'] = {}

        # 首先查找包含 "IELTS (Academic version)" 的部分
        # 使用 CSS 選擇器的替代方法
        ielts_section = response.xpath('//h6[contains(text(), "IELTS")]/parent::*/parent::*/parent::*')
        
        if ielts_section:
            # 抓取整體分數
            overall_score = ielts_section.xpath('.//span[@class="lead"]/b/text()').get()
            # 抓取各科最低分數要求
            subtest_req = ielts_section.xpath('.//p/text()').getall()
            subtest_req = [text.strip() for text in subtest_req if 'Minimum' in text]
            
            if overall_score and subtest_req:
                complete_requirement = f"{overall_score}, {subtest_req[0]}" if subtest_req else overall_score
                # 使用正則表達式提取數字部分（例如：6.5）
                match = re.search(r'(\d+(\.\d+)?)\s+overall score', complete_requirement)
                if match:
                    overall_score = match.group(1)  # 提取數字部分
                    # 將 'others' 放入 programs 中
                    ielts_data['others']["eng_req"] = overall_score
                ielts_data['others']["eng_req_info"] = f"IELTS {complete_requirement}"

        rows = response.xpath('//table[@id="table24116"]/tbody/tr')
        for row in rows:
            # 擷取 Program/Discipline
            programs = row.xpath('./td[1]//text()').getall()
            programs = [prog.strip() for prog in programs if prog.strip()]

            # 擷取完整的 IELTS 資訊，抓取所有的文本
            ielts_requirement = row.xpath('./td[2]//text()').getall()
            # 清理空白並合併文本
            ielts_requirement = " ".join([text.strip() for text in ielts_requirement if text.strip()])  

            # 檢查是否提取到 IELTS 資訊
            if ielts_requirement:
                if "We only accept test results from one test sitting" in ielts_requirement:
                    overall_match = re.search(r'minimum overall score of (\d+(\.\d+)?)', ielts_requirement)
                    component_match = re.search(r'no score in any component of the test is below (\d+(\.\d+)?)', ielts_requirement)

                    overall_score = overall_match.group(1) if overall_match else None
                    min_component_score = component_match.group(1) if component_match else None

                    for program in programs:
                        program = program.replace("M ", "Master of ").replace("B ", "Bachelor of ")
                        ielts_data[program] = {}

                        if overall_score and min_component_score:
                            ielts_data[program]["eng_req"] = overall_score
                            ielts_data[program]["eng_req_info"] = f"IELTS {overall_score} overall score, with no component below {min_component_score}"
                        else:
                            ielts_data[program]["eng_req_info"] = f"IELTS {ielts_requirement}"
                else:
                    # **不包含 "We only accept test results from one test sitting"，直接存原始內容**
                    # 將每個 program 初始化為字典，並包含 eng_req 和 eng_req_info
                    for program in programs:
                        program = program.replace("M ", "Master of ").replace("B ", "Bachelor of ")
                        ielts_data[program] = {}
                        ielts_data[program]["eng_req_info"] = f"IELTS {ielts_requirement}"
                        
                        # 如果有整體分數，則提取數字並更新
                        match = re.search(r'(\d+(\.\d+)?)\s+overall score', ielts_requirement)
                        if match:
                            overall_score = match.group(1)  # 提取數字部分
                            ielts_data[program]["eng_req"] = overall_score
        # 存儲或處理爬取的資料
        self.ielts_data = ielts_data  # 存為類別變數，方便查詢
        yield scrapy.Request(
                self.course_start_urls, 
                method="GET",
                callback=self.course_start_parse, 
                )   

    def get_ielts_requirement(self, course_name):
        if "others" not in self.ielts_data:
            return {"eng_req": None, "eng_req_info": None}
        
        for program, requirement in self.ielts_data.items():
            # 檢查課程名稱是否在program中
            if course_name.lower() in program.lower():
                return {
                    "eng_req": requirement.get("eng_req", None),
                    "eng_req_info": requirement.get("eng_req_info", "No info available")
                }
        
        # 若沒有找到匹配的課程，返回 'others' 的資料
        return {
            "eng_req": self.ielts_data["others"].get("eng_req", None),
            "eng_req_info": self.ielts_data["others"].get("eng_req_info", "No info available")
        }
    def course_start_parse(self, response):
        data = response.json()  
        # api 回傳格式
        # {"coursePageUrl":"https://www.westernsydney.edu.au/future/study/courses/undergraduate/bachelor-of-international-studies-bachelor-of-social-science",
        #  "courseColour":"#ED0033",
        #  "courseLevel":"undergraduate",
        #  "courseProgramName":"Bachelor of International Studies / Bachelor of Social Science",
        #  "alphabetCode":"s",
        #  "vanityId":"1616075741"}
        for item in data['result']:
            course_url = item['coursePageUrl']
            course_name = item['courseProgramName']
             # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of", "Doctor of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue
            if course_url not in self.all_course_url[:5]:
                self.all_course_url.append(course_url)
                yield response.follow(course_url, self.page_parse)

    def page_parse(self, response):
        course_name = response.css("h1.cmp-title__text::text").get().strip()
        degree_level_id = None

        if "undergraduate" in response.url.lower():
            degree_level_id = 1
        elif "postgraduate" in response.url.lower(): 
            degree_level_id = 2

        duration_info = response.css(".course_duration_info_box p.course_duration_time::text").get().strip()
        if duration_info:
            duration_info = duration_info.replace('(Available Part Time)*','')
            match = re.search(r'\d+(\.\d+)?', duration_info)  # 使用正則表達式查找數字
            if match:
                duration = float(match.group())  # 提取匹配內容並轉換為 float
            else:
                duration = None  # 如果沒有匹配到數字
        else:
            duration_info = None
            duration = None 

        # 取得費用
        data_json = response.xpath('//*[@id="course-api-json"]/@data-json').get()
        if data_json:
            data_json = data_json.replace('&#34;', '"')
            data = json.loads(data_json)
            fees = data.get('internationalFees')
            if fees:
                fees_numeric = re.search(r'\d{1,3}(?:,\d{3})*', fees)
                if fees_numeric:
                    tuition_fee = fees_numeric.group(0)
                    tuition_fee = tuition_fee.replace(',', '')
        # english = self.english_requirement(course_name)
        english = self.get_ielts_requirement(course_name)

        campuses = response.css('.course_location_campus--items .course_location_name::text').getall()
        # 去除多餘的空白字符，包括 \t, \n 等
        campuses = [re.sub(r'\s+', ' ', campus).strip() for campus in campuses]
        # 移除後面直接跟隨數字的內容
        campuses = [re.sub(r'\s*\d+$', '', campus).strip() for campus in campuses]
        # 移除包含 'UAC' 的內容
        campuses = [re.sub(r'\s*UAC.*', '', campus).strip() for campus in campuses]
        location = ', '.join(campus for campus in campuses if campus)
        if location and location.lower() == "online":
            self.except_count += 1
            return
        university = UniversityScrapyItem()
        university['university_name'] = "University of Western Sydney"
        university['name'] = course_name  
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        university['eng_req_url'] = self.english_requirement_url

        yield university

    # def english_requirement(self, course_name):
    #     exception_courses_1 = [
    #         "Nursing", 
    #         "Nursing (Advanced)",
    #         "Clinical Science (Medicine)/Doctor of Medicine",
    #         "Podiatric Medicine"
    #     ]
    #     exception_courses_2 = [
    #         "Occupational Therapy", 
    #         "Health Science (Paramedicine)",
    #         "Physiotherapy",
    #         "Speech Pathology",
    #         "Health Science (Sport and Exercise Science)",
    #         "Social Work",
    #         "Criminal and Community Justice"
    #     ]
    #     if any(course in course_name for course in exception_courses_1):
    #         return {"eng_req":7,"eng_req_info":"IELTS 7.0 overall score, minimum 7.0 in each subtest"}
        
    #     elif any(course in course_name for course in exception_courses_2):
    #         return {"eng_req":7,"eng_req_info": "IELTS 7.0 overall score, minimum 6.5 in writing and reading, 7.0 in speaking and listening"}

    #     elif "Education (Primary)" in course_name:
    #         return {"eng_req":7.5,"eng_req_info": "IELTS 7.5 overall score, minimum 7.0 in reading and writing, minimum 8.0 for speaking and listening"  }

    #     return {"eng_req":6.5,"eng_req_info":  "IELTS 6.5 overall score, Minimum 6.0 in each subtest"  }

    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n西雪梨大學, 共有 {len(self.all_course_url) - self.except_count} 筆資料\n')
      