import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import re

class UwaSpider(scrapy.Spider):
    name = "uwa_spider"
    allowed_domains = ["www.uwa.edu.au", "www.search.uwa.edu.au"]
    start_urls = ["https://www.search.uwa.edu.au/s/search.html?collection=uwa~sp-search&f.Level+of+study%7CcourseStudyLevel=undergraduate&f.International%7Cinternational=Available+to+International+Students&f.Tabs%7Ccourses=Courses&num_ranks=100&sort="]
    full_data=[]
    
    def parse(self, response):
        cards = response.css("div.listing-item__content")
        for card in cards: 
            url = card.css("a::attr(data-live-url)").get()
            course_name = card.css("h3.listing-item__title::text").get().strip()
            location = card.css("dt:contains('Location:') + dd::text").get()
            self.full_data.append({
                'url':url,
                'course_name':course_name,
                'location':location
            })

        # 檢查下一頁
        next_page = response.css('a.pagination__link[aria-label="Next page"]::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)       
        else:
            print(f'共有 {len(self.full_data)} 筆資料')
            for data in self.full_data:
                yield response.follow(data['url'], self.page_parse, meta={'location': data['location'],'course_name':data['course_name']})
    
    
    def page_parse(self, response):
        #取得課程名稱
        # course_name = response.css('h1.course-header-module-title::text').get()

        # 取得學費
        international_fees = response.css('div.segment-info[data-segment-filter="international"]')
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
        admission_requirement = response.css('div#admission-requirements')
        english_card = admission_requirement.css('div.course-detail.card').xpath(
            './/h3[contains(text(), "English competency")]/following-sibling::div[@class="card-container"]'
        )
        full_text = " ".join(english_card.css('div.card-content.rich-text-content p::text').getall()).strip()

        pattern = re.compile(
            r"(Minimum overall IELTS score of (\d+\.?\d*), with no band less than (\d+\.?\d*))|"
            r"Applicants presenting with the IELTS Academic require an overall score of at least (\d+\.?\d*), "
            r"a minimum (\d+\.?\d*) in the reading and writing bands, and a minimum score of (\d+\.?\d*) "
            r"in the listening and speaking bands(?:\s*For more information visit.*)?"
        )
        # 確保 full_text 不是 None
        if full_text:
            match = pattern.search(full_text)
        else:
            match = None

        if match:
            if match.group(2) and match.group(3):  # 情況 1: 總分與單科要求
                total_score = match.group(2)
                single_band_score = match.group(3)
                target_paragraph = f"IELTS {total_score} (單科不低於 {single_band_score})"
            elif match.group(4) and match.group(5) and match.group(6):  # 情況 2: 分別的分數要求
                total_score = match.group(4)
                reading_writing_score = match.group(5)
                listening_speaking_score = match.group(6)
                target_paragraph = (f"IELTS {total_score} (閱讀和寫作單項不低於 {reading_writing_score}，"
                                f"聽力和口語不低於 {listening_speaking_score})")
            else:
                target_paragraph = None
        else:
            target_paragraph = None

        # 取得duration
        course_details = response.css('div#course-details')
        duration_info = course_details.css('div.course-detail.card').xpath(
            './/h3[contains(text(), "Quick details")]/following-sibling::div[@class="card-container"]'
            '//div[@class="card-details-label" and text()="Full time/part time duration"]/following-sibling::div//ul/li/text()'
        ).getall()
        if not duration_info:
            duration = None  
        else:
            duration = "; ".join([d.replace('\n', '').strip() for d in duration_info])
     
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university['name'] = 'University of Western Australia'
        university['ch_name'] = '西澳大學'
        university['course_name'] = response.meta.get('course_name')
        university['min_tuition_fee'] = fee_2025
        university['location'] =  response.meta.get('location')
        university['english_requirement'] = target_paragraph
        university['duration'] = duration
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print('University of Western Australia 爬蟲完成!')        