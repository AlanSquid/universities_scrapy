import scrapy
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from universities_scrapy.items import UniversityScrapyItem  
import re

class UnimelbSpiderSpider(scrapy.Spider):
    name = "unimelb_spider"
    allowed_domains = ["www.unimelb.edu.au", "study.unimelb.edu.au"]
    start_urls = ["https://study.unimelb.edu.au/find/?collection=find-a-course&profile=_default&query=%21showall&num_ranks=12&start_rank=1&f.Tabs%7CtypeCourse=Courses&f.Study+level%7CcourseStudyLevel=undergraduate"]
    course_detail_urls = []
    
    def start_requests(self):
        for url in self.start_urls:
            yield SeleniumRequest(
                url=url, 
                callback=self.parse, 
                wait_time=5,
                wait_until=lambda driver: WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-result__card.card.course")))
            )

    
    def parse(self, response):
        courses = response.css(".search-result__card.card.course")
        
        for course in courses:
            # 抓取課程名稱
            course_name = course.css(".card-header--wrapper h4::text").get()
            # 抓取課程網址
            course_url = course.css(".card-body a:nth-of-type(1)::attr(href)").get()
            if 'Bachelor' in course_name:
                # 將課程網址存入列表
                self.course_detail_urls.append(course_url)
            
        # 處理換頁
        next_relative_url = response.css('a.page-link.page-link--next::attr(href)').get()
        if next_relative_url is not None:
            next_url = response.urljoin(next_relative_url)
            # 換頁請求
            yield SeleniumRequest(
                url=next_url, 
                callback=self.parse, 
                wait_time=5,
                wait_until=EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".search-result__card.card.course"))
            )
            
        # 沒有下一頁後開始爬取各課程詳細資訊
        else:
            for course_url in self.course_detail_urls:
                driver = response.request.meta['driver']
                wait = WebDriverWait(driver, 10)
                driver.get(course_url)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".key-facts-section__main")))

                # 居住地要選擇International student
                residency = driver.find_element(By.CSS_SELECTOR, "span.residency--title").text.strip()
                
                # 如果不是International student，則點擊切換按鈕
                if residency != 'International student':
                    change_btn = driver.find_element(By.CSS_SELECTOR, "a.btn--toggle.btn--toggle-alt")
                    driver.execute_script("arguments[0].click();", change_btn)
                
                # 給scrapy解析頁面
                page = scrapy.Selector(text=driver.page_source)
                
                # 取得課程名稱
                course_name = page.css("#page-header::text").get().strip()

                # 取得學費
                tuition_fee = ''
                info = page.css(".key-facts-section__main")
                info_items = info.css('.key-facts-section__main--item')
                for item in info_items:
                    title = item.css('.key-facts-section__main--title::text').get().strip()
                    if 'Fees' in title:
                        tuition_fee_raw = item.css('.key-facts-section__main--value::text').get()
                        tuition_fee = self.extract_fee_range(tuition_fee_raw)
                    if "Duration" in title:
                        duration = item.css("div.key-facts-section__main--value::text").get()
                        duration = ", ".join([d.strip() for d in duration.split("/")])

                    if 'English' in title:
                        english_requirement_raw = item.css('.key-facts-section__main--value::text').get().strip()
                        english_requirement = self.extract_ielts_requirement(english_requirement_raw)
                        
                        
                if tuition_fee:
                    # 存入 UniversityScrapyItem
                    item = UniversityScrapyItem()
                    item['name'] = 'University of Melbourne'
                    item['ch_name'] = '墨爾本大學'
                    item['course_name'] = course_name
                    item['tuition_fee'] = tuition_fee
                    item['english_requirement'] = english_requirement
                    item['duration'] = duration
                    item['course_url'] = course_url
                    
                    yield item
                    
                    
                # 沒有學費的代表不開放國際生
                else:
                    print(f'{course_name}不開放國際生\n{course_url}')
                    self.course_detail_urls.remove(course_url)
                
                          
    # 提取學費範圍或單個金額
    def extract_fee_range(self, fee_string):
        # 匹配範圍金額的正則表達式
        range_pattern = re.compile(r'\$([\d,]+)-\$([\d,]+)')
        # 匹配單個金額的正則表達式
        single_pattern = re.compile(r'\$([\d,]+)')

        range_match = range_pattern.search(fee_string)
        if range_match:
            return f"{range_match.group(1).replace(',', '')}-{range_match.group(2).replace(',', '')}"
        
        single_match = single_pattern.search(fee_string)
        if single_match:
            return single_match.group(1).replace(',', '')

        return '' 
    
    # 提取英文門檻(IELTS)
    def extract_ielts_requirement(self, ielts_string):
        # 匹配帶有子分數的正則表達式
        pattern_with_bands = re.compile(r'IELTS (\d+(\.\d+)?) \(with no bands less than (\d+(\.\d+)?)\)')
        # 匹配没有子分數的正則表達式
        pattern_without_bands = re.compile(r'IELTS (\d+(\.\d+)?)')

        match_with_bands = pattern_with_bands.search(ielts_string)
        if match_with_bands:
            return f"IELTS {match_with_bands.group(1)} (單科不低於{match_with_bands.group(3)})"
        
        match_without_bands = pattern_without_bands.search(ielts_string)
        if match_without_bands:
            return f"IELTS {match_without_bands.group(1)}"

        return ''     

        
    def closed(self, reason):
        print(f'University of Melbourne 爬蟲結束，共{len(self.course_detail_urls)}個課程')