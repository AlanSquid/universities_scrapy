import scrapy
from universities_scrapy.items import UniversityScrapyItem  
import re

class JcuSpiderSpider(scrapy.Spider):
    name = "jcu_spider"
    allowed_domains = ["www.jcu.edu.au"]
    courese_urls = "https://www.jcu.edu.au/courses/_config/ajax-items/global-funnelback-results-dev?SQ_ASSET_CONTENTS_RAW&bodyDesignType=default&collection=jcu-v1-courses&query=Bachelor&num_ranks=1001&pagination=all&sort=&meta_studyLevel_sand=Undergraduate&meta_courseAvailability_orsand=both+int_only"
                  
    # 這是english_requirement_url
    start_urls = ["https://www.jcu.edu.au/policy/academic-governance/student-experience/admissions-policy-schedule-ii"]
    academic_requirement_url = "https://www.jcu.edu.au/applying-to-jcu/international-applications/academic-and-english-language-entry-requirements/country-specific-academic-levels"
    all_course_url=[]
    english_levels = {}
    # english_levels = {
    #     "Band P": "IELTS 5.5 (單科不低於 5.0)",
    #     "Band 1": "IELTS 6 (單科不低於 6.0)",
    #     "Band 2": "IELTS 6.5 (單科不低於 6.0)",
    #     "Band 3a": "IELTS 7.0 (單科不低於 6.5)",
    #     "Band 3b": "IELTS 7.5 (三項不低於 7.0，一項不得低於 6.5)",
    #     "Band 3c": "IELTS 7.5 (單科不低於 7.0)",
    # }

    def parse(self, response):
        # 處理英文門檻
        ielts_row = response.xpath('//tr[td/p/strong[contains(text(), "IELTS")]]')
        if not ielts_row:
            return
        header_row = response.xpath('//tr[1]')
        band_names = header_row.xpath('.//td/p/strong/text()').getall()
        ielts_cells = ielts_row.xpath('.//td')
        self.english_levels = {}
        
        for band_name, cell in zip(band_names, ielts_cells[1:]):
            # 提取單科總分的正則表達式
            overall_score_match = re.search(r'(\d+(?:\.\d+)?)', cell.get())
            
            # 提取附加條件的正則表達式
            condition_match = re.search(r'\(([^)]+)\)', cell.get())
            
            if overall_score_match:
                overall_score = overall_score_match.group(1)
                english_desc = f"IELTS {overall_score}"
                
                # 處理附加條件
                if condition_match:
                    condition = condition_match.group(1).lower()
                    
                    if 'no component lower than' in condition or '不低於' in condition:
                        # 擷取最低分數要求
                        min_score_match = re.search(r'no component lower than (\d+(?:\.\d+)?)', condition)
                        if min_score_match:
                            min_score = min_score_match.group(1)
                            english_desc += f" (單科不低於 {min_score})"
                    
                    # 特殊情況：三項分數要求
                    if 'with' in condition and 'three components' in condition:
                        three_components_score_match = re.search(r'(\d+(?:\.\d+)?) in three components', condition)
                        one_component_score_match = re.search(r'and (\d+(?:\.\d+)?) in one component', condition)
                        
                        if three_components_score_match and one_component_score_match:
                            three_score = three_components_score_match.group(1)
                            one_score = one_component_score_match.group(1)
                            english_desc = f"IELTS 7.5 (三項不低於 {three_score}，一項不得低於 {one_score})"
                
                band_name = band_name.strip()
                self.english_levels[band_name] = english_desc
                yield response.follow(self.courese_urls, self.cards_parse)

    def cards_parse(self, response):
        cards = response.css(".jcu-v1__search__result")
        for card in cards: 
            course_title = card.css(".jcu-v1__search__result--title a.jcu-v1__search__heading::text").get()
            # 去掉不是Bachelor的course
            if not course_title or "Bachelor" not in course_title:
                # print(course_title)
                continue
            url = card.css("a::attr(href)").get()
            self.all_course_url.append(url)
            yield response.follow(url, self.page_parse)
            
    def page_parse(self, response):
        course_name = response.css("h1.course-banner__title::text").get()
        campuses = response.css('.course-fast-facts__location-list-item a.course-fast-facts__location-link::text').getall()
        campuses = [campus.strip() for campus in campuses if campus.strip()]
        location = ', '.join(campuses)
        duration = response.css(".course-fast-facts__tile.fast-facts-duration p::text").get()
        tuition_fee = response.css(".course-fast-facts__tile.fast-facts-fees p::text").get()
        match = re.search(r'\d+(?:,\d+)*(\.\d+)?', tuition_fee)
        if match:
            fee = match.group(0)  
            fee = fee.replace(',', '')  

        english_level = response.css('.course-fast-facts__tile__body-top p::text').re_first(r'Band\s\w+')
        english = self.english_requirement(english_level)

        university = UniversityScrapyItem()
        university['name'] = 'James Cook University'
        university['ch_name'] = '詹姆士庫克大學'
        university['course_name'] = course_name  
        university['min_tuition_fee'] = fee
        university['english_requirement'] = english
        university['location'] = location
        university['duration'] = duration
        university['course_url'] = response.url
        university['english_requirement_url'] = self.start_urls
        university['academic_requirement_url'] = self.academic_requirement_url

        yield university
        
    def english_requirement(self, english_level):
        if english_level:
            return self.english_levels.get(english_level, self.english_levels['Band P'])
        return self.english_levels['Band P']
    
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n詹姆士庫克大學, 共有 {len(self.all_course_url)} 筆資料\n')
      