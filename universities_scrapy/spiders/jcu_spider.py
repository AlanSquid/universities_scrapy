import scrapy
from universities_scrapy.items import UniversityScrapyItem  
import re

class JcuSpiderSpider(scrapy.Spider):
    name = "jcu_spider"
    allowed_domains = ["www.jcu.edu.au"]
    courese_urls = "https://www.jcu.edu.au/courses/_config/ajax-items/global-funnelback-results-dev?SQ_ASSET_CONTENTS_RAW&bodyDesignType=default&collection=jcu-v1-courses&query=!null&num_ranks=1001&pagination=all&sort=metacourseSort&meta_courseAvailability_orsand=both+int_only"
    
    # english_requirement_url
    start_urls = ["https://www.jcu.edu.au/policy/academic-governance/student-experience/admissions-policy-schedule-ii"]
    acad_req_url = "https://www.jcu.edu.au/applying-to-jcu/international-applications/academic-and-english-language-entry-requirements/country-specific-academic-levels"
    all_course_url=[]
    english_levels = {}
    except_count = 0
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
            score_and_details = " ".join(cell.xpath('.//p//text()').getall()).strip()
            # 提取單科總分的正則表達式
            overall_score_match = re.search(r'(\d+(?:\.\d+)?)', cell.get())
            # 提取附加條件的正則表達式
            # condition_match = re.search(r'\(([^)]+)\)', cell.get())
            
            if overall_score_match:
                overall_score = overall_score_match.group(1)
                # english_desc = f"IELTS {overall_score}"
                
                # # 處理附加條件
                # if condition_match:
                #     condition = condition_match.group(1).lower()
                    
                #     if 'no component lower than' in condition or '不低於' in condition:
                #         # 擷取最低分數要求
                #         min_score_match = re.search(r'no component lower than (\d+(?:\.\d+)?)', condition)
                #         if min_score_match:
                #             min_score = min_score_match.group(1)
                #             english_desc += f" (單科不低於 {min_score})"
                    
                #     # 特殊情況：三項分數要求
                #     if 'with' in condition and 'three components' in condition:
                #         three_components_score_match = re.search(r'(\d+(?:\.\d+)?) in three components', condition)
                #         one_component_score_match = re.search(r'and (\d+(?:\.\d+)?) in one component', condition)
                        
                #         if three_components_score_match and one_component_score_match:
                #             three_score = three_components_score_match.group(1)
                #             one_score = one_component_score_match.group(1)
                            
                #             english_desc = f"IELTS {overall_score} (三項不低於 {three_score}，一項不得低於 {one_score})"
                
                band_name = band_name.strip()
                self.english_levels[band_name] = {
                    "eng_req": overall_score,
                    "eng_req_info":(f"IELTS {score_and_details}")

                }
                # self.english_levels[band_name] = english_desc
                yield response.follow(self.courese_urls, self.cards_parse)

    def cards_parse(self, response):
        cards = response.css(".jcu-v1__search__result")
        for card in cards: 
            course_title = card.css(".jcu-v1__search__result--title a.jcu-v1__search__heading::text").get()
    
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of"]
            if not course_title or any(keyword in course_title for keyword in skip_keywords) or sum(course_title.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_title)
                continue
            url = card.css("a::attr(href)").get()
            self.all_course_url.append(url)
            yield response.follow(url, self.page_parse)
            
    def page_parse(self, response):
        course_name = response.css("h1.course-banner__title::text").get()
        degree_level_id=None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2
        # name = re.sub(r'\b(master of|bachelor of)\b', '', course_name, flags=re.IGNORECASE).strip()

        campuses = response.css('.course-fast-facts__location-list-item a.course-fast-facts__location-link::text').getall()
        campuses = [campus.strip() for campus in campuses if campus.strip()]
        location = ', '.join(campuses)
        if location.lower() == "online":
            self.except_count += 1
            return
        duration_info = response.css(".course-fast-facts__tile.fast-facts-duration p::text").get()
        if duration_info:
            match = re.search(r'\d+(\.\d+)?', duration_info)
            if match:
                duration = float(match.group())
            else:
                duration = None 
        else:
            duration_info = None
            duration = None 
        tuition_fee = response.css(".course-fast-facts__tile.fast-facts-fees p::text").get()
        match = re.search(r'\d+(?:,\d+)*(\.\d+)?', tuition_fee)
        if match:
            fee =match.group(0)
            fee = float(fee.replace(',', ''))
        else:
            fee = None

        english_level = response.css('.course-fast-facts__tile__body-top p::text').re_first(r'Band\s\w+')
        english = self.english_requirement(english_level)

        university = UniversityScrapyItem()
        university['university_name'] = "James Cook University"
        university['name'] = course_name  
        university['min_fee'] = fee
        university['max_fee'] = fee
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['campus'] = location
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url
        university['eng_req_url'] = self.start_urls
        university['acad_req_url'] = self.acad_req_url

        yield university
 
    def english_requirement(self, english_level):
        if english_level:
            return self.english_levels.get(english_level, self.english_levels['Band P'])
        return self.english_levels['Band P']
    
    
    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n詹姆士庫克大學, 共有 {len(self.all_course_url) - self.except_count} 筆資料\n')
      