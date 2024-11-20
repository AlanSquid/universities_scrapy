import scrapy


class AnuSpiderSpider(scrapy.Spider):
    name = "anu_spider"
    allowed_domains = ["www.anu.edu.au", "study.anu.edu.au", "programsandcourses.anu.edu.au"]
    start_urls = ["https://study.anu.edu.au/apply/international-applications"]
    detail_url_list = []
    
    def parse(self, response):
        # 發送form request
        return scrapy.FormRequest.from_response(
            response,
            formid='views-exposed-form-campaign-course-page-block-5',
            formdata={'combine': 'Bachelor'},
            callback=self.after_search
        )
    
    # 搜尋Bachelor後的解析
    def after_search(self, response):
        cards = response.css('.acc-card-body')
        for card in cards:
            # 抓取課程名稱
            title = card.css('h4 strong::text').get()
            # 抓取課程網址
            detail_url = card.css('.acc-card-links a:nth-of-type(2)::attr(href)').get()
            self.detail_url_list.append(detail_url)
            print(f'title: {title}, detail_url: {detail_url}')
            
        # 換頁
        next_page = response.css('li.pager__item.pager__item--next a::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.after_search)
    
    def closed(self, reason):    
        print(f'共有 {len(self.detail_url_list)} 筆資料\n{self.detail_url_list}')
        