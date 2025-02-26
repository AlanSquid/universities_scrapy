import re
import time
import scrapy
from universities_scrapy.items import UniversityScrapyItem

class QutSpiderSpider(scrapy.Spider):
    name = "qut_spider"
    allowed_domains = ["www.qut.edu.au"]
    start_urls = ["https://www.qut.edu.au/study/international/"]
    seen_urls = set()
    start_time = time.time()
    non_international_num = 0
    except_count = 0
    # 到 https://www.qut.edu.au/study/international 頁面找到15個課程大類
    def parse(self, response):
        urls = response.css('div#study-areas ul.study-area-links li.list-links a.arrow-link::attr(href)').getall()
        for url in urls:
            # 跟隨連結進入新的頁面
            yield response.follow(url, callback=self.parse_areas)

    # 進入各課程大類共三種狀況 1. 需先選擇undergraduate 或 postgraduate。(e.g. Justice) 2. 有分不同的課程類型。(e.g. Business) 3. 直接有課程
    # 第3種狀況中的又有Create Arts的部分比較特殊，又進一步細分小類別
    def parse_areas(self, response):
        # 檢查是否存在 "Explore our undergraduate courses"
        explore_courses_button = response.css('a.button.blue.button--blue-outline.arrow.mb-3.study-area-list-buttons.w-100::attr(href)').getall()
        course_links = response.css('ul.study-area-links li.list-links a.arrow-link::attr(href)').getall()
        bachelor_courses = response.css('.row .col-lg-4')
        
        # # 處理第一種狀況 ex: https://www.qut.edu.au/study/international/communication
        if explore_courses_button:
            for course_button in explore_courses_button:
                # print(course_button) 確認只有?postgraduate和?undergraduate
                yield response.follow(
                    url=response.urljoin(course_button),
                    callback=self.parse_course_link,
                )

        # 第二種狀況 ex: https://www.qut.edu.au/study/international/business
        elif course_links:
            for link in course_links:
                yield response.follow(
                    url=response.urljoin(link),
                    callback=self.parse_course_link,
                )

         # 第三種狀況 ex: https://www.qut.edu.au/study/international/creative-arts
        elif bachelor_courses:
            for course in bachelor_courses:
                course_name = course.css('h3::text').get(default='').strip()
            
                if 'Bachelor' in course_name and 'Honours' not in course_name:
                    course_link = course.css('a.arrow-link::attr(href)').get()
                    
                    # 如果是art中的creative art類別，要到parse_creative_art_course再進一層解析
                    if "creative-art" in str(course_link):
                        art_course_group_link = course_link
                        yield response.follow(
                            url=response.urljoin(art_course_group_link),
                            callback=self.parse_creative_art_course,
                        )
                        
                    # 如果有連結，進行資料返回    
                    elif course_link:
                        if "?international" not in str(course_link):
                            course_link = response.urljoin(course_link) + "?international"
                        yield response.follow(
                            url=course_link,
                            callback=self.parse_course_page,
                        )

    # 專門處理creative art小類別的url的function
    def parse_creative_art_course(self, response):
        art_course_names = response.css('li.no-list-bullets a::text').getall()
        art_course_links = response.css('li.no-list-bullets a::attr(href)').getall()
        for i in range(len(art_course_names)):
            if 'Bachelor' in art_course_names[i] or 'Master' in art_course_names[i]:
                art_course_link = art_course_links[i].strip()
                if "?international" not in str(art_course_link):
                    art_course_link = response.urljoin(art_course_link) + "?international"
                yield response.follow(
                    url=art_course_link,
                    callback=self.parse_course_page,
                )
    # 除了creative art小類別，蒐集其他網頁的課程url
    def parse_course_link(self, response):
        # div.course-details 的 id:data-course-audience="DOM,INT" 國際生要有 "INT"
        # 取得 h4 是 single-degrees 和 Masters 底下的 div.course-list 底下的 div.course-details 底下的 a.course-page-link
        courses = response.xpath('//h4[contains(text(), "Single degrees") or contains(text(), "Masters")]'
                                '/following-sibling::div[contains(@class, "course-list")][1]'
                                '//div[contains(@class, "course-details") and contains(@data-course-audience, "INT")]'
                                '//a[contains(@class, "course-page-link")]/@href').getall()        
        if courses:
            for course in courses:   
                if not course or "honours" in course:
                    # print('honours跳過:',course)
                    continue
                if "?international" not in str(course):
                    international_course = response.urljoin(course) + "?international"
                yield response.follow(
                    url = international_course,
                    callback = self.parse_course_page,
                )
                
    # 在課程網頁中抓取資料
    def parse_course_page(self, response):
        course_name = response.css('h1.hero__header__title span::text').get()
        keywords = ["Bachelor of", "Master of", "Doctor of"]
        if not course_name or sum(course_name.count(keyword) for keyword in keywords) >= 2:
            return 

        degree_level_id = None
        if "Bachelor of" in course_name:
            degree_level_id = 1
        elif "Master of" in course_name: 
            degree_level_id = 2
    
        # 費用處理
        tuition_fee = ''
        fees_all = response.css('div.box-wrap.col-sm-6 div.box-content p::text').getall()
        for fee in fees_all:
            if "CSP" in fee:
                continue
            if "2025" in fee:  # 檢查是否包含 2025
                match = re.search(r'\$(\d{1,3}(?:,\d{3})*)', fee)  # 使用正則表達式抓取費用
                if match:
                    tuition_fee = match.group(1).replace(',', '')  # 去掉千位分隔符
                    break
        
        # # 校區處理
        locations = response.css('ul[data-course-map-key="quickBoxDeliveryINT"] li::text').getall()
        location = ', '.join(locations)

        if location and location.lower() == "online":
            self.except_count += 1
            return

        # # 學習時間處理
        durations = response.css('li[data-course-map-key="quickBoxDurationINTFt"]::text').getall()
        duration_info = ', '.join([d.strip() for d in durations])
        if duration_info:
            duration_info = duration_info.strip()
            match = re.search(r'\d+(\.\d+)?', duration_info)  # 使用正則表達式查找數字
            if match:
                duration = float(match.group())  # 提取匹配內容並轉換為 float
            else:
                duration = None  # 如果沒有匹配到數字

        # # 英文門檻
        eng_req = ''
        eng_reqs = response.css('table#int-elt-table td#elt-overall::text').getall()
        for number in eng_reqs:
            if type(number) == str:
                eng_req = number.strip()
                break
        
        if tuition_fee and eng_req:
            self.seen_urls.add(response.url)
            university = UniversityScrapyItem()
            university['university_name'] = "Queensland University of Technology"
            university['name'] = course_name
            university['min_fee'] = tuition_fee
            university['max_fee'] = tuition_fee
            university['eng_req'] = eng_req
            university['eng_req_info'] = f'IELTS (Academic) {eng_req}'
            university['campus'] = location
            university['duration'] = duration
            university['duration_info'] = duration_info
            university['degree_level_id'] = degree_level_id
            university['course_url'] = response.url
            yield university

        else:
            audience_element = response.xpath('//span[@data-course-audience="DOM" and text()="This course is only available for Australian and New Zealand students."]')
            if audience_element:
                self.non_international_num += 1
                # print(f'不收國際生: {response.url}')
            # 專門處理類似creative art小類別的網頁
            else:
                url = str(response.url).replace("?international", "")
                yield response.follow(
                    url=url,
                    callback=self.parse_creative_art_course,
                )

    def close(self):
        print(f'\n{self.name}爬蟲完畢！\n昆士蘭科技大學，共{len(self.seen_urls) - self.except_count}個課程開放給國際生')
        print(f'其中有{self.non_international_num}個科系，不開放給國際生\n')
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'{elapsed_time:.2f}', '秒')