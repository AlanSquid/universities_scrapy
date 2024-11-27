# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

def serialize_to_string(value):
    return str(value)

def serialize_to_float(value):
    try:
        if value is not None:
            return round(float(value), 2)
        else:
            return value
    except ValueError:
        return None
class BookScrapyItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    

class UniversityScrapyItem(scrapy.Item):
    # 前五個最重要
    name = scrapy.Field(serializer=serialize_to_string) # 學校英文名稱
    ch_name = scrapy.Field(serializer=serialize_to_string) # 學校中文名稱
    course_name = scrapy.Field(serializer=serialize_to_string) # 課程(科系)名稱
    min_tuition_fee = scrapy.Field(serializer=serialize_to_float) # 年度學費 區間最小值 如果沒有區間，只需要填min_tuition_fee
    max_tuition_fee = scrapy.Field(serializer=serialize_to_float) # 年度學費 區間最大值
    location = scrapy.Field(serializer=serialize_to_string) # 校區
    
    currency = scrapy.Field(default='AUD', serializer=serialize_to_string) # 幣別
    english_requirement = scrapy.Field(serializer=serialize_to_string) # 英語門檻
    course_url = scrapy.Field(serializer=serialize_to_string) # 課程(科系)URL，大部分course_url會包含fee, english_requirement, academic_requirement等資訊
    english_requirement_url = scrapy.Field(serializer=serialize_to_string) # 英語門檻URL
    academic_requirement_url = scrapy.Field(serializer=serialize_to_string) # 學術門檻URL
    fee_detail_url = scrapy.Field(serializer=serialize_to_string) # 學費詳細資訊URL
    duration = scrapy.Field(serializer=serialize_to_string) # 學制(期間)