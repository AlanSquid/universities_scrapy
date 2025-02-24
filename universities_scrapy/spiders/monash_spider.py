import re
import time
import scrapy
import cloudscraper
from scrapy.http import HtmlResponse
from scrapy_selenium import SeleniumRequest
from universities_scrapy.items import UniversityScrapyItem


class MonashSpiderSpider(scrapy.Spider):
    name = "monash_spider"
    allowed_domains = ["www.monash.edu", "www.cloudflare.com"]
    start_urls = [
        "https://www.monash.edu/study/courses/find-a-course?collection=monash~sp-find-a-course&f.Study+type%7CcourseStudyType=Full+time&f.Course+Level+Undergrad%7CcourseUndergradLevel=Undergraduate+single+degrees",
        "https://www.monash.edu/study/courses/find-a-course?f.Tabs%7Cgraduate=Graduate&collection=monash~sp-find-a-course&f.Study+type%7CcourseStudyType=Full+time"
    ]
    scraper = cloudscraper.create_scraper() # 初始化一個可以發送 HTTP 請求的 Scraper 實例，並設置一些預設的request header（如 User-Agent），使得請求看起來像是來自真實用戶的瀏覽器
    all_course_url = []
    non_international_num = 0
    start_time = time.time()

    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(url=url, callback=self.parse)


    def parse(self, response):
        url = response.url
        response = self.url_transfer_to_scrapy_response(url)
        all_course_cards = response.css('div.box-featured')
        for card in all_course_cards:
            # 首先確認此科系有給國際生
            course_url_international = card.css('a.box-featured__heading-link::attr(title)').get()
            # course_url = card.css('a.box-featured__heading-link::attr(href)').get()
            # course_url_international = course_url + "?international=true"
            # if not any(keyword in course_url for keyword in ["professional-psychology", "genome-analytics", "educational-and-developmental-psychology"]):
            #     continue
            # 取得科系名稱
            course_name = card.css('h2.box-featured__heading::text').get()
            course_level = card.css('span.box-featured__level::text').get()
            course_name = course_level+ " " + course_name
            # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
            skip_keywords = ["Doctorate", "honours", "Graduate Certificate", "Diploma", "Research master"]
            keywords = ["Bachelor", "Master", "Doctor", "master", "bachelor"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or \
                (sum(course_name.count(keyword) for keyword in keywords) >= 2 or not any(keyword in course_name for keyword in keywords)):
                    self.non_international_num += 1 
                    # print('跳過:',course_name)
                    continue
            
            course_response = self.url_transfer_to_scrapy_response(course_url_international)
            paragraph = course_response.css('p::text').getall()  # 擷取所有的 <p> 標籤中的文字
            
            if any("Course offered to domestic students only" in p for p in paragraph):
                self.non_international_num += 1
                continue
            else:
                if course_url_international not in self.all_course_url:
                    self.all_course_url.append(course_url_international)
            
            degree_level_id = None        
            if "bachelor" in course_name.lower():
                degree_level_id = 1
            elif "master" in course_name.lower(): 
                degree_level_id = 2        

            # 費用
            # try:
            min_fee = max_fee = None 
            fee_element = course_response.css('h4:contains("International fee") + p + p strong::text').get()
            if fee_element:
                tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()
            else:                    
                fee_element_all = course_response.css('h4:contains("International fee") + p + ul li strong::text').getall()
                if fee_element_all:
                    # 轉換費用為數字類型，過濾無效值
                    tuition_fees = [
                        float(fee.replace("A$", "").replace("$", "").replace(",", "").strip())
                        for fee in fee_element_all if fee.replace("A$", "").replace("$", "").replace(",", "").strip().isdigit()
                    ]
                    if tuition_fees:  # 確保列表不為空
                        min_fee = min(tuition_fees)
                        max_fee = max(tuition_fees)
                # else:
                #     fee_element = course_response.css('h4:contains("Full fee") + p + ul li strong::text').get()
                #     tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()

            # except:
            #     # print(f"Fee information not found: {course_url_international}")
            
            # 英文門檻
            # eng_IELTS = course_response.css('div.flex-row.first-row.first::text').get()
            # if eng_IELTS:
            #     eng_score = course_response.css('div.flex-row.first-row[role="cell"]::text').get()
            #     IELTS_score_result = eng_IELTS + ' ' + eng_score
            # else:
            #     # 目標：從td中獲取 "IELTS (Academic)" 和分數
            #     IELTS_td = course_response.css('h4:contains("English entry requirements") + p + div table tbody tr td')  # 選擇對應的td

            #     # 提取IELTS學術的分數
            #     strong_text = IELTS_td.css('strong::text').get()
            #     score_text = IELTS_td.css('td::text').get()
            #     if strong_text:
            #         # 使用正則表達式找到 "IELTS (Academic)" 前的分數
            #         match = re.search(r'(\d+(\.\d+)?)', score_text)

            #         if match:
            #             IELTS_score_result = f"{strong_text.strip()} {match.group(1)}"
            #     #     else:
            #     #         print("No match found.")
            #     # else:
            #     #     print(f"IELTS requirement not found: {course_url_international}")
            
            # 找到 "English entry requirements" 的標題
            english_requirements1 = course_response.css("div.font-bold.text-bullet-grey.py-4:contains('English entry requirements')")
            english_requirements2 = course_response.css("div#min-entry-requirements h4:contains('English entry requirements')")
            eng_req = None
            eng_req_info = None
            if english_requirements1:
                # 取得 "English entry requirements" 之後的兄弟元素
                ielts_container = english_requirements1.xpath("following-sibling::div[1]")
                eng_req = ielts_container.css("div.text-3xl.font-bold::text").get()
                eng_req = eng_req.strip() if eng_req else None
                eng_req_info = ielts_container.css("div.py-2.font-jsans::text").get()
                eng_req_info = eng_req_info.strip() if eng_req_info else None            
            elif english_requirements2:
                # 找到 h4 英文要求標題後的第一個 table
                ielts_container = english_requirements2.xpath("following-sibling::table[1] | following-sibling::div[1]//table[1]")
                # 嘗試獲取 IELTS 相關資訊，考慮 <br> 分隔
                ielts_texts = ielts_container.xpath(".//td/strong[contains(text(), 'IELTS')]/parent::td//text()").getall()
                # ielts_texts = ielts_container.xpath(".//td[strong[contains(text(), 'IELTS')]]/text()").getall()

                # 清理資料
                ielts_texts = [text.strip().lstrip(': ') for text in ielts_texts if text.strip()]
                for text in ielts_texts:
                    match = re.search(r'(\d+\.\d+)\s*Overall score', text)
                    if match:
                        eng_req = match.group(1)
                        eng_req_info = text
                        break  # 找到第一個 IELTS 總分即停止

            # 地點
            location_th = course_response.css('th').xpath(".//h5[text()='Location']")
            location_td = location_th.xpath('./ancestor::th/following-sibling::td')
            location_list_items = location_td.css('ul li::text').getall()
            locations = []
            for item in location_list_items:
                clean_item = re.sub(r':.*', '', item)  # 只保留冒號前的地點
                clean_item = re.sub(r'On-campus at ', '', clean_item)  # 移除 "On-campus at "
                locations.append(clean_item.strip())

            location = ', '.join([d.strip() for d in locations])
             # 防止空字串
            if not location:
                location = None

            # 學習期間
            duration_th = course_response.css('th').xpath(".//h5[text()='Duration']")
            duration_td = duration_th.xpath('./ancestor::th/following-sibling::td')
            duration_list_items = duration_td.css('ul li::text').getall()
            
            # 若有用li列表
            if duration_list_items:
                durations = []
                for item in duration_list_items:
                    clean_item = re.sub(r'\s+', ' ', item.strip())
                    durations.append(clean_item)
                duration = ', '.join([d.strip() for d in durations])
            
            # 若直接在td的部分顯示詳細的學制說明
            else:
                raw_text = duration_td.css('::text').getall()
                combined_text = ' '.join(raw_text).strip()  # 合併並清理文字
                clean_item = re.sub(r'\s+', ' ', combined_text)
                duration = clean_item

            
            # 先將 'or' 替換成 ','
            normalized_duration = re.sub(r'\s+or\s+', ', ', duration)

            # 正則匹配所有數字 (整數或小數) 及 "years"
            matches = re.findall(r'(\d+(?:\.\d+)?)\s+years?', normalized_duration)

            # 取得所有數字中的最小值
            if matches:
                duration_detail = min(float(match) for match in matches)
            else:
                duration_detail = None  

            matches = re.findall(r'(\d+(?:\.\d+)?)\s+years?', duration)
            if matches:
                duration_detail= min(float(match) for match in matches)
            else:
                # 如果沒有 "years"，則檢查 "months"
                month_match = re.search(r'(\d+(?:\.\d+)?)\s+months?', duration)
                if month_match:
                    months = float(month_match.group(1))
                    duration_detail = months / 12  # 轉換成年數
                else:
                    duration_detail = None  # 若無匹配，返回 None            
                    print(duration)
            if duration:
                if "See entry requirements" in duration:
                    # duration = duration.replace("See entry requirements,", "").strip()
                    duration = re.sub(r"\s*See entry requirements[\s\u200b]*\.*", "", duration).strip()

                # 處理包含有accelerated這類型的說明
                # "This course is equivalent to 4.25 years of full-time study and may be accelerated to complete in 4 years. Part-time study is also available."
                # if "accelerated" in clean_item:
                #     result = []
                #     words = clean_item.split()
                #     # 提取 full-time 部分
                #     if "full-time" in clean_item:
                #         for i, word in enumerate(words):
                #             if word == "full-time":
                #                 # 從 full-time 向前搜尋最近的數字和 years
                #                 for j in range(i - 1, -1, -1):
                #                     if re.match(r'\d+(\.\d+)?', words[j]):  # 確保是數字
                #                         full_time_years = f"{words[j]} years (full-time)"
                #                         result.append(full_time_years)
                #                         break
                #                 break

                #     # 提取 accelerated 部分
                #     for i, word in enumerate(words):
                #         if "accelerated" in word:
                #             # 往後找 "complete in" 的數字和 "years"
                #             for j in range(i + 1, len(words)):
                #                 if "years" in words[j]:
                #                     accelerated_years = f"{words[j - 1]} years (accelerated)"
                #                     result.append(accelerated_years)
                #                     break
                #             break

                #     # 提取 Part-time 部分
                #     if "Part-time" in clean_item:
                #         part_time_phrase = "Part-time study is also available"
                #         result.append(part_time_phrase)

                #     # 將結果合併成字串
                #     duration = ', '.join(result)
    
                # # 沒有accelerated類型的說明
                # # 5 years (full time). This consists of 3 years in the Bachelor of Architectural Design, and 2 years in the Master of Architecture. To qualify as a registered architect, you need to complete the Master of Architecture and undertake two years of professional practice.
                # else:
                #     matches = re.findall(r'(\d+(?:\.\d+)?)\s+years?\s+\((full|part-time)\)', clean_item, re.IGNORECASE)

                #     if matches:
                #         durations = []
                #         for match in matches:
                #             years, mode = match
                #             durations.append(f"{years} years ({mode})")
                #         duration = ', '.join(durations)
                #     else:
                #         # 如果沒有匹配，保存整段說明作為備選內容
                #         # 嘗試擷取 "X or Y years full-time" 格式
                #         match = re.search(r'(\d+(?:\.\d+)?\s+or\s+\d+(?:\.\d+)?)\s+years?\s+(full-time)', clean_item, re.IGNORECASE)
                #         if match:
                #             duration = f"{match.group(1)} years {match.group(2)}"
                #         else:
                #             duration = clean_item

                #     # 去掉(time)之後的所有字串，如果存在
                #     duration = re.sub(r'\(full time\).*', '(full time)', duration, flags=re.IGNORECASE)
            # if duration:
            #     duration = duration.strip()
            #     match = re.search(r'\d+(\.\d+)?', duration)  # 使用正則表達式查找數字
            #     if match:
            #         duration_detail = float(match.group())  # 提取匹配內容並轉換為 float
            #     else:
            #         duration_detail = None  # 如果沒有匹配到數字
            university = UniversityScrapyItem()
            university['university_id'] = 31
            university['name'] = course_name
            university['min_fee'] = min_fee if min_fee is not None else tuition_fee
            university['max_fee'] = max_fee if max_fee is not None else tuition_fee
            university['eng_req'] = eng_req
            university['eng_req_info'] = eng_req_info
            university['campus'] = location
            university['duration'] = duration_detail
            university['duration_info'] = duration
            university['degree_level_id'] = degree_level_id
            university['course_url'] = course_url_international
            yield university
                
    def url_transfer_to_scrapy_response(self, url):
        response = self.scraper.get(url) # response 會包含網站的 HTML 內容，以及其他有關這次請求的元數據（如狀態碼、請求頭等）。
        scrapy_response = HtmlResponse(
            url=url, 
            body=response.text, 
            encoding="utf-8", 
        )
        return scrapy_response
    
    def close(self):
        print(f'\n{self.name}爬蟲完畢！\n蒙納許大學，共{len(self.all_course_url)}筆資料')
        # print(f'有{self.non_international_num}個科系，不提供給國際生\n')
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'{elapsed_time:.2f}', '秒')