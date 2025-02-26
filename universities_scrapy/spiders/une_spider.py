import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re


class UneSpiderSpider(scrapy.Spider):
    name = "une_spider"
    allowed_domains = ["www.une.edu"]
    start_urls = [
        "https://www.une.edu/academics/majors-and-programs",
    ]
    courses = []
    keywords = ["Bachelors", "Masters"]
    exclude_keywords = [
        "(Honours)",
        "/",
    ]

    
    year = '2024-2025'

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta=dict(playwright=True),
            )

    def parse(self, response):
        cards = response.css(
            'div[data-once="ajax-pager une-programs"] .view-content .views-row'
        )
        for card in cards:
            degree_type = card.css("article::attr(data-types)").get()
            location_type = card.css("article::attr(data-location)").get()
            if (
                any(keyword in degree_type for keyword in self.keywords)
                and sum(degree_type.count(keyword) for keyword in self.keywords) == 1
                and "on_campus" in location_type
            ):
                # course_name = card.css(".program-title a span::text").get().strip()
                
                # 學區
                campus = card.css(".program-location::text").get().strip()
                
                # 學位
                if "Bachelors" in degree_type:
                    degree = 1
                elif "Masters" in degree_type:
                    degree = 2
                else:
                    degree = None
                
                link = card.css(".program-title a::attr(href)").get()
                course_url = response.urljoin(link)
                
                self.courses.append({"campus": campus, "url": course_url, "degree": degree})

        for course in self.courses:
            yield scrapy.Request(
                course["url"],
                self.parse_course,
                meta=dict(campus=course["campus"],
                          degree=course["degree"]),
            )

    def parse_course(self, response):
        course_name = response.css("h1.page-title span::text").get()
        campus = response.meta["campus"]
        degree_level_id = response.meta["degree"]
        fee_url = None
        
        # print(course_name)
        # print(campus)
        # print(response.url)
        # print("\n")
        
        # 學費
        fee_url = None
        fee = None
        if degree_level_id == 1:
            fee_url = f"https://www.une.edu/sfs/undergraduate/costs"    
            fee = 44280          
        elif degree_level_id == 2:
            fee_url = f"https://www.une.edu/catalog/{self.year}/graduate-catalog/financial-information"
            
            if "Physician Assistant" in course_name:
                fee = 51670
            elif "Occupational Therapy" in course_name:
                fee = 42970
            elif "Athletic Training" in course_name:
                fee = 1050 * 62 # 學分費用 * 學分數
            elif "Clinical Anatomy" in course_name:
                fee = 29250 + 26910
                fee_url = "https://www.une.edu/sfs/graduate/costs/2024-2025-master-science-clinical-anatomy-costs"
            
        # 把資料存入 university Item
        university = UniversityScrapyItem()
        university["university_name"] = "University of New England"
        university["name"] = course_name
        university["degree_level_id"] = degree_level_id
        university["min_fee"] = fee
        university["max_fee"] = fee
        university["eng_req"] = 6.0
        university["eng_req_info"] = 'Overall Band 6.0 or higher'
        university["campus"] = campus
        university["fee_detail_url"] = fee_url
        # 沒有學制資訊
        # university["duration"] = None
        # university["duration_info"] = None
        yield university


    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(f"新英格蘭大學, 共有 {len(self.courses)} 筆資料\n")
