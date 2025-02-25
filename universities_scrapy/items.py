# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
class BookScrapyItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    
class UniversityScrapyItem(scrapy.Item):
    university_name = scrapy.Field() #大學id
    name = scrapy.Field() # 課程(科系)名稱
    min_fee = scrapy.Field() # 年度學費 區間最小值 如果沒有區間，只需要填min_fee
    max_fee = scrapy.Field() # 年度學費 區間最大值
    campus = scrapy.Field() # 校區
    degree_level_id = scrapy.Field() #學位等級id
    currency_id = scrapy.Field(default='AUD') # 幣別id
    eng_req = scrapy.Field() # 英語門檻
    eng_req_info = scrapy.Field() # 詳細的英語門檻
    course_url = scrapy.Field() # 課程(科系)URL，大部分course_url會包含fee, english_requirement, academic_requirement等資訊
    eng_req_url = scrapy.Field() # 英語門檻URL
    acad_req_url = scrapy.Field() # 學術門檻URL
    fee_detail_url = scrapy.Field() # 學費詳細資訊URL
    duration = scrapy.Field() # 學制(期間)
    duration_info = scrapy.Field() # 詳細的學制(期間)
    course_category_id = scrapy.Field() #課程類別id