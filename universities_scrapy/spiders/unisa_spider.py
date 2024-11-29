import scrapy
from universities_scrapy.items import UniversityScrapyItem
import re

class UnisaSpiderSpider(scrapy.Spider):
    name = "unisa_spider"
    allowed_domains = ["www.unisa.edu.au", "www.search.unisa.edu.au", "www.i.unisa.edu.au/"]
    start_urls = ["https://search.unisa.edu.au/s/search.html?collection=study-search&query=&f.Tabs%7Ctab=Degrees+%26+Courses&f.Student+Type%7CpmpProgramsStudentType=International&f.Study+Type%7CstudyType=Degree&f.Level+of+study%7CfacetLevelStudy=Undergraduate"]
                  
    all_course_url = []

    def parse(self, response):
        cards = response.css(".search-result-block.small-margin-bottom.theme-background-white.search-result-degree")
        for card in cards: 
            url = card.css("h3 a::attr(href)").get()
            course_url = response.urljoin(url)
            self.all_course_url.append(course_url)
        next_page = None
        # 檢查下一頁
        next_page = response.css('a.page-num[rel="Next"]::attr(href)').get()
        if next_page:
            next_page_url = response.urljoin(next_page)
            yield response.follow(next_page_url, self.parse, dont_filter=True ) 
        else:
            for url in self.all_course_url:
                yield response.follow(url, self.page_parse, dont_filter=True)
    
    
    def page_parse(self, response):
        try:
            # 取得課程名稱
            course_name = response.css('.title-row h1::text').get().strip()    

            location = response.xpath(
                "//div[contains(@class, 'columns medium-4')]//span[contains(text(), 'Campus')]/../../..//a/span/text()"
            ).get()
            
            # 取得location
            if location is None:
                online = response.css("span.badge.small-margin-bottom::text").get()
                if online and "Online" in online:
                    location = 'online'
                else:
                    location = None
            
            # 取得duration
            duration = response.xpath("//span[contains(text(), 'Duration')]/ancestor::p/span/following-sibling::br/following-sibling::text()").get().strip()
            
            # 取得英文門檻
            english_info = response.xpath("//span[contains(text(), 'English Language Requirements')]/following-sibling::ul/li/text()").getall()
            pattern = r"IELTS total \[(\d+\.?\d*)\]|IELTS reading \[(\d+\.?\d*)\]|IELTS writing \[(\d+\.?\d*)\]|IELTS speaking \[(\d+\.?\d*)\]|IELTS listening \[(\d+\.?\d*)\]"
            total, reading, writing, speaking, listening = None, None, None, None, None
            for item in english_info:
                matches = re.findall(pattern, item)
                for match in matches:
                    if match[0]: total = match[0]
                    if match[1]: reading = match[1]  
                    if match[2]: writing = match[2]  
                    if match[3]: speaking = match[3]
                    if match[4]: listening = match[4] 

            parts = [f"IELTS {total}"] if total else []  
            if reading: parts.append(f"閱讀 {reading}")
            if writing: parts.append(f"寫作 {writing}")
            if speaking: parts.append(f"口說 {speaking}")
            if listening: parts.append(f"聽力 {listening}")
            english_requirement = f"{parts[0]} ({'，'.join(parts[1:])})" if len(parts) > 1 else parts[0] if parts else ""
            
            # 取得學費
            fees_info = response.xpath(
                "//div[contains(@class, 'icon-block-horizontal')]//span[contains(text(), 'Fees')]/following::span[contains(text(), 'AUD')]/text()"
            ).get()
            tuition_fee = None
            if fees_info:
                fees_info.strip()
                fees_numeric = re.search(r'(\d{1,3}(?:,\d{3})*)', fees_info)
                if fees_numeric:
                    tuition_fee = fees_numeric.group(1).replace(",", "")
                else:
                    tuition_fee = None


            university = UniversityScrapyItem()
            university['name'] = 'University of South Australia'
            university['ch_name'] = '南澳大學'
            university['course_name'] = course_name
            university['min_tuition_fee'] = tuition_fee
            university['english_requirement'] = english_requirement
            university['location'] = location
            university['duration'] = duration
            university['course_url'] = response.url
            yield university
        except Exception as e:
            self.logger.error(f"Error parsing page {response.url}: {e}")
            yield None 

    def closed(self, reason):    
        print(f'{self.name}爬蟲完成!\n南澳大學, 共有 {len(self.all_course_url)} 筆資料\n')