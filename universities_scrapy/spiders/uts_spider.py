import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UtsSpider(scrapy.Spider):
    name = "uts_spider"
    allowed_domains = ["www.uts.edu.au"]    
    course_urls = "https://www.uts.edu.au/study/find-a-course/search?search="
    start_urls = ['https://www.uts.edu.au/study/international/essential-information/english-language-requirements']
    academic_requirement_url = 'https://www.uts.edu.au/study/international/essential-information/academic-requirements'
    fee_detail_url = 'https://cis.uts.edu.au/fees/course-fees.cfm'
    all_course_url = []
    skipped_courses_count = 0
    ielts_data = {}


    def parse(self, response):        
        sections = response.xpath('//section[@class="collapsible"]')
        
        for section in sections:
            section_title = section.xpath('.//h3/text()').get()
            is_undergraduate = 'Undergraduate' in section_title if section_title else False
            
            content_sections = section.xpath('.//div[@class="collapsible__content"]//p[strong]')
            
            for content in content_sections:
                # 獲取課程名稱
                courses = content.xpath('.//strong/text()').getall()
                
                # 獲取IELTS要求
                requirements_list = content.xpath('./following-sibling::ul[1]')
                if requirements_list:
                    ielts_req = requirements_list.xpath('.//li[contains(text(), "IELTS")]/text()').get()
                    
                    if ielts_req:
                        ielts_req = ielts_req.replace('\xa0\xa0', ' ').replace('\xa0', ' ')

                        # 提取IELTS分數
                        score_match = re.search(r'IELTS.*?(\d+\.?\d*)\s+overall', ielts_req)
                        if score_match:
                            ielts_score = float(score_match.group(1))
                            
                            # 處理每個課程
                            for course in courses:
                                course = course.strip()
                                
                                # 處理 "All other courses"
                                if "All other courses" in course:
                                    key = "Undergraduate coursework All other courses" if is_undergraduate else "Postgraduate coursework All other courses"
                                    self.ielts_data[key] = {
                                        "eng_req_info": ielts_req.strip(),
                                        "eng_req": ielts_score
                                    }
                                else:
                                    cleaned_course = re.sub(r'\s*\([C]\d{5}\)\s*', '', course.strip())
                                    if cleaned_course:
                                        cleaned_course = cleaned_course.replace('\xa0\xa0', ' ').replace('\xa0', ' ')
                                        self.ielts_data[cleaned_course] = {
                                            "eng_req_info": ielts_req.strip(),
                                            "eng_req": ielts_score
                                        }

        yield response.follow(self.course_urls, self.course_parse)

    def course_parse(self, response):
        target_labels = {
            "panel-undergraduate": "Bachelor's Degree",
            "panel-postgraduate": "Master's Coursework"
        }
        for panel_id, label in target_labels.items():
                panel = response.css(f"div.tab-bar__panel#{panel_id}")
                th_id = panel.xpath(f'//th[contains(text(), "{label}")]/@id').get()
                
                if th_id:
                    panel_links = response.xpath(f'//td[@headers="{th_id}"]//a/@href').getall()
                    panel_links = [response.urljoin(link) for link in panel_links] 
                    panel_links = [link for link in panel_links if "online-courses" not in link]
                    self.all_course_url.extend(panel_links)
                for link in panel_links:
                    yield response.follow(link, self.page_parse, errback=self.handle_error, meta={'panel_id': panel_id})
    
    def handle_error(self, failure):
        # 如果請求失敗並返回 503，則處理此錯誤
        if failure.check(scrapy.exceptions.IgnoreRequest):
            self.skipped_courses_count += 1
            # print(f"Skipping due to 503 error: {failure.request.url}")

    def page_parse(self, response):
        course_name = response.css('.page-title h1::text').get().strip()    

        locations = response.css('.block.block-dddd.block-dddd-view-modeluts-course-course__location p::text').get()
        if locations :
            locations.strip()
        duration_all = response.css('.sidebar__info.sidebar--info-duration p::text').getall()
        duration_data = [item.strip().replace("\n", "") for item in duration_all]
        duration_info = ' '.join(' '.join(duration_data).split())      

        # 提取 full time 前的數字
        pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full time"
        match = re.search(pattern, duration_info)
        if match:
            duration = match.group(1)
        else:
            duration = None


        uts_code_value = response.css('div.sidebar__info.sidebar--info-codes dt:contains("UTS") + dd span::text').get()
        
        # 根據 panel_id 設定 fee_type
        panel_id = response.meta.get('panel_id')
        fee_type = 'IFUG' if panel_id == 'panel-undergraduate' else 'IF'
        # 發送請求，取得學費        
        form_data = {
            'fee_type': fee_type,  # International Undergraduate
            'fee_year': '2025',  
            'cohort_year': '2025', 
            'course_area': 'All',  
            'Search': uts_code_value,
            'op': 'Search'
        }

        yield scrapy.FormRequest(
            url='https://cis.uts.edu.au/fees/course-fees.cfm',  
            formdata=form_data,
            callback=self.after_post,
            dont_filter=True, 
            meta={'course_name': course_name, 'locations': locations,'duration': duration, 'duration_info': duration_info, 'uts_code': uts_code_value, 'course_url': response.url,'degree_level':fee_type }
        )

    def after_post(self, response):
               
        tuition_fee = None
        rows = response.css('tr')
        for row in rows:
            fees = row.css('td.fees::text').getall()
            fees = [f.strip() for f in fees if f.strip()]
            if fees and '$' in fees[-1]:
                tuition_fee = fees[-1].replace('$', '').strip()
        
        
        
        # degree_level_id
        if response.meta['degree_level'] == 'IFUG' :
            degree_level_id = 1
        else:
            degree_level_id = 2
        english = self.get_ielts_requirement(response.meta['course_name'],degree_level_id)

        university = UniversityScrapyItem()
        university['university_id'] = 11
        university['name'] = response.meta['course_name']
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['campus'] =  response.meta['locations']
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['duration'] = response.meta['duration']
        university['duration_info'] = response.meta['duration_info']
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.meta['course_url']
        university['acad_req_url'] = self.academic_requirement_url
        university['eng_req_url'] = self.start_urls[0]
        university['fee_detail_url'] = self.fee_detail_url

        yield university

    def get_ielts_requirement(self, course_name, degree_level_id):
  
        for program, requirement in self.ielts_data.items():
            if course_name.lower() in program.lower():
                return {
                    "eng_req": requirement.get("eng_req", None),
                    "eng_req_info": requirement.get("eng_req_info", None)
                }
        if degree_level_id == 1:
            return {
                "eng_req": self.ielts_data["Undergraduate coursework All other courses"].get("eng_req", None),
                "eng_req_info": self.ielts_data["Undergraduate coursework All other courses"].get("eng_req_info", None)
            }    
        else:
            return {
                "eng_req": self.ielts_data["Postgraduate coursework All other courses"].get("eng_req", None),
                "eng_req_info": self.ielts_data["Postgraduate coursework All other courses"].get("eng_req_info", None)
            } 




    def closed(self, reason):    
        valid_courses_count = len(self.all_course_url) - self.skipped_courses_count
        print(f'{self.name}爬蟲完成!\n雪梨科技大學, 共有 {valid_courses_count} 筆資料(已扣除不開放申請)\n有 {self.skipped_courses_count} 筆目前不開放申請\n')

