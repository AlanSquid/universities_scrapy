import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UwaSpider(scrapy.Spider):
    name = "uwa_spider"
    allowed_domains = ["www.uwa.edu.au", "www.search.uwa.edu.au"]
    start_urls = ["https://www.search.uwa.edu.au/s/search.html?f.Tabs%7Ccourses=Courses&query=&f.International%7Cinternational=Available+to+International+Students&collection=uwa%7Esp-search"]

    full_data=[]
    def parse(self, response):
        cards = response.css("div.listing-item__content")
        for card in cards: 
            url = card.css("a::attr(data-live-url)").get()
            course_name = card.css("h3.listing-item__title::text").get().strip()
           
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctor of", "Honours", "Online", "Graduate Certificate", "Diploma"]
            keywords = ["Bachelor of", "Master of", "Doctor of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue

            # 刪除 master of 和 bachelor of
            # name = re.sub(r'\b(master of|bachelor of)\b', '', course_name, flags=re.IGNORECASE).strip()
         
            campus = card.css("dt:contains('Location:') + dd::text").get()
            self.full_data.append({
                'url':url,
                'course_name':course_name,
                'campus':campus
            })

        # 檢查下一頁
        next_page = response.css('a.pagination__link[aria-label="Next page"]::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)       
        else:
            # print(f'共有 {len(self.full_data)} 筆資料')
            for data in self.full_data[:10]:
                yield response.follow(data['url'], self.page_parse, meta={'campus': data['campus'],'course_name':data['course_name']})

    def normalize_duration(self, duration):
        # 如果字串為空或無效，返回 None
        if not duration:
            return None

        # 處理 "Three years" -> "3 years"
        duration = re.sub(r'\b(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\b', 
                        lambda x: str({'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5, 
                                        'Six': 6, 'Seven': 7, 'Eight': 8, 'Nine': 9, 'Ten': 10}[x.group(0)]), 
                        duration, flags=re.IGNORECASE)

        # 處理區間，例如 "4-8 months" -> "0.33 years"（取最小值）
        duration = re.sub(r'(\d+)\s*[-to]\s*(\d+)\s*months?', 
                        lambda m: str(min(int(m.group(1)), int(m.group(2))) / 12) + " years", 
                        duration)

        # 處理單個月份 "months" -> "years" 轉換
        duration = re.sub(r'(\d+)\s*months?', 
                        lambda m: str(int(m.group(1)) / 12) + " years", 
                        duration)

        # 處理區間，例如 "1.5-2 years" -> "1.5 years"（取較小的數字）
        duration = re.sub(r'(\d+(\.\d+)?)\s*[-to]\s*(\d+(\.\d+)?)\s*years?', 
                        lambda m: str(min(float(m.group(1)), float(m.group(3)))), duration)

        # 去除 [Hons]、(BSc) 或其他不需要的部分
        duration = re.sub(r'\[.*?\]|\(.*?\)', '', duration)

        # 去除 "full-time" 和 "part-time" 並根據情況處理
        duration = re.sub(r'\b(part-time|full-time)\b', '', duration)

        # 處理 "semester" 轉換為 0.5 年
        duration = re.sub(r'\bsemester\b', '0.5 years', duration)

        # 清除其他可能的標點符號和多餘空白
        duration = re.sub(r'[^\d.]+', ' ', duration).strip()

        # 如果處理後只剩下數字，則進行提取
        durations = re.findall(r'(\d+\.?\d*)', duration)

        # 如果沒有找到年份，返回 None
        if not durations:
            return None

        # 將所有的年數轉換為浮動數字（浮點數）
        durations = [float(d) for d in durations]

        # 選擇最小的年份（你可以根據需求選擇最小值或其他邏輯）
        min_duration = min(durations)

        # 轉換為整數（如果沒有小數部分）或保留小數（如果有小數部分）
        if min_duration.is_integer():
            return int(min_duration)  # 沒有小數部分，返回整數
        else:
            return round(min_duration, 2)  # 有小數部分，保留兩位小數
    
    
    def page_parse(self, response):
        #取得課程名稱
        # course_name = response.css('h1.course-header-module-title::text').get()

        # 取得學費
        international_fees = response.css('div.segment-info[data-segment-filter="international"]')
        degree_level = response.css('div.course-header-module-titles h2::text').get()
        if "Undergraduate" in degree_level :
            degree_level_id=1
        elif "Postgraduate" in degree_level:
            degree_level_id=2

        # 檢查是否有 "2025" 的學費資訊
        fee_2025 = international_fees.xpath(
            './/div[contains(@class, "card-details-label") and contains(text(), "2025")]/following-sibling::div[contains(@class, "card-details-value")]/text()'
        ).get()
        if fee_2025:
            fee_2025 = fee_2025.strip()
            fee_2025 = float(fee_2025.replace('$', '').replace(',', ''))
            if fee_2025.is_integer():
                fee_2025 = int(fee_2025)  # 沒有小數部分，轉換為整數
            else:
                fee_2025 = round(fee_2025, 2)  # 有小數部分，保留兩位小數

        # 提取 "English competency" 部分的所有段落
        admission_requirement = response.css('div')
    
        english_card = admission_requirement.css('div.course-detail.card').xpath(
            './/h3[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "english competency") or '
            'contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "english language requirements")]/following-sibling::div[@class="card-container"]'
        )
        paragraphs = english_card.css('div.card-content.rich-text-content p::text').getall()
        lists = english_card.css('div.card-content.rich-text-content ul li::text').getall()

        full_text = " ".join(paragraphs + lists).strip()
        
        pattern = re.compile(
            r"(?i)"  # 忽略大小寫
            r"(?:minimum\s+score\s+of\s+(\d+\.?\d*)\s+overall\s+with\s+at\s+least\s+(\d+\.?\d*)\s+in\s+each\s+section)|"
            r"(?:minimum\s+overall\s+ielts\s+score\s+(?:of\s+)?(\d+\.?\d*)?,?\s+with\s+no\s+band\s+less\s+than\s+(\d+\.?\d*))|"
            r"(?:applicants\s+presenting\s+with\s+the\s+ielts\s+academic\s+require\s+an\s+overall\s+score\s+of\s+at\s+least\s+(\d+\.?\d*),?\s+"
            r"a\s+minimum\s+score\s+of\s+(\d+\.?\d*)\s+in\s+the\s+reading\s+and\s+writing\s+bands,\s+and\s+a\s+minimum\s+score\s+of\s+(\d+\.?\d*)\s+"
            r"in\s+the\s+listening\s+and\s+speaking\s+bands)|"
            r"(?:a\s+valid\s+ielts\s+academic\s+overall\s+score\s+of\s+at\s+least\s+(\d+\.?\d*),?\s+"
            r"a\s+minimum\s+score\s+of\s+(\d+\.?\d*)\s+in\s+the\s+reading\s+and\s+writing\s+bands,\s+"
            r"and\s+a\s+minimum\s+score\s+of\s+(\d+\.?\d*)\s+in\s+the\s+listening\s+and\s+speaking\s+bands)|"
            r"(?:applicants\s+presenting\s+with\s+the\s+ielts\s+academic\s+require\s+an\s+overall\s+score\s+of\s+at\s+least\s+(\d+\.?\d*)\s+"
            r"and\s+no\s+band\s+less\s+than\s+(\d+\.?\d*))"
        )
       
        # 確保 full_text 不是 None
        if full_text:
            match = pattern.search(full_text)
        else:
            match = None

        if match:
            if match.group(1) and match.group(2):  # 情況 1: 總分與單科要求
                total_score = match.group(1)
                single_band_score = match.group(2)
                target_paragraph = f"IELTS {total_score} (單科不低於 {single_band_score})"
            elif match.group(3) and match.group(4):  # 情況 2: 總分與單科要求
                total_score = match.group(3)
                single_band_score = match.group(4)
                target_paragraph = f"IELTS {total_score} (單科不低於 {single_band_score})"
            elif match.group(5) and match.group(6) and match.group(7):  # 情況 3: 不同技能的分數要求
                total_score = match.group(5)
                reading_writing_score = match.group(6)
                listening_speaking_score = match.group(7)
                target_paragraph = (f"IELTS {total_score} (閱讀和寫作單項不低於 {reading_writing_score}，"
                                    f"聽力和口語不低於 {listening_speaking_score})")
            elif match.group(8) and match.group(9) and match.group(10):  # 情況 4:不同技能的分數要求 另一種寫法
                total_score = match.group(8)
                reading_writing_score = match.group(9)
                listening_speaking_score = match.group(10)
                target_paragraph = (f"IELTS {total_score} (閱讀和寫作不低於 {reading_writing_score}，"
                                    f"聽力和口語不低於 {listening_speaking_score})")
            elif match.group(11) and match.group(12):  # 情況 5: 總分與單科要求
                total_score = match.group(11)
                single_band_score = match.group(12)
                target_paragraph = f"IELTS {total_score} (單科不低於 {single_band_score})"
            else:
                total_score = None
                target_paragraph = None
        else:
            total_score = None
            target_paragraph = None

        # 取得duration
        course_details = response.css('div#course-details')
        duration_info = course_details.xpath(
           './/div[contains(@class, "card-details-dynamic")]//div[re:match(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "full time/part time duration", "i")]/following-sibling::div[@class="card-details-value"]//li/text()'
        ).get()

        if duration_info:
            duration_info = duration_info.replace('\n', ' ').strip()
        
        duration = self.normalize_duration(duration_info)
       
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university['university_id'] = 42
        university['name'] = response.meta.get('course_name')
        university['min_fee'] = fee_2025
        university['max_fee'] = fee_2025
        university['campus'] =  response.meta.get('campus')
        university['eng_req'] = total_score
        university['eng_req_info'] = target_paragraph
        university['duration'] = duration
        university['duration_info'] = duration_info
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n西澳大學，共{len(self.full_data)}筆資料\n')
