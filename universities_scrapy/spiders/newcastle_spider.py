import scrapy

class NewcastleSpiderSpider(scrapy.Spider):
    name = "newcastle_spider"
    allowed_domains = ["www.newcastle.edu.au"]
    start_urls = ["https://www.newcastle.edu.au/degrees#filter=level_undergraduate,intake_international"]
    course_urls = []
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta=dict(
                playwright = True,
                playwright_include_page = True, 
		    ))
    
    def parse(self, response):
        rows = response.css('.uon-filtron-row.uon-card:not([style*="display: none;"])')
        # rows = response.css('.uon-filtron-listing.index-group a.degree-link')
        for row in rows:
            course_name = row.css('.degree-title a.degree-link::text').get()
            course_url = row.css('.degree-title a.degree-link::attr(href)').get()
            if 'Bachelor' in course_name and '(pre' not in course_name:
                    self.course_urls.append(course_url)
        
        print(f'Found {len(self.course_urls)} courses')
        for course_url in self.course_urls:
            print(f'{course_url}')

