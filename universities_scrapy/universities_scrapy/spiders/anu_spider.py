import scrapy


class AnuSpiderSpider(scrapy.Spider):
    name = "anu_spider"
    allowed_domains = ["www.anu.edu.au", "study.anu.edu.au", "programsandcourses.anu.edu.au"]
    start_urls = ["https://study.anu.edu.au/apply/international-applications"]
    detail_url_list = []
    
    def parse(self, response):
        return scrapy.FormRequest.from_response(
            response,
            formid='views-exposed-form-campaign-course-page-block-5',
            formdata={'combine': 'Bachelor'},
            callback=self.after_search
        )
        
    def after_search(self, response):
        cards = response.css('.acc-card-body')
        for card in cards:
            title = card.css('h4 strong::text').get()
            detail_url = card.css('.acc-card-links a:nth-of-type(2)::attr(href)').get()
            self.detail_url_list.append(detail_url)
            print(f'title: {title}, detail_url: {detail_url}')
            
        # 換頁
        next_page = response.css('li.pager__item.pager__item--next a::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)
        
        print(self.detail_url_list)
        