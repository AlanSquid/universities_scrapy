import scrapy
import json
import re
from universities_scrapy.items import UniversityScrapyItem  

class WesternsydneySpiderSpider(scrapy.Spider):
    name = "westernsydney_spider"
    allowed_domains = ["www.westernsydney.edu.au"]
    # 搜尋courses頁面: https://www.westernsydney.edu.au/future/study/courses 
    start_urls = ["https://www.westernsydney.edu.au/content/wsu-international/jcr:content/courseFilter.json?available-for=international-students&course-level=postgraduate,undergraduate"]
    all_course_url=[]
    english_requirement_url = 'https://www.westernsydney.edu.au/international/studying/entry-requirements'
   
    def parse(self, response):
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
        # name = re.sub(r'\b(master of|bachelor of)\b', '', course_name, flags=re.IGNORECASE).strip()
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
        english = self.english_requirement(course_name)
        
        campuses = response.css('.course_location_campus--items .course_location_name::text').getall()
        # 去除多餘的空白字符，包括 \t, \n 等
        campuses = [re.sub(r'\s+', ' ', campus).strip() for campus in campuses]
        # 移除後面直接跟隨數字的內容
        campuses = [re.sub(r'\s*\d+$', '', campus).strip() for campus in campuses]
        # 移除包含 'UAC' 的內容
        campuses = [re.sub(r'\s*UAC.*', '', campus).strip() for campus in campuses]
        location = ', '.join(campus for campus in campuses if campus)

        university = UniversityScrapyItem()
        university['university_id'] = 12
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

    def english_requirement(self, course_name):
        exception_courses_1 = [
            "Nursing", 
            "Nursing (Advanced)",
            "Clinical Science (Medicine)/Doctor of Medicine",
            "Podiatric Medicine"
        ]
        exception_courses_2 = [
            "Occupational Therapy", 
            "Health Science (Paramedicine)",
            "Physiotherapy",
            "Speech Pathology",
            "Health Science (Sport and Exercise Science)",
            "Social Work",
            "Criminal and Community Justice"
        ]
        if any(course in course_name for course in exception_courses_1):
            return {"eng_req":7,"eng_req_info":"IELTS 7.0 (單科不低於 7.0)"}
        
        elif any(course in course_name for course in exception_courses_2):
            return {"eng_req":7,"eng_req_info": "IELTS 7.0 (寫作和閱讀不低於 6.5，口說和聽力不低於 7.0)"}

        elif "Education (Primary)" in course_name:
            return {"eng_req":7.5,"eng_req_info": "IELTS 7.5 (閱讀和寫作不低於 7.0分，口說和聽力不低於 8.0)"  }

        return {"eng_req":6.5,"eng_req_info":  "IELTS 6.5 (單科不低於 6.0)"  }

    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n西雪梨大學, 共有 {len(self.all_course_url)} 筆資料\n')
      