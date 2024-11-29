import scrapy
from universities_scrapy.items import UniversityScrapyItem 


class UtsSpider(scrapy.Spider):
    name = "uts_spider"
    allowed_domains = ["www.uts.edu.au"]
    start_urls = ["https://www.uts.edu.au/study/find-a-course/search?search=Bachelor"]
    english_requirement_url = 'https://www.uts.edu.au/study/international/essential-information/english-language-requirements'
    academic_requirement_url = 'https://www.uts.edu.au/study/international/essential-information/academic-requirements'
    all_course_url = []

    def parse(self, response):
        pass
        links = response.css(
            "div.tab-bar__panel#panel-undergraduate tr td a::attr(href)"
        ).getall()

        for link in links:
            link = response.urljoin(link)
            self.all_course_url.append(link)
            yield response.follow(link, self.page_parse)

            
    def page_parse(self, response):
        course_name = response.css('.page-title h1::text').get().strip()    
        locations = response.css('.block.block-dddd.block-dddd-view-modeluts-course-course__location p::text').get().strip()
        duration_info = response.css('.sidebar__info.sidebar--info-duration p::text').getall()
        duration_data = [item.strip().replace("\n", "") for item in duration_info]
        duration = ' '.join(' '.join(duration_data).split())        
        uts_code_value = response.css('div.sidebar__info.sidebar--info-codes dt:contains("UTS") + dd span::text').get()
        # 發送請求，取得學費        
        form_data = {
            'fee_type': 'IFUG',  # International Undergraduate
            'fee_year': '2025',  # 费用年份
            'cohort_year': '2025',  # Cohort年份
            'course_area': 'All',  # 课程领域
            'Search': uts_code_value,  # 课程代码
            'op': 'Search'  # 提交操作
        }

        # 发送POST请求
        yield scrapy.FormRequest(
            url='https://cis.uts.edu.au/fees/course-fees.cfm',  
            formdata=form_data,
            callback=self.after_post,
            dont_filter=True, 
            meta={'course_name': course_name, 'locations': locations, 'duration': duration, 'uts_code': uts_code_value, 'course_url': response.url }
        )

    def after_post(self, response):

        fee_per_session = response.css('td.fees::text').getall()
        if len(fee_per_session) >= 5:
            fee = fee_per_session[5].strip()
            tuition_fee=fee.replace('$', '')
        else:
            tuition_fee = None
        english = self.english_requirement(response.meta['course_name'])

        university = UniversityScrapyItem()
        university['name'] = 'University of Technology Sydney'
        university['ch_name'] = '雪梨科技大學'
        university['course_name'] = response.meta['course_name']
        university['min_tuition_fee'] = tuition_fee
        university['location'] =  response.meta['locations']
        university['english_requirement'] = english
        university['duration'] = response.meta['duration']
        university['course_url'] = response.meta['course_url']
        university['academic_requirement_url'] = self.academic_requirement_url
        university['english_requirement_url'] = self.english_requirement_url
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
            return "IELTS 7.5 (口說8.0，聽力8.0，閱讀7.0，寫作7.0)"
        
        elif any(course == course_name for course in exception_courses_2):
            return "IELTS 7.0 (寫作7.0)"
        
        elif "Bachelor of Communication (Honours)" == course_name:
            return "IELTS 7.0 (寫作7.0)"        
        
        return "IELTS 6.5 (寫作6.0)"
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n雪梨科技大學, 共有 {len(self.all_course_url)} 筆資料\n')