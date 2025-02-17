import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UtasSpiderSpider(scrapy.Spider):
    name = "utas_spider"
    allowed_domains = ["www.utas.edu.au"]
    start_urls = ["https://www.utas.edu.au/search?num_ranks=50&f.Course+Level%7CcourseLevel=UG&f.Course+Level%7CcourseLevel=PG&f.Course+Year%7CcourseYear=2025&collection=utas%7Esp-search&f.Tabs%7Cutas%7Eds-handbook-courses=Courses"]
    all_course_url = []
    num = 0
    except_count = 0
    def parse(self, response):
        # 把資料存入 university Item
        self.num +=1
        cards = response.css("div#search-results__list ol li.search-result.search-result-course")
        for card in cards:
            course_name = card.css("h4 a::text").get()
            course_name = course_name.strip() if course_name else None
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Undergraduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2  or sum(course_name.count(keyword) for keyword in keywords) < 1:
                # print('跳過:',course_name)
                continue
            fb_result_url = card.attrib.get("data-fb-result")
            if fb_result_url not in self.all_course_url:
                self.all_course_url.append(fb_result_url)
                yield response.follow(fb_result_url, self.page_parse) 

        next_page_button = response.css('nav[aria-label="pagination"] li.page-next a::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            yield response.follow(next_page_url, self.parse) 
        else:
            print("沒有下一頁，頁數",self.num)
    
    def page_parse(self, response):
        course_name = response.css("h1::text").get()

        not_available_text = response.xpath(
            '//div[@id="#panel-international"]//p[contains(text(), "This course may not be available to international students.")]/text()'
        ).get()
        if not_available_text:
            self.except_count += 1
            # print("此課程不適用於國際學生，", response.url)
            return

        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2        
        
        # duration_info
        duration_info = response.xpath('//dl[.//h3[contains(text(), "Duration")]]//dd//span[@class="meta-list--item-inner"]/text()').get()
        if duration_info:
            duration_info = duration_info.strip().split('\n')[0].strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?"
        match = re.search(pattern, duration_info)
        if match:
            duration = match.group(1)
        else:
            duration = None

        # locations
        locations = response.xpath('//h3[contains(text(), "Location")]/..//dl/dt[@class="meta-list--title"]/text()').getall()
        locations_set = {loc.strip() for loc in locations if loc.strip()}  # 使用集合去重
        locations = ', '.join(sorted(locations_set)) if locations_set else None  # 如果集合為空則返回 None

        # fee 
        fee_section2 = response.xpath('//div[@class="richtext richtext__medium"]//p[contains(text(), "Total Course Fee")]//strong/text()').get()
        fee_section = response.xpath(
            '//div[@class="richtext richtext__medium"]//p[contains(text(), "Course cost based on a rate of")]/text() | //div[@class="richtext richtext__medium"]//p[contains(text(), "Course cost based on a rate of")]/descendant-or-self::text()'
        ).getall()

        total_fee = None
        # 第二種情況：根據費率計算年費
        if fee_section:
            fee_text = ' '.join(fee_section).strip()  # 將所有提取到的文本合併成一個字符串
            rate_match = re.search(r'\$([\d,]+)', fee_text)  # 提取$後的數字
            if rate_match:
                total_fee = float(rate_match.group(1).replace(',', ''))
        # 第一種情況：直接列出年費
        if fee_section2 and  total_fee is None :
            fee_number = re.search(r'[\d,]+', fee_section2)
            if fee_number:
                total_fee = float(fee_number.group().replace(',', ''))

        eng_req_info = None
        total_score = None
        ielts_patterns = [
            '//div[@id="c-entry-requirements"]//p[contains(text(), "IELTS (Academic)")]/text()',
            '//div[@id="c-entry-requirements"]//ul/li[contains(text(), "IELTS")]/text()',
            '//div[@id="c-entry-requirements"]//p[contains(text(), "IELTS")]/text()',
            '//div[@id="c-entry-requirements"]//p/font[contains(text(), "IELTS")]/text()',
            '//div[@id="c-entry-requirements"]//p//*[contains(text(), "IELTS (Academic)")]/text()'
        ]

        ielts_text2 = response.xpath('//div[@id="c-entry-requirements"]//p[descendant-or-self::*[contains(text(), "IELTS")]]//text()').get()

        for pattern in ielts_patterns:
            ielts_text = response.xpath(pattern).get()
            if ielts_text:
                ielts_text = ielts_text.strip()

                regex_patterns = [
                    r'IELTS \(Academic\).*?(\d+\.\d+).*?\)',
                    r'IELTS Academic.*?band',
                    r'IELTS.*?(\d+\.?\d*).*?less than \d+\.?\d*' 
                ]

                for regex in regex_patterns:
                    ielts_match = re.search(regex, ielts_text)
                    if ielts_match:
                        eng_req_info = ielts_match.group(0).strip()
                        eng_req_info = re.sub(r',?\s*or a PTE Academic score of [^,]+', '', eng_req_info)

                        score_match = re.search(r'(\d+(\.\d+)?)', eng_req_info) 

                        if score_match:
                            total_score = float(score_match.group(1))
                        break
                if eng_req_info:
                    break

        # 特殊課程 Master of Teaching
        if eng_req_info is None and ielts_text2:
            regex = r'(The Master of Teaching requires an \(IELTS\) average of.*?(\d+\.\d+))'
            ielts_match = re.search(regex, ielts_text2)
            if ielts_match:
                # 提取整段符合條件的文字
                eng_req_info = ielts_match.group(1).strip()  
                eng_req_info = re.sub(r',?\s*or a PTE Academic score of [^,]+', '', eng_req_info)
                total_score = float(ielts_match.group(2))

        university = UniversityScrapyItem()
        university['university_id'] = 29
        university['name'] = course_name
        university['min_fee'] = total_fee
        university['max_fee'] = total_fee
        university['campus'] = locations
        university['eng_req'] = total_score
        university['eng_req_info'] = eng_req_info
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}塔斯馬尼亞大學\n西澳大學，共{len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')