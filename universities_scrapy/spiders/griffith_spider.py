import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem  
from selenium.common.exceptions import TimeoutException 
import re

class GriffithSpider(scrapy.Spider):
    name = "griffith_spider"
    allowed_domains = ["www.griffith.edu.au"]
    start_urls = ["https://www.griffith.edu.au/"]
    all_course_url=[]
    except_count = 0
    

    def start_requests(self):
        url = "https://www.griffith.edu.au/study/degrees?academicCareerCode=ugrd&academicCareerCode=pgrd&degreeType=single&studentType=international"
        yield SeleniumRequest(url=url, callback=self.parse)

    def parse(self, response):
        driver = response.meta['driver']
        wait = WebDriverWait(driver, 10) 

        # 滾到最底部
        self.scroll_to_bottom(driver) 

        # 等待資料加載完成
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.result.card.trim")))

        # 獲取頁面內容並轉換為 Scrapy 的 Selector 對象
        page = scrapy.Selector(text=driver.page_source)
        cards = page.css("div.result.card.trim")

        for card in cards:
            # 提取每個card的url
            course_url = card.css("div.degree-link-wrapper p.degree a::attr(href)").get()
            title = card.css("p.degree-prefix::text").get()
            course_name = card.css("div.degree-link-wrapper p.degree a::text").get().strip()
            # 跳過雙學位, Honours, Graduate Certificate, Diploma
            skip_keywords = ["Doctor", "Honours", "Graduate Certificate", "Diploma"]
            if title is None:
                title = ""
            if not course_name or any(keyword in title for keyword in skip_keywords) or any(keyword in course_name for keyword in skip_keywords):
                continue
            if course_url:
                full_link = response.urljoin(course_url)
                driver.get(full_link)  # 確保獲取最新的頁面

                try:
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "dt.info-group-title.campus + div dd")))
                except TimeoutException:
                    # print("not found:",response.url)
                    continue  
                self.all_course_url.append(course_url)

                course_page = scrapy.Selector(text=driver.page_source)

                #取得校區             
                degree_level_id = None
                degree_level =course_page.css("div.banner-title p::text").get()
                if "Bachelor of" in degree_level:
                    degree_level_id = 1
                elif "Master of" in degree_level: 
                    degree_level_id = 2
                    
                location_list = course_page.css("dt.info-group-title.campus + div dd::text").getall()
                location_format = ', '.join([location.strip() for location in location_list]) if location_list else None
                if location_format.lower() == "online":
                    self.except_count += 1
                    continue                
        
                #取得ielts要求
                eng_req_info = course_page.css("dl.info-group.entry-requirement-group dd .badge *::text").getall()
                if eng_req_info:
                    eng_req_info = " ".join(eng_req_info).strip() 
                    eng_req_info = re.sub(r"\s+", " ", eng_req_info)  
                    match = re.search(r'\d+(\.\d+)?', eng_req_info)
                    if match:
                        eng_req = match.group()  
                    else:
                        eng_req = None

                else:
                    eng_req = None
                    eng_req_info = None
                
                # 取得學費
                tuition_fee_elements = course_page.css("dl dd::text").getall()
                tuition_fee = None
                for fee in tuition_fee_elements:
                    fee_text = fee.strip()
                    if "$" in fee_text and "per year" in fee_text:
                        tuition_fee = int(
                            fee_text.replace('$', '')
                            .replace(' per year', '')
                            .replace(',', '')
                        )
                        break
                # 取得duration
                duration_element = course_page.css("dt.info-group-title.duration + div dd *::text").getall()
                duration_raw = " ".join([d.strip() for d in duration_element]) if duration_element else None
                duration = None
                duration_info = None
                if duration_raw:
                    # 清理掉\xa0字符和多餘的空格
                    duration_info = duration_raw.replace('\xa0', ' ').strip()

                    # 提取包含 'year' 和 'part-time' 或 'full-time' 的數字部分
                    match = re.search(r'(\d+(\.\d+)?)\s+year\s*s?\s*(full-time|part-time)', duration_info)
                    
                    if match:
                        # 's' 前面沒有空格，並且加上 'years'或 'year'
                        duration = match.group(1)
                        year_label = "year" if duration == "1" else "years" 
                        duration_info = f"{duration} {year_label} {match.group(3)}"     

                # 把資料存入 university Item
                university = UniversityScrapyItem()
                university['university_name'] = "Griffith University"
                university['name'] = course_name
                university['min_fee'] = tuition_fee
                university['max_fee'] = tuition_fee
                university['eng_req'] = eng_req
                university['eng_req_info'] = eng_req_info
                university['campus'] = location_format
                university['duration'] = duration
                university['duration_info'] = duration_info
                university['degree_level_id'] = degree_level_id
                university['course_url'] = full_link

                yield university
    def close(self):
        print(f'{self.name}爬蟲完畢！\n格里菲斯大學， 共有 {len(self.all_course_url) - self.except_count}筆資料\n')                


    def scroll_to_bottom(self, driver):
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            # 滾動到頁面底部
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 等待頁面加載
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break  # 如果頁面高度不變，表示已經滾動到底部，停止滾動
            last_height = new_height
