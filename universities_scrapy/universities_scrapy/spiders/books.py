import scrapy
from universities_scrapy.items import BooksScrapyItem


class BooksSpider(scrapy.Spider):
    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]

    # 沒用itmes.py的寫法
    # def parse(self, response):
    #     products = response.css('article.product_pod')
    #     for product in products:
    #         yield {
    #             'title': product.css('h3 a::text').get(),
    #             'price': product.css('p.price_color::text').get(),
    #         }
    
    # 用items.py的寫法
    def parse(self, response):
        products = response.css('article.product_pod')
        for product in products:
            item = BooksScrapyItem()
            item['title'] = product.css('h3 a::attr(title)').get()
            item['price'] = product.css('div.product_price p.price_color::text').get()
            yield item
            
        # 換頁
        next_page = response.css('li.next a::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)
