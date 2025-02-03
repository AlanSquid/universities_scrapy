import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UtsSpider(scrapy.Spider):
    name = "uts_spider"
    allowed_domains = ["www.uts.edu.au"]    
    start_urls = ["https://www.uts.edu.au/study/find-a-course/search?search="]
    english_requirement_url = 'https://www.uts.edu.au/study/international/essential-information/english-language-requirements'
    academic_requirement_url = 'https://www.uts.edu.au/study/international/essential-information/academic-requirements'
    all_course_url = []
    skipped_courses_count = 0

    def parse(self, response):
        pass
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
            print(f"Skipping due to 503 error: {failure.request.url}")

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
        
        
        english = self.english_requirement(response.meta['course_name'])
        
        # degree_level_id
        if response.meta['degree_level'] == 'IFUG' :
            degree_level_id = 1
        else:
            degree_level_id = 2

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
        university['eng_req_url'] = self.english_requirement_url
        yield university

    def english_requirement(self, course_name):
        exception_courses_1 = [
            "Bachelor of Science Master of Teaching in Secondary Education", 
            "Bachelor of Communication (Writing and Publishing) Master of Teaching in Secondary Education",
            "Bachelor of Technology Master of Teaching in Secondary Education",
            "Bachelor of Business Master of Teaching in Secondary Education",
            "Bachelor of Economics Master of Teaching in Secondary Education",
            "Bachelor of Education Futures Master of Teaching in Primary Education",
        ]
        exception_courses_2 = [
            "Bachelor of Nursing", 
            "Bachelor of Nursing Bachelor of Creative Intelligence and Innovation",
            "Bachelor of Nursing Bachelor of International Studies"
        ]
        if any(course == course_name for course in exception_courses_1):
            return  {"eng_req":7.5,"eng_req_info":"IELTS 7.5 (口說8.0，聽力8.0，閱讀7.0，寫作7.0)"}

        elif any(course == course_name for course in exception_courses_2):
            return  {"eng_req":7,"eng_req_info":"IELTS 7.0 (寫作7.0)"}

        elif "Bachelor of Communication (Honours)" == course_name:
            return  {"eng_req":7,"eng_req_info":"IELTS 7.0 (寫作7.0)"}

        return  {"eng_req":6.5,"eng_req_info":"IELTS 6.5 (寫作6.0)"}

    def closed(self, reason):    
        valid_courses_count = len(self.all_course_url) - self.skipped_courses_count
        print(f'{self.name}爬蟲完成!\n雪梨科技大學, 共有 {valid_courses_count} 筆資料\n跳過 {self.skipped_courses_count} 筆資料')