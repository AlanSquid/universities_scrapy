import scrapy
import json
import re
from universities_scrapy.items import UniversityScrapyItem  

class WesternsydneySpiderSpider(scrapy.Spider):
    name = "westernsydney_spider"
    allowed_domains = ["www.westernsydney.edu.au"]
    start_urls = ["https://www.westernsydney.edu.au/content/wsu-international/jcr:content/courseFilter.json?available-for=international-students&course-level=undergraduate"]
    all_course_url=[]
    english_requirement_url = 'https://www.westernsydney.edu.au/international/studying/entry-requirements'

    def parse(self, response):
        data = response.json()  # api 回來是 json格是
        for item in data['result']:
            course_url = item['coursePageUrl']
            if course_url not in self.all_course_url:
                self.all_course_url.append(course_url)
                yield response.follow(course_url, self.page_parse)
    def page_parse(self, response):
        course_name = response.css("h1.cmp-title__text::text").get().strip()
        duration = response.css(".course_duration_info_box p.course_duration_time::text").get().strip()
        duration = duration.replace('(Available Part Time)*','')
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
        campuses = [re.sub(r'\s*UAC.*', '', campus.strip()) for campus in campuses]
        location = ', '.join(campus for campus in campuses if campus)
        university = UniversityScrapyItem()
        university['name'] = 'University of Western Sydney'
        university['ch_name'] = '西雪梨大學'
        university['course_name'] = course_name  
        university['min_tuition_fee'] = tuition_fee
        university['english_requirement'] = english
        university['location'] = location
        university['duration'] = duration
        university['course_url'] = response.url
        university['english_requirement_url'] = self.english_requirement_url

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
            return "IELTS 7.0 (單科不低於 7.0)"
        
        elif any(course in course_name for course in exception_courses_2):
            return "IELTS 7.0 (寫作和閱讀不低於 6.5，口說和聽力不低於 7.0)"
        
        elif "Education (Primary)" in course_name:
            return "IELTS 7.5 (閱讀和寫作不低於 7.0分，口說和聽力不低於 8.0)"        
        
        return "IELTS 6.5 (單科不低於 6.0)"
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n西雪梨大學, 共有 {len(self.all_course_url)} 筆資料\n')
      