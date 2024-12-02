import scrapy


class FlindersSpiderSpider(scrapy.Spider):
    name = "flinders_spider"
    allowed_domains = ["www.flinders.edu.au"]
    start_urls = ["https://www.flinders.edu.au/international"]
    courses = []

    def parse(self, response):
        study_areas_urls = response.xpath('//section/div/div[@class="section"][7]').css('.cta-button a::attr(href)').getall()
        for relative_url in study_areas_urls:
            url = response.urljoin(relative_url)
            yield scrapy.Request(url, callback=self.extract_course_url)
            
    def extract_course_url(self, response):
        urls = response.xpath('//div[@class="course_list_component"]//div[@class="accordion_item"][1]')\
        .css('ul.course_list li a::attr(href)').getall()
        self.courses += urls
        self.courses = list(set(self.courses))
    
    def closed(self, reason):
        print(f'Found {len(self.courses)} courses')

