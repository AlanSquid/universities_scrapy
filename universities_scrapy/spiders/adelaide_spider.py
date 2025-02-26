import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class AdelaideSpider(scrapy.Spider):
    name = "adelaide_spider"
    allowed_domains = ["www.adelaide.edu.au"]
    base_url = "https://www.adelaide.edu.au"
    start_urls = ["https://www.adelaide.edu.au/degree-finder/?v__s=&m=view&dsn=program.source_program&adv_avail_comm=1&adv_acad_career=0&adv_degree_type=1&adv_atar=0&year=2025&adv_subject=0&adv_career=0&adv_campus=0&adv_mid_year_entry=0","https://www.adelaide.edu.au/degree-finder/?v__s=&m=view&dsn=program.source_program&adv_avail_comm=1&adv_acad_career=0&adv_degree_type=10&adv_atar=0&year=2025&adv_subject=0&adv_career=0&adv_campus=0&adv_mid_year_entry=0"]
    full_link_list=[]
    except_count = 0
    def parse(self, response):
        links = response.css(
            "div.c-degree-finder__filter-results  ul.c-degree-finder__filter-results__list li a::attr(href)"
        ).getall()
        
        full_links = [self.base_url + link.strip() for link in links if link]
        for link in full_links:
            self.full_link_list.append(link)
            yield response.follow(link, self.page_parse)
    
    def page_parse(self, response): 
        degree_level_id = None

        # 取得課程名稱
        course_name = response.css('h1::text').get().strip()
    
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2

        if course_name.lower().startswith("master of"):
            course_name = course_name.split("of", 1)[1].strip()
        elif course_name.lower().startswith("bachelor of"):
            course_name = course_name.split("of", 1)[1].strip()
    
        # 取得duration
        duration_info = response.css('li.c-icon-box__column') \
                        .xpath('.//h3[contains(text(), "Duration")]/following-sibling::div[@class="c-icon-box__description"]//text()') \
                        .getall()
        if duration_info:
            duration_info = ' '.join([d.strip() for d in duration_info if d.strip()])
            duration_info = re.sub(r'\s+', ' ', duration_info).strip()
            match = re.search(r'\d+(\.\d+)?', duration_info)  # 使用正則表達式查找數字
            if match:
                duration = float(match.group())  # 提取匹配內容並轉換為 float
            else:
                duration = None  # 如果沒有匹配到數字
        else:
            duration_info = None
            duration = None 


        # 取得location
        locations = response.css('li.c-icon-box__column') \
        .xpath('.//h3[contains(text(), "Location")]/following-sibling::div[@class="c-icon-box__description"]//a/text() |.//h3[contains(text(), "Location")]/following-sibling::div[@class="c-icon-box__description"]/text()')\
        .getall()

        locations = [loc.strip() for loc in locations if loc.strip()]
        locations = ', '.join(locations) if locations else None
        if locations and locations.lower() == "online":
            self.except_count += 1
            return        
        # 取得學費
        fee_element = response.css('div.international_applicant td::text').getall()
        tuition_fee = None
        for text in fee_element:
            if "International student place" in text:
                fee_match = re.search(r'\$([\d,]+)', text)
                if fee_match:
                    tuition_fee = fee_match.group(1).replace(',', '')
                break
        
        # 取得英文門檻
        english_table = response.xpath('//h6[contains(text(), "English Language Requirements")]/following-sibling::table[1]')   
        ielts_overall = english_table.xpath(
            './/table[contains(@class, "df_int_elr_table")]//td[contains(text(), "Overall")]/text()'
        ).get()
        
        # 如果有找到分數，處理並建立結果
        if ielts_overall:
            overall_score = re.search(r'(\d+(\.\d+)?)', ielts_overall)
            eng_req_info = f"IELTS {overall_score.group(1)}"
            eng_req = overall_score.group(1)
        else:
            eng_req_info = None
            eng_req = None

        university = UniversityScrapyItem()
        university['university_name'] = "University of Adelaide"
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['campus'] =  locations
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['course_url'] = response.url
        university['degree_level_id'] = degree_level_id

        yield university
    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n阿德雷得大學，共{len(self.full_link_list) - self.except_count}筆資料\n')
