import scrapy
from universities_scrapy.items import UniversityScrapyItem 
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import re

class FederationSpider(scrapy.Spider):
    name = "federation_spider"
    allowed_domains = ["www.federation.edu.au"]
    # 網頁
    # start_urls = ["https://www.federation.edu.au/study/search/?sortQ=undefined&typeQ=search&keywordQ=&pageQ=0&isDomesticQ=false&LevelOfStudyQ=Undergraduate%2CPostgraduate"]
    
    # API
    start_urls = ["https://www.federation.edu.au/api/CourseApi/course-search?PageId=12&PageSize=20&PageNumber=1&Sort=undefined&Type=search&LevelOfStudy=Undergraduate&LevelOfStudy=Postgraduate&IsDomestic=false"]
    all_course_url = []
    page = 0

    def parse(self, response):
        json_response = response.json()
        totalPage = json_response["result"]["totalPage"]
        for item in json_response["result"]["items"]:
            course_name = item["header"]
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
            keywords = ["Bachelor of", "Master of"]
            if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                # print('跳過:',course_name)
                continue
            course_url = item["link"]["href"]
            self.all_course_url.append(course_url)
            duration_info = item["date"]
            duration_info = re.sub(r'<br />.*$', '', duration_info)
            if duration_info:
                duration_info = duration_info.strip()
                pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full-time"
                match = re.search(pattern, duration_info)
                if match:
                    duration = float(match.group(1))  # 提取匹配內容並轉換為 float
                else:
                    duration = None  # 如果沒有匹配到數字
            else:
                duration_info = None
 
            location = item["location"]
            yield SeleniumRequest(
                url=course_url,
                callback=self.page_parse,
                wait_time=10,
                wait_until=EC.presence_of_element_located((By.XPATH, '//button[contains(@class, "bg-tertiary")]')),
                dont_filter=True,
                # 設置 localStorage 並刷新頁面以使其重新渲染
                script='''window.localStorage.setItem('isDomestic', 'international');
                        window.location.reload();''',  # 設置完後重新載入頁面
                meta=dict(
                    duration_info = duration_info,
                    duration = duration,
                    location = location
                )
            )
        self.page += 1
        if totalPage > self.page:
            # print('page:',self.page)
            new_url = self.start_urls[0].replace(f"PageNumber=1", f"PageNumber={self.page + 1}")
            yield scrapy.Request(
                new_url,
                method="GET",
                callback=self.parse
            )

    def page_parse(self, response): 
        course_name = response.css("h1::text").get()    
        degree_level_id = None
        if "bachelor" in course_name.lower():
            degree_level_id = 1
        elif "master" in course_name.lower(): 
            degree_level_id = 2
        
        # 英文門檻
        eng_req_info = response.xpath('//header[text()="IELTS"]/following-sibling::div[contains(@class, "text-primary-cool-grey")]//text()').getall()
        eng_req_info = ''.join(eng_req_info).strip()
        if eng_req_info:
            # 移除 "or equivalent" 及其後面的所有文字
            eng_req_info = re.sub(r'or equivalent.*', 'or equivalent', eng_req_info, flags=re.IGNORECASE)
            eng_req_info = re.sub(r'OET with.*', 'OET with', eng_req_info, flags=re.IGNORECASE)

            # 匹配 IELTS 分數（允許 Overall、Academic、任意前綴等情況）
            match = re.search(r'IELTS.*?(\d+(\.\d+)?)', eng_req_info, re.IGNORECASE)

            if match:
                eng_req = float(match.group(1))
            else:
                eng_req = None
        else:
            eng_req = None
            eng_req_info = None


        fee_info = response.xpath('//section[@id="fees"]//p[contains(text(), "fee:")]/text()').get()

        if fee_info:
            fee_match = re.search(r'[\$\€\¥]\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', fee_info)
            if fee_match:
                fee = float(fee_match.group(1).replace(",", ""))  # 移除千位分隔符並轉換為浮點數
            else:
                fee = None
        else:
            fee = None

        university = UniversityScrapyItem()
        university['university_id'] = 37
        university['name'] = course_name
        university['min_fee'] = fee
        university['max_fee'] = fee
        university['campus'] = response.meta["location"]
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = response.meta["duration"]
        university['duration_info'] = response.meta["duration_info"]
        university['degree_level_id'] = degree_level_id
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n澳大利亞聯邦大學，共 {len(self.all_course_url) } 筆資料')
