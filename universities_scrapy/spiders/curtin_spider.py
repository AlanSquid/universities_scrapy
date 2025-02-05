import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.support.ui import WebDriverWait  # 用於設定智能等待機制   會在指定時間內持續檢查條件是否滿足
from universities_scrapy.items import UniversityScrapyItem  
from selenium.common.exceptions import TimeoutException 
import re


class CurtinSpider(scrapy.Spider):
    name = "curtin_spider"
    allowed_domains = ["www.curtin.edu.au"]
    start_urls = ["https://www.curtin.edu.au/study/search/?search_text=&study_level=undergraduate&category=degree&study_mode=on-campus","https://www.curtin.edu.au/study/search/?search_text=&study_level=postgraduate&category=master_c&study_mode=on-campus"]
    full_link_list=[]
    def parse(self, response):
        cards = response.css("div.search-card")
        for card in cards: 
            full_link = card.css("a::attr(href)").get()
            # name = card.css("a::text").get().strip()
            self.full_link_list.append(full_link)

        # # 檢查是否有下一頁
        next_page = response.css('a.search-pagination__next::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)       
        else:
            for link in self.full_link_list:
                yield SeleniumRequest(url=link, callback=self.page_parse, meta={'link': link})

    def page_parse(self, response):
            driver = response.meta['driver']
            link = response.meta['link'] 
            wait = WebDriverWait(driver, 10)
            try:
                driver.get(link)  # 進入課程的詳細頁面
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.offering-overview__hero__title")))
                switch_button = driver.find_elements(By.CSS_SELECTOR, ".utility__personalisation")
                # 判斷是否為 'INTERNATIONAL'，如果不是就需要切換成國際生
                span_text = switch_button[0].find_element(By.TAG_NAME, "span").get_attribute("innerText")
                if span_text != "INTERNATIONAL":
                    driver.execute_script("arguments[0].click();", switch_button[0])
                    # 等待按鈕可點擊
                    international_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='See international content']")))
                    driver.execute_script("arguments[0].click();", international_button)
                    wait.until(EC.visibility_of_any_elements_located((By.XPATH, "//h3[text()='International student indicative fees'] | //p[contains(text(), 'Fee information is not available for this course at this time')]")))
            except TimeoutException:
                # print("Element not found for this card.")
                return  # 結束當前方法，跳過當前卡片
    
            # 取得課程標題
            page = scrapy.Selector(text=driver.page_source)
            course_name = page.css('h1.offering-overview__hero__title::text').get().strip() 
            # name = re.sub(r'\b(master of|bachelor of)\b', '', course_name, flags=re.IGNORECASE).strip()
            degree_level = page.css('h2.offering-overview__hero__award::text').get().strip() 
            if (degree_level):
                if "Bachelor degree" in degree_level :
                    degree_level_id = 1
                elif "Master" in degree_level:
                    degree_level_id = 2
                else: 
                    degree_level_id = degree_level 
            else:
                degree_level_id = None 

            # 取得校區
            location_dt_elements = page.css("dt")
            if location_dt_elements:
                for dt in location_dt_elements:
                    if "Location" in dt.css("::text").get():  # 找到 <dt> 包含 "Location"
                        location_dd = dt.xpath("following-sibling::dd").get()  # 取得下一个 <dd>                    
                        
                        # 直接提取所有 <span> 的文本内容
                        spans = scrapy.Selector(text=location_dd).css("span::text").getall()
                        location_format = ', '.join(span.strip() for span in spans if span.strip())  
                        location_format = location_format.replace(',,', ',').strip(', ')
                        if location_format.endswith(','):
                            location_format = location_format[:-1].strip() 
                        break
            else:
                location_format = None

     
            # 取得 duration
            duration_selector = response.css("dd.details-duration::text").get()
            if duration_selector:
                duration_info = duration_selector.strip()

                # 匹配年和月的數字
                years_match = re.search(r'(\d+)\s*year', duration_info, re.IGNORECASE)
                months_match = re.search(r'(\d+)\s*month', duration_info, re.IGNORECASE)

                # 初始化年和月
                years = float(years_match.group(1)) if years_match else 0
                months = float(months_match.group(1)) if months_match else 0

                # 將年和月換算為小數的年份（1年=12個月）
                duration = years + (months / 12)
            else:
                duration_info = None
                duration = None

            # 取得英文門檻
            eng_req_info = None
            english_rows = page.css("div[data-applicant-type='english-proficiency'] div.english-table_row")

            # english_rows = page.css("div.english-table_row")
            overall_score = None
            individual_scores = []

            if english_rows:  
                for row in english_rows:
                    cols = row.css("p")
                    if cols and "Overall band score" in cols[0].css("::text").get():
                        overall_score = cols[1].css('::text').get().strip()
                    elif cols:
                        individual_scores.append(f"{cols[0].css('::text').get().strip()} {cols[1].css('::text').get().strip()}")

            if overall_score:
                eng_req = overall_score
                if individual_scores:
                    eng_req_info = f"IELTS {overall_score} ({', '.join(individual_scores)})"
                else:
                    eng_req_info = f"IELTS {overall_score}"
            else:
                eng_req_info = None
                eng_req = None
            # 取得費用
            tuition_fee_format = None
            if page.xpath("//div[contains(@class, 'fees-charges__box') and contains(@class, 'purple')]/p[contains(text(), 'Fee information is not available for this course at this time')]"):
                # print(f"{course_name} 沒有費用資訊")
                tuition_fee_format = None
            elif page.xpath("//h3[text()='International student indicative fees']"):
                fee_items = page.css("div.fees-charges__item--int")
                for item in fee_items:
                    if "Indicative year 1 fee" in item.css("h4.fees-charges__fee-title::text").get():
                        tuition_fee_format = ''.join(filter(str.isdigit, item.css("p.fees-charges__fee::text").get().strip()))
                        break

   
            university = UniversityScrapyItem()
            university['university_id'] = 39
            university['name'] = course_name  
            university['min_fee'] = tuition_fee_format
            university['max_fee'] = tuition_fee_format
            university['eng_req'] = eng_req
            university['eng_req_info'] = eng_req_info
            university['campus'] = location_format
            university['duration'] = duration
            university['duration_info'] = duration_info
            university['degree_level_id'] = degree_level_id
            university['course_url'] = link

            yield university
            
    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n科廷大學，共{len(self.full_link_list)}筆資料\n')
