import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class AdelaideSpider(scrapy.Spider):
    name = "adelaide_spider"
    allowed_domains = ["www.adelaide.edu.au"]
    base_url = "https://www.adelaide.edu.au"
    start_urls = ["https://www.adelaide.edu.au/degree-finder?v__s=bachelor&m=view&dsn=program.source_program&adv_avail_comm=1&adv_acad_career=0&adv_degree_type=0&adv_atar=0&year=2025&adv_subject=0&adv_career=0&adv_campus=0&adv_mid_year_entry=0"]

    def parse(self, response):
        links = response.css(
            "div.c-degree-finder__filter-results div.df_list_filter_ug ul.c-degree-finder__filter-results__list li a::attr(href)"
        ).getall()
        
        full_links = [self.base_url + link.strip() for link in links if link]
        for link in full_links:
            yield response.follow(link, self.page_parse)
    
    def page_parse(self, response): 
        
        # 取得課程名稱
        course_name = response.css('h1::text').get().strip()
        
        # 取得duration
        duration = response.css('li.c-icon-box__column') \
                        .xpath('.//h3[contains(text(), "Duration")]/following-sibling::div[@class="c-icon-box__description"]//text()') \
                        .getall()
        duration = ' '.join([d.strip() for d in duration if d.strip()])
        duration = re.sub(r'\s+', ' ', duration).strip()
        
        # 取得location
        locations = response.css('li.c-icon-box__column') \
        .xpath('.//h3[contains(text(), "Location")]/following-sibling::div[@class="c-icon-box__description"]//a/text() |.//h3[contains(text(), "Location")]/following-sibling::div[@class="c-icon-box__description"]/text()')\
        .getall()

        locations = [loc.strip() for loc in locations if loc.strip()]
        locations = ', '.join(locations) if locations else None

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
            english_requirement = f"IELTS {ielts_overall.strip()}"
        else:
            english_requirement = None

        university = UniversityScrapyItem()
        university['name'] = 'University of Adelaide'
        university['ch_name'] = '阿德雷得大學'
        university['course_name'] = course_name
        university['min_tuition_fee'] = tuition_fee
        university['location'] =  locations
        university['english_requirement'] = english_requirement
        university['duration'] = duration
        university['course_url'] = response.url

        yield university
    def closed(self, reason):    
        print('University of Adelaide 爬蟲完成!')        