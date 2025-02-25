import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UscSpiderSpider(scrapy.Spider):
    name = "usc_spider"
    allowed_domains = ["www.usc.edu.au"]
    # start_urls先取德英文門檻
    start_urls =  ["https://www.usc.edu.au/international/international-students/english-language-requirements"]
    # course_urls = ["https://www.usc.edu.au/study/courses-and-programs?location=Study+location&discipline=Study+area"]
    course_urls = "https://www.usc.edu.au/webapi/programfilter/get/5648"
    all_course_url = []
    except_count = 0
    ielts_data = {}

    def parse(self, response):
        self.ielts_data = {}
        self.ielts_data['Undergraduate'] = {}
        self.ielts_data['Postgraduate'] = {}

        standard_requirements = response.css("div.tab-content div[aria-labelledby='tab-1']")
        ielts_row = standard_requirements.xpath('.//tr[td//p[contains(text(), "IELTS (Academic)")]]')
        ielts_undergraduate = ielts_row.xpath('./td[2]/text()').get()
        ielts_postgraduate = ielts_row.xpath('./td[3]/text()').get()
        ielts_undergraduate = ielts_undergraduate.strip() if ielts_undergraduate else None
        ielts_postgraduate = ielts_postgraduate.strip() if ielts_postgraduate else None

        def extract_ielts_score(ielts_text):
            if ielts_text and ielts_text.strip():
                match = re.search(r'overall\s*(?:score|band)?\s*(?:of|or)?\s*(\d+(?:\.\d+)?)', ielts_text, re.IGNORECASE)
                if match:
                    return float(match.group(1))
            return None

        self.ielts_data['Undergraduate']["eng_req_info"] = ielts_undergraduate
        self.ielts_data['Undergraduate']["eng_req"] = extract_ielts_score(ielts_undergraduate)

        self.ielts_data['Postgraduate']["eng_req_info"] = ielts_postgraduate
        self.ielts_data['Postgraduate']["eng_req"] = extract_ielts_score(ielts_postgraduate)

        non_standard_requirements = response.css("div.tab-content div[aria-labelledby='tab-2']")

        h6_elements = non_standard_requirements.css('h6')

        for i in range(0, len(h6_elements)):
            # 取得課程名稱
            h6 = h6_elements[i]
            current_course_names = []
            a_elements = h6.css('a')
            for a in a_elements:
                course_name = a.xpath('string()').get().strip()
                if course_name:
                    current_course_names.append(course_name)
            if not current_course_names:
                h6_text = h6.xpath('string()').get().strip()
                text_parts = [part.strip() for part in h6_text.split(',')]
                current_course_names = [part for part in text_parts if part and not part.startswith('*')]

            if not current_course_names:
                continue

            next_table = h6.xpath('following-sibling::table[1]')
            if not next_table:
                continue

            ielts_text = None
            # 取得IELTS門檻
            ielts_row = next_table.xpath('.//tr[contains(., "IELTS")]')
            if ielts_row:
                td_element = ielts_row.xpath('.//td')
                if td_element:
                    all_texts = td_element.xpath('.//text()').getall()
                    text_content = ' '.join([text.strip().replace('\xa0', ' ') for text in all_texts if text.strip()])
                    if text_content:
                        ielts_text = text_content

            if not ielts_text:
                first_row = next_table.xpath('.//tr[1]')
                if first_row and 'IELTS' in first_row.get():
                    td_element = first_row.xpath('.//td')
                    if td_element:
                        all_texts = td_element.xpath('.//text()').getall()
                        text_content = ' '.join([text.strip().replace('\xa0', ' ') for text in all_texts if text.strip()])
                        if text_content:
                            ielts_text = text_content

            if not ielts_text or ielts_text.strip() == '':
                ielts_text = None

            for course in current_course_names:
                clean_course = course.replace('*', '').strip()
                if clean_course and clean_course != '(Sippy Downs) Semester 1 commencement (February)':
                    self.ielts_data[clean_course] = {
                        'eng_req_info': f"IELTS (Academic) {ielts_text}" if ielts_text else None,
                        'eng_req': extract_ielts_score(ielts_text)
                    }

        yield scrapy.Request(self.course_urls, callback=self.course_parse)
    
    
    def get_ielts_requirement(self, course_name, degree_level_id):
  
        for program, requirement in self.ielts_data.items():
            if course_name.lower() in program.lower():
                return {
                    "eng_req": requirement.get("eng_req", None),
                    "eng_req_info": requirement.get("eng_req_info", None)
                }
        if degree_level_id == 1:
            return {
                "eng_req": self.ielts_data["Undergraduate"].get("eng_req", None),
                "eng_req_info": self.ielts_data["Undergraduate"].get("eng_req_info", None)
            }    
        else:
            return {
                "eng_req": self.ielts_data["Postgraduate"].get("eng_req", None),
                "eng_req_info": self.ielts_data["Postgraduate"].get("eng_req_info", None)
            } 
       
    def course_parse(self, response):
        json_response = response.json()
        cards = json_response["programs"]
        for card in cards:
            course_name = card["name"]
            
            # degree_level
            allowed_program_types = {"Bachelor Degree", "Master Degree"}
            # 判斷 programType 是否只包含允許的項目
            if not set(card["programType"]).issubset(allowed_program_types):
                continue

            degree_level = ", ".join(card["programType"])
            degree_level_id = None
            if "Bachelor" in degree_level:
                degree_level_id = 1
            elif "Master" in degree_level:
                degree_level_id = 2

            # url
            url = card["url"]
            course_url = response.urljoin(url)
            self.all_course_url.append(course_url)
            
            # duration
            duration_info = card["internationalDuration"]
            if duration_info:
                duration_info = duration_info.strip()
                pattern = r"(\d+(\.\d+)?)\s+year"
                match = re.search(pattern, duration_info)
                if match:
                    duration = float(match.group(1))  
                else:
                    duration = None 
            else:
                duration_info = None

            fee_element = card["annualTuitionFee"]
            if fee_element:
                tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()
            
            # locations
            locations = card["locations"]
            filtered_locations = [
                re.sub(r'<.*?>', '', location)  # 移除 HTML 標籤，保留地名
                for location in locations
                if 'international' in re.search(r'audience="([^"]+)"', location).group(1)
            ]

            # 將結果以逗號分隔並存成字串
            locations_str = ", ".join(filtered_locations)      
            if locations_str.lower() == "online":
                self.except_count += 1
                return
            yield response.follow(course_url, self.page_parse, meta=dict(
                course_name = course_name,
                degree_level_id = degree_level_id,
                duration_info = duration_info,
                duration = duration,
                tuition_fee = tuition_fee,
                locations_str = locations_str
            ))


    def page_parse(self, response): 
        course_info = response.css("div.program-viewswitch--text::text").get()
        if course_info and "This program is only available to domestic students" in course_info:
            # print("不開放國際生申請，",response.url)
            self.except_count += 1
            return

        title = response.xpath('//h1[@class="program-header--title"]//text()').getall()
        course_name = ' '.join([t.strip() for t in title if t.strip()])
        english = self.get_ielts_requirement(course_name, response.meta["degree_level_id"])
        university = UniversityScrapyItem()
        university['university_id'] = 22
        university['name'] = course_name
        university['min_fee'] = response.meta["tuition_fee"]
        university['max_fee'] = response.meta["tuition_fee"]
        university['campus'] = response.meta["locations_str"]
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['duration'] = response.meta["duration"]
        university['duration_info'] = response.meta["duration_info"]
        university['degree_level_id'] = response.meta["degree_level_id"]
        university['course_url'] = response.url
        university['eng_req_url'] = self.start_urls

        yield university
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n陽光海岸大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
