import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re
import json
import requests 
import os  
import pdfplumber
import re
class NotredameSpiderSpider(scrapy.Spider):
    name = "notredame_spider"
    allowed_domains = ["search.nd.edu.au","www.notredame.edu.au","notre-dame-search.clients.funnelback.com"]
    # 英文門檻url
    start_urls = ["https://www.notredame.edu.au/study/fees-costs-and-scholarships/tuition-fees/international-student-fees"]
    # fee_detail_url = "https://www.notredame.edu.au/study/fees-costs-and-scholarships/tuition-fees/international-student-fees"
    eng_req_url = "https://www.notredame.edu.au/study/applications-and-admissions/admission-requirements/english-language-proficiency-requirements"
    course_urls = "https://search.nd.edu.au/s/search.html?_gl=1*16wpysm*_gcl_au*Njk2MTk3MDQ4LjE3NDAwMTYzOTg.*_ga*MTgzNjU4MTA0OC4xNzQwMDE2Mzk4*_ga_Q0GX64QPEG*MTc0MDAxNjM5NS4xLjAuMTc0MDAxNjM5NS42MC4wLjk2Nzk4ODM1NQ..&f.Study+mode%7CprogramsStudyMode=&f.Study+mode%7CprogramsStudyMode=On+campus&profile=programs&query=&f.Study+area%7CprogramsStudyArea=&f.Location%7CprogramsCampus=&collection=notre-dame~sp-program&f.Study+level%7CprogramsDegreeLevel=Postgraduate&f.Study+level%7CprogramsDegreeLevel=Undergraduate&f.Student+type%7CprogramsStudentType=International&f.Duration+type%7CprogramsDurationType=Full+time"
    all_course_url = []
    except_count = 0
    ielts_data = {}
    fee_data = {}

    # 取得學費資訊，存入 fee_data
    def parse(self, response):
        # 照到 PDF 下載的 urls
        fees_urls = response.xpath(
            "//strong[text()='Student Fees List']/parent::p/following-sibling::ul[1]//a/@href"
        ).getall()

        for url in fees_urls:
            pdf_response = requests.get(url)
            pdf_path = os.path.join("downloads", os.path.basename(url))  # 保存路徑
            os.makedirs("downloads", exist_ok=True)  # 建立資料夾
            with open(pdf_path, 'wb') as f:
                f.write(pdf_response.content)  # 保存 PDF 
            
            # 提取fees
            fees_data = self.extract_fees_data(pdf_path)
            self.fee_data.update(fees_data)  

        yield response.follow(self.eng_req_url, self.eng_req_parse)

    # 取得英文門檻資訊，存入 ielts_data
    def eng_req_parse(self, response):
        ielts_info = response.css("div#English_language_test_scores-1")
        undergraduate_ielts_info = ielts_info.xpath("//p[contains(text(), 'undergraduate')]/following-sibling::table[1]//td[p/strong[text()='IELTS Academic']]/following-sibling::td/p/text()").get()
        postgraduate_ielts_info = ielts_info.xpath("//h6[contains(text(), 'postgraduate')]/following-sibling::table[1]//td[p/strong[text()='IELTS Academic']]/following-sibling::td/p/text()").get()
        if undergraduate_ielts_info:
            undergraduate_ielts_info = undergraduate_ielts_info.strip()
            undergraduate_score = float(re.search(r'(\d+\.\d+|\d+)', undergraduate_ielts_info).group(1))
        else:
            undergraduate_ielts_info = None
            undergraduate_score = None
        if postgraduate_ielts_info:
            postgraduate_ielts_info = postgraduate_ielts_info.strip()
            postgraduate_score = float(re.search(r'(\d+\.\d+|\d+)', postgraduate_ielts_info).group(1))
        else:
            postgraduate_ielts_info = None
            postgraduate_score = None

        self.ielts_data = {
            "undergraduate": {
                "eng_req_info": f"IELTS Academic {undergraduate_ielts_info}" if undergraduate_ielts_info else None,
                "eng_req": undergraduate_score
            },
            "postgraduate": {
                "eng_req_info": f"IELTS Academic {postgraduate_ielts_info}" if postgraduate_ielts_info else None,
                "eng_req": postgraduate_score
            }
        }
        
        # 特殊英文門檻課程資訊
        accordion_items = response.css('li.accordion__item')
        
        for item in accordion_items:
            programs = item.css('ul li a::text').getall()            
            ielts_info = item.xpath('.//tr[contains(.//td[1]/p/strong/text(), "IELTS Academic")]/td[2]/p/text()').getall()
            if ielts_info:
                ielts_info = ' '.join([info.strip() for info in ielts_info if info.strip()])
                ielts_match = re.search(r'(\d+\.\d+)\s+overall', ielts_info)
                if ielts_match:
                    ielts_score = float(ielts_match.group(1))
                else:
                    ielts_match = re.search(r'Average.*?(\d+\.\d+)', ielts_info)
                    if ielts_match:
                        ielts_score = float(ielts_match.group(1))
                    else:
                        ielts_score = None
                
                for program in programs:
                    program_name = program.strip()
                    if program_name and not program_name.startswith("including"):
                        program_name = re.sub(r' - \d{4}$', '', program_name)
                        program_name = re.sub(r' \(\d{4}\)$', '', program_name)
                        self.ielts_data[program_name] = {
                            "eng_req_info": f"IELTS Academic {ielts_info}",
                            "eng_req": ielts_score
                        }

        yield response.follow(self.course_urls, self.course_parse)



    def course_parse(self, response):
        cards = response.css("div#courses-testing div.card.ps-card")
        for card in cards:
            course_name = card.css("div.ps-card-content a h3::text").get()
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2 or sum(course_name.count(keyword) for keyword in keywords) < 1:
                # print('跳過:',course_name)
                continue            
            url = card.css("div.ps-card-content a::attr(href)").get()
            self.all_course_url.append(url)
            yield response.follow(url, self.page_parse)
        next_page_button = response.css('ul.cp-pagination div.cp-pagination-next li a::attr(href)').get()
        if next_page_button:
            next_page_url = response.urljoin(next_page_button)
            yield response.follow(next_page_url, self.course_parse) 


    def get_ielts_requirement(self, course_name, degree_level_id):
        for program, requirement in self.ielts_data.items():
            if course_name.lower() in program.lower():
                return {
                    "eng_req": requirement.get("eng_req", None),
                    "eng_req_info": requirement.get("eng_req_info", None)
                }
        if degree_level_id == 1:
            return {
                "eng_req": self.ielts_data["undergraduate"].get("eng_req", None),
                "eng_req_info": self.ielts_data["undergraduate"].get("eng_req_info", None)
            }    
        else:
            return {
                "eng_req": self.ielts_data["postgraduate"].get("eng_req", None),
                "eng_req_info": self.ielts_data["postgraduate"].get("eng_req_info", None)
            } 
       

    def page_parse(self, response):
        course_name = response.css("h1.page-title::text").get()
        course_url = response.xpath('//meta[@name="dcterms.identifier"]/@content').get()
        
        # Bachelor of Nursing 頁面不一樣另外處理 
        if not course_name:
            course_name = response.css("h1.text-white::text").get()
            script_content = response.xpath('//script[contains(text(), "pageUrls")]/text()').get()
            urls = re.search(r'let pageUrls = ({.*?})', script_content, re.S)
            if urls:
                urls_dict = json.loads(urls.group(1).replace("'", '"'))
                international_first_url = urls_dict.get('international-fremantle')
            yield response.follow(international_first_url,self.page_parse2, meta=dict(
                            course_name = course_name,
                            course_url = course_url
                        ))
            return
            
        course_info = response.css("div.content-container.nopadding div.sidebar.sidebar--right div.program-details")
        location = course_info.xpath('//span[strong[text()="Location"]]/following-sibling::span/text()').get()
        duration_info = course_info.xpath('//span[strong[text()="Duration"]]/following-sibling::span/text()').get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?(.*?)full-time"
            pattern2 = r"(\d+(\.\d+)?)\s+full-time"
            match = re.search(pattern, duration_info)
            match2 = re.search(pattern2, duration_info)
            if match:
                duration = float(match.group(1))  
            elif match2:
                duration = float(match2.group(1))  
            else :
                duration = None  
        else:
            duration_info = None

        # 取得學費
        cricos_code = course_info.xpath('//span[strong[text()="CRICOS code"]]/following-sibling::span/text()').get()
        # 特殊情況，不只一個匹配七位數字或英文字母組合
        match = re.findall(r'\b[A-Za-z0-9]{7}\b', cricos_code) if cricos_code else []
        # 取得第一組符合格式的 CRICOS code，若無則回傳 None
        cricos_code = match[0] if match else None

        tuition_fee = None
        tuition_fee = self.fee_data.get(cricos_code) 
        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2

        english = self.get_ielts_requirement(course_name, degree_level_id)
        
        university = UniversityScrapyItem()
        university['university_name'] = "University of Notre Dame Australia"
        university['name'] = course_name
        university['min_fee'] =tuition_fee
        university['max_fee'] =tuition_fee
        university['campus'] = location
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = course_url
        university['eng_req_url'] = self.eng_req_url
        university['fee_detail_url'] = self.start_urls[0]

        yield university

    def page_parse2(self, response):
        course_info = response.css("section.bg-light div.row.career-details div.career-details-item")
        duration_info = course_info.xpath('//div[h6[text()="Duration"]]/p[1]/text()').get()
        if duration_info:
            duration_info = duration_info.strip()
            pattern = r"(\d+(\.\d+)?)\s+year[s]?(.*?)full time"
            match = re.search(pattern, duration_info)
            if match:
                duration = float(match.group(1))   
            else :
                duration = None  
        else:
            duration_info = None
        location_titles = response.xpath('//div[@class="section__contact-cards"]//h4[@class="card__title"][normalize-space() != ""]/text()').getall()
        location = ', '.join(location_titles)
        fee_text = response.xpath('//h6[text()="Fees"]/following-sibling::p[contains(text(), "Indicative annual fee")]/text()').get()
        tuition_fee = float(fee_text.split(':')[1].strip().replace(',', '').replace('$', '').replace('*', ''))
        degree_level_id = None
        if "bachelor" in response.meta["course_name"].lower():
            degree_level_id = 1
        elif "master" in response.meta["course_name"].lower(): 
            degree_level_id = 2
        english = self.get_ielts_requirement(response.meta["course_name"], degree_level_id)
        university = UniversityScrapyItem()
        university['university_name'] = "University of Notre Dame Australia"
        university['name'] = response.meta["course_name"]
        university['min_fee'] =tuition_fee
        university['max_fee'] =tuition_fee
        university['campus'] = location
        university['eng_req'] = english['eng_req']
        university['eng_req_info'] = english['eng_req_info']
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.meta["course_name"]
        university['eng_req_url'] = self.eng_req_url
        university['fee_detail_url'] = self.start_urls[0]

        yield university


    def clean_text(self, text):
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())

    def extract_fees_data(self, pdf_path):
        with pdfplumber.open(pdf_path) as pdf:
            cricos_tuition_map = {}
            global_header_indices = None
            
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                
                for table in tables:
                    if not table or len(table) <= 1:
                        continue
                    
                    # 檢查table是否有表頭
                    has_header = False
                    header_indices = None
                    
                    for row_idx, row in enumerate(table):
                        row_text = " ".join([str(cell) for cell in row if cell])
                        if 'CRICOS' in row_text and 'TUITION' in row_text:
                            has_header = True
                            
                            # 提取需要的列索引
                            header_indices = {
                                'cricos': next((i for i, x in enumerate(row) if x and 'CRICOS' in str(x)), None),
                                'tuition': next((i for i, x in enumerate(row) if x and 'TUITION' in str(x) and 'ANNUAL' in str(x)), None)
                            }
                            
                            global_header_indices = header_indices
                            break
                    
                    # 如果目前表格沒有表頭，請使用通用表頭索引
                    if not has_header and global_header_indices is not None:
                        header_indices = global_header_indices
                    elif not has_header and global_header_indices is None:
                        # print(f"{page_num + 1} 頁表格中未包含找到表頭的信息")
                        continue
                    
                    # 處理表格資料
                    start_row_idx = row_idx + 1 if has_header else 0
                    
                    for row_idx in range(start_row_idx, len(table)):
                        row = table[row_idx]
                        if not row or not any(row):
                            continue
                        
                        # 提取CRICOS和學費
                        if header_indices.get('cricos') is not None and header_indices.get('tuition') is not None:
                            cricos_idx = header_indices['cricos']
                            tuition_idx = header_indices['tuition']
                            
                            if cricos_idx < len(row) and tuition_idx < len(row):
                                cricos = self.clean_text(row[cricos_idx]) if row[cricos_idx] else ""
                                tuition = self.clean_text(row[tuition_idx]) if row[tuition_idx] else ""
                                
                                if re.match(r'^[A-Za-z0-9]{7}$', cricos):
                                    # 處理學金額
                                    if tuition and '$' in tuition:
                                        value_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)', tuition)
                                        if value_match:
                                            try:
                                                tuition_value = float(value_match.group(1).replace(',', ''))
                                                cricos_tuition_map[cricos] = tuition_value
                                            except ValueError:
                                                pass
            
            return cricos_tuition_map


    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n澳洲聖母大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)\n')
