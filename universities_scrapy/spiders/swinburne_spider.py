import scrapy
from scrapy_playwright.page import PageMethod
from universities_scrapy.items import UniversityScrapyItem
import re


class SwinburneSpiderSpider(scrapy.Spider):
    name = "swinburne_spider"
    allowed_domains = ["www.swinburne.edu.au"]
    start_urls = ["https://www.swinburne.edu.au/courses/find-a-course/"]
    categories = []
    courses = [] 
    keywords = ["Bachelor of", "Master of"]
    exclude_keywords = ["Honours", "Research", "Online"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse
            )

    def parse(self, response):
        ul = response.xpath(
            "//div/div[2]/article/div/div/div/section[2]/div/div/div[2]/div/ul"
        )
        cards = ul.css(".card")
        for card in cards:
            # title = card.css('.card-title::text').get().strip()
            link = card.css(".card-link.btn.btn-secondary-charcoal::attr(href)").get()
            url = response.urljoin(link)
            yield scrapy.Request(
                url,
                self.categorize_url
            )

    # 分類url
    def categorize_url(self, response):
        h2_elements = response.css("#content-area section h2::text").getall()
        if any("Explore our" in h2 for h2 in h2_elements):
            links = response.css("#content-area h2").xpath('../following-sibling::div[1]').css('ul li a.card')
            for link in links:
                url = response.urljoin(link.css("::attr(href)").get())
                if "/course/" in url or "/courses/" in url:
                    if "find-a-course" in url:
                        self.categories.append(url)
                    else:
                        name = link.css('.card-title::text').get().strip()
                        if any(name.count(keyword) == 1 for keyword in self.keywords) and all(
                            exclude_keyword not in name
                            for exclude_keyword in self.exclude_keywords
                        ):
                            self.courses.append(url)           
        else:
            self.categories.append(response.url)

        # 去重複
        self.categories = list(set(self.categories))
        for category_url in self.categories:
            yield scrapy.Request(
                category_url,
                self.extract_course_url,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", ".results-list")
                    ],
                ),
            )
        
            
    # 提取課程url
    async def extract_course_url(self, response):
        page = response.meta["playwright_page"]

        while True:
            try:
                view_more_btn = await page.query_selector(
                    "#content-area footer.results-list__footer button"
                )
                await view_more_btn.click()
            except:
                break
        updated_page = scrapy.Selector(text=await page.content())
        await page.close()
        
        course_urls = updated_page.css(
            "#content-area .results-list div:not([class]) a"
        )
        
        for url in course_urls:
            course_url = url.css("::attr(href)").get()
            course_name = url.css(".results-column--title.h6::text").get()
            sub_name = url.css(".results-column--title.h6 em::text").get()
            if sub_name:
                course_name += sub_name 
            if any(course_name.count(keyword) == 1 for keyword in self.keywords) and all(
                exclude_keyword not in course_name
                for exclude_keyword in self.exclude_keywords
            ):
                # print("course_name:", course_name)
                # print("course_url:", course_url)
                # print("\n")
                self.courses.append(course_url)
                
        # 去除重複
        self.courses = list(set(self.courses))
        
        for course_url in self.courses:
            yield scrapy.Request(
                course_url,
                self.parse_courses,
                # meta=dict(
                #     playwright=True,
                #     playwright_include_page=True,
                # ),
            )

    # 提取課程資訊
    def parse_courses(self, response):
       course_name = response.css('.course-details__title h1::text').get().strip() if response.css('.course-details__title h1::text').get() else None
       print('course_name', course_name)
       print(response.url)
       
    def closed(self, reason):
        print(f"{self.name} 爬蟲完成!")
        print(f"斯威本理工大學, 共有 {len(self.courses)} 筆資料\n")
