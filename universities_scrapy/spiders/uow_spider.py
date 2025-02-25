import scrapy
from universities_scrapy.items import UniversityScrapyItem 
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
import re

class UowSpider(scrapy.Spider):
    name = "uow_spider"
    allowed_domains = ["www.uow.edu.au"]
    start_urls = ["https://www.uow.edu.au/study/courses/?keywords=&students=international&courseCalendar=undergraduate&courseCalendar=majors&courseCalendar=postgraduate%20coursework&courseCalendar=specialisations&courseCalendar=postgraduate%20research&atarTo=95"]
    all_course_url = []
    except_count = 0
    def parse(self, response):
        cards = response.css("div#search-results div.cf-course-item__inner")
        for card in cards:
            course_name = card.css("h3 a::text").get()
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue
            card_url = card.css("h3 a::attr(href)").get()

            params = {
                'students': 'international',
            }
            # 如果 card_url 本身已經有 query 參數，也會保留原有的
            parsed_url = urlparse(card_url)
            query_params = parse_qs(parsed_url.query)
            query_params.update(params)
            new_query_string = urlencode(query_params, doseq=True)
            new_card_url = parsed_url._replace(query=new_query_string).geturl()
            if new_card_url not in self.all_course_url:
                self.all_course_url.append(new_card_url)
            yield response.follow(new_card_url, self.page_parse) 

        next_page_button = response.css('nav[aria-label="Pagination"] a.cf-pagination__next.cf-pagination__page__numbers.cf-pagination__current::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            yield response.follow(next_page_url, self.parse) 
        # else:
        #     print("沒有下一頁")      

    # 另一個搜尋頁面
    # start_urls = ["https://www.uow.edu.au/search/?query=Master&sitesearch=&isKeyboardNav=&collection=courses","https://www.uow.edu.au/search/?query=Bachelor&sitesearch=&isKeyboardNav=&collection=courses"]
    # def parse(self, response):
    #     cards = response.css("div.uw-search--results article.uw-card--course")
    #     for card in cards:
    #         course_name = card.css("a::text").get()
    #         # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
    #         skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
    #         keywords = ["Bachelor of", "Master of"]
    #         if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
    #             # print('跳過:',course_name)
    #             continue
    #         card_url = card.css("a::attr(href)").get()

    #         params = {
    #             'students': 'international',
    #         }
    #         # 如果 card_url 本身已經有 query 參數，也會保留原有的
    #         parsed_url = urlparse(card_url)
    #         query_params = parse_qs(parsed_url.query)
    #         query_params.update(params)
    #         new_query_string = urlencode(query_params, doseq=True)
    #         new_card_url = parsed_url._replace(query=new_query_string).geturl()
    #         self.all_course_url.append(new_card_url)
    #         yield response.follow(new_card_url, self.page_parse) 

    #     next_page_button = response.css('nav[aria-label="pagination"] ul li.pagination-next a::attr(href)').get()
    #     if next_page_button:
    #         next_page_url = response.urljoin(next_page_button)
    #         yield response.follow(next_page_url, self.parse) 
    #     else:
    #         print("沒有下一頁")      



    def page_parse(self, response):
        course_name = response.css("div.cf-hero__text h1::text").get()

        student_row = response.xpath('//span[@id="studentLabel"]/ancestor::div[contains(@class, "cf-college-info__row")]')
        # 1. 嘗試抓取單一校區名稱
        student_text = student_row.xpath('.//div[contains(@class, "cf-college-info__right")]/text()').get()
        student_text = student_text.strip() if student_text else None
        if student_text:
            # 第一種情況，單一校區
            student = student_text
        else:
            # 2. 嘗試抓取選單中的多個校區名稱
            options = student_row.xpath('.//select[@id="students"]/option[not(@value="")]/text()').getall()
            options = [opt.strip() for opt in options if 'Please select' not in opt]
            if options:
                student_list = ', '.join(options)
                student = student_list
            else:
                student = None

        if "International" not in student:
            print(course_name,"不開放國際生，",response.url)
            self.except_count += 1
            return

        campus_row = response.xpath('//span[@id="campusLabel"]/ancestor::div[contains(@class, "cf-college-info__row")]')
        # 1. 嘗試抓取單一校區名稱
        campus_text = campus_row.xpath('.//div[contains(@class, "cf-college-info__right")]/text()').get()
        campus_text = campus_text.strip() if campus_text else None
        if campus_text:
            # 第一種情況，單一校區
            campus = campus_text
        else:
            # 2. 嘗試抓取選單中的多個校區名稱
            options = campus_row.xpath('.//select[@id="campus"]/option[not(@value="")]/text()').getall()
            options = [opt.strip() for opt in options if 'Please select' not in opt]
            if options:
                campus_list = ', '.join(options)
                campus = campus_list
            else:
                campus = None


        # duration
        duration_info = response.css('section.cf-hero div.cf-college-info div#duration::text').get()
        duration_info = duration_info.replace('\r\n', '').strip() if duration_info else None
        # 如果 duration_info 為 None 或不包含 full-time/full time，則跳過
        if duration_info:
            if 'part-time' in duration_info.lower() or 'part time' in duration_info.lower():
                if 'full-time' not in duration_info.lower() and 'full time' not in duration_info.lower() and 'or' not in duration_info.lower():
                    # print("Only part-time info found, skipping this course.",response.url)
                    self.except_count += 1
                    return
            pattern = r"(\d+(\.\d+)?)\s+year(s)?"
            match = re.search(pattern, duration_info, re.IGNORECASE)
            if match:
                duration = match.group(1)
            else:
                duration = None
        else:
            duration = None

        ielts_container = response.css("div#cf-scroll-entry-requirements div.cf-tabs-wrap div#panel1 ul li tbody")
        # ielts_row = response.xpath('//td[contains(text(), "IELTS Academic")]/parent::tr')
        ielts_row = ielts_container.xpath('//td[contains(.//text(), "IELTS Academic")]/parent::tr')
        if ielts_row:
            # 提取 IELTS 成績
            # 提取 IELTS 成績，注意這裡用 normalize-space() 處理空白符號問題
            overall = ielts_row.xpath('./td[2]//text()').getall()
            reading = ielts_row.xpath('./td[3]//text()').getall()
            writing = ielts_row.xpath('./td[4]//text()').getall()
            listening = ielts_row.xpath('./td[5]//text()').getall()
            speaking = ielts_row.xpath('./td[6]//text()').getall()

            # 去掉空白並組合文字
            overall = ''.join(x.strip() for x in overall).strip()
            reading = ''.join(x.strip() for x in reading).strip()
            writing = ''.join(x.strip() for x in writing).strip()
            listening = ''.join(x.strip() for x in listening).strip()
            speaking = ''.join(x.strip() for x in speaking).strip()

            # 組成所需格式的字串
            eng_req = overall
            eng_req_info = f"IELTS Academic Overall Score {overall}, Reading {reading}, Writing {writing}, Listening {listening}, Speaking {speaking}"
        else:
            eng_req = None
            eng_req_info = None

        # 學費
        session_fees_container = response.css("section.cf-home-mid-sec div#cf-scroll-more-detail div#panel11")
        session_fees_raw = session_fees_container.xpath('//table//td[3]//text()').getall()

        # 提取金額數字
        fees = []
        for fee in session_fees_raw:
            match = re.search(r'\$([\d,]+)', fee)
            if match:
                fee_value = int(match.group(1).replace(',', ''))
                fees.append(fee_value)

        if fees:
            max_fee = max(fees)
            min_fee = min(fees)
        else:
           max_fee = None
           min_fee = None
        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2

        university = UniversityScrapyItem()
        university['university_id'] = 13
        university['name'] = course_name
        university['min_fee'] = min_fee
        university['max_fee'] = max_fee
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['campus'] = campus
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university      

    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n臥龍崗大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)\n')
