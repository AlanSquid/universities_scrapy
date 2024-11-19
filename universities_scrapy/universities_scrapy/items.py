# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class BookScrapyItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    

class UniversityScrapyItem(scrapy.Item):
    name = scrapy.Field()
    ch_name = scrapy.Field()
    course = scrapy.Field()
    course_url = scrapy.Field()
    tuition_fee = scrapy.Field()
    currency = scrapy.Field()
    english_requirement = scrapy.Field()
    location = scrapy.Field()
