# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class BookScrapyItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    

class UniversityScrapyItem(scrapy.Item):
    # 前五個最重要
    name = scrapy.Field() # 學校英文名稱
    ch_name = scrapy.Field() # 學校中文名稱
    course_name = scrapy.Field() # 課程(科系)名稱
    tuition_fee = scrapy.Field() # 年度學費
    location = scrapy.Field() # 校區
    
    currency = scrapy.Field(default='AUD') # 幣別
    english_requirement = scrapy.Field() # 英語門檻
    course_url = scrapy.Field() # 課程(科系)URL，大部分course_url會包含fee, english_requirement, academic_requirement等資訊
    english_requirement_url = scrapy.Field() # 英語門檻URL
    academic_requirement_url = scrapy.Field() # 學術門檻URL
    fee_detail_url = scrapy.Field() # 學費詳細資訊URL
    duration = scrapy.Field()
