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
        "https://www.monash.edu/study/courses/find-a-course?country=&country=&country=&country=AU&country=AU&country=AU&collection=monash~sp-find-a-course"
    ]
    scraper = cloudscraper.create_scraper() # 初始化一個可以發送 HTTP 請求的 Scraper 實例，並設置一些預設的request header（如 User-Agent），使得請求看起來像是來自真實用戶的瀏覽器
    all_course_url = []
    non_international_num = 0
    start_time = time.time()

    def start_requests(self):
        url = self.start_urls[0]
        yield SeleniumRequest(url=url, callback=self.parse)
        
    def parse(self, response):
        url = response.url
        response = self.url_transfer_to_scrapy_response(url)
        all_course_cards = response.css('div.box-featured')
        
        for card in all_course_cards:
            # 首先確認此科系有給國際生
            course_url = card.css('a.box-featured__heading-link::attr(href)').get()
            course_url_international = course_url + "?international=true"
            course_response = self.url_transfer_to_scrapy_response(course_url_international)


            # 取得科系名稱
            course_name = card.css('h2.box-featured__heading::text').get()
            course_level = card.css('span.box-featured__level::text').get()
            course_name = course_name + " - " + course_level
            paragraph = course_response.css('p::text').getall()  # 擷取所有的 <p> 標籤中的文字
            
            if any("Course offered to domestic students only" in p for p in paragraph) or 'Diploma' in course_name:
                self.non_international_num += 1
                continue
            else:
                if course_url_international not in self.all_course_url:
                    self.all_course_url.append(course_url_international)
            
            # 在course_response進一步找資料
            
            # 費用
            # try:
            fee_url = course_url_international + "#application-fees"
            fee_response = self.url_transfer_to_scrapy_response(fee_url)
            fee_element = fee_response.css('h4:contains("International fee") + p + p strong::text').get()
            if fee_element:
                tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()
            else:
                fee_element = fee_response.css('h4:contains("International fee") + p + ul li strong::text').get()
                if fee_element:
                    tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()
                else:
                    fee_element = fee_response.css('h4:contains("Full fee") + p + ul li strong::text').get()
                    tuition_fee = fee_element.replace("A$", "").replace(",", "").strip()
            # except:
            #     # print(f"Fee information not found: {course_url_international}")
            
            # 英文門檻
            eng_req_url = course_url_international + "#entry-requirements-2"
            eng_response = self.url_transfer_to_scrapy_response(eng_req_url)
            eng_IELTS = eng_response.css('div.flex-row.first-row.first::text').get()
            if eng_IELTS:
                eng_score = eng_response.css('div.flex-row.first-row[role="cell"]::text').get()
                IELTS_score_result = eng_IELTS + ' ' + eng_score
            else:
                # 目標：從td中獲取 "IELTS (Academic)" 和分數
                IELTS_td = eng_response.css('h4:contains("English entry requirements") + p + div table tbody tr td')  # 選擇對應的td

                # 提取IELTS學術的分數
                strong_text = IELTS_td.css('strong::text').get()
                score_text = IELTS_td.css('td::text').get()
                if strong_text:
                    # 使用正則表達式找到 "IELTS (Academic)" 前的分數
                    match = re.search(r'(\d+(\.\d+)?)', score_text)

                    if match:
                        IELTS_score_result = f"{strong_text.strip()} {match.group(1)}"
                #     else:
                #         print("No match found.")
                # else:
                #     print(f"IELTS requirement not found: {course_url_international}")
            
            # 地點
            location_th = course_response.css('th').xpath(".//h5[text()='Location']")
            location_td = location_th.xpath('./ancestor::th/following-sibling::td')
            location_list_items = location_td.css('ul li::text').getall()
            locations = []
            for item in location_list_items:
                clean_item = re.sub(r'\s+', ' ', item.strip())
                clean_item = clean_item.replace('On-campus at ', '')
                locations.append(clean_item)
            location = ', '.join([d.strip() for d in locations])
            
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
                
                # 處理包含有accelerated這類型的說明
                # "This course is equivalent to 4.25 years of full-time study and may be accelerated to complete in 4 years. Part-time study is also available."
                if "accelerated" in clean_item:
                    result = []
                    words = clean_item.split()

                    # 提取 full-time 部分
                    if "full-time" in clean_item:
                        for i, word in enumerate(words):
                            if word == "full-time":
                                # 從 full-time 向前搜尋最近的數字和 years
                                for j in range(i - 1, -1, -1):
                                    if re.match(r'\d+(\.\d+)?', words[j]):  # 確保是數字
                                        full_time_years = f"{words[j]} years (full-time)"
                                        result.append(full_time_years)
                                        break
                                break

                    # 提取 accelerated 部分
                    for i, word in enumerate(words):
                        if "accelerated" in word:
                            # 往後找 "complete in" 的數字和 "years"
                            for j in range(i + 1, len(words)):
                                if "years" in words[j]:
                                    accelerated_years = f"{words[j - 1]} years (accelerated)"
                                    result.append(accelerated_years)
                                    break
                            break

                    # 提取 Part-time 部分
                    if "Part-time" in clean_item:
                        part_time_phrase = "Part-time study is also available"
                        result.append(part_time_phrase)

                    # 將結果合併成字串
                    duration = ', '.join(result)
    
                # 沒有accelerated類型的說明
                # 5 years (full time). This consists of 3 years in the Bachelor of Architectural Design, and 2 years in the Master of Architecture. To qualify as a registered architect, you need to complete the Master of Architecture and undertake two years of professional practice.
                else:
                    matches = re.findall(r'(\d+(?:\.\d+)?)\s+years?\s+\((full|part-time)\)', clean_item, re.IGNORECASE)

                    if matches:
                        durations = []
                        for match in matches:
                            years, mode = match
                            durations.append(f"{years} years ({mode})")
                        duration = ', '.join(durations)
                    else:
                        # 如果沒有匹配，保存整段說明作為備選內容
                        duration = clean_item

                    # 去掉(time)之後的所有字串，如果存在
                    duration = re.sub(r'\(full time\).*', '(full time)', duration, flags=re.IGNORECASE)

            university = UniversityScrapyItem()
            university['name'] = "Monash University"
            university['ch_name'] = "蒙納許大學"
            university['course_name'] = course_name
            university['min_tuition_fee'] = tuition_fee
            university['english_requirement'] = IELTS_score_result
            university['location'] = location
            university['course_url'] = course_url_international
            university['duration'] = duration
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
        print(f'\n{self.name}爬蟲完畢！\n蒙納許大學，共{len(self.all_course_url) + self.non_international_num}筆資料')
        print(f'其中有{self.non_international_num}個科系，不提供給國際生\n')
        # end_time = time.time()
        # elapsed_time = end_time - self.start_time
        # print(f'{elapsed_time:.2f}', '秒')