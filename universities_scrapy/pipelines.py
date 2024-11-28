# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json 
import os 

class UniversitiesScrapyPipeline:
    def process_item(self, item, spider):
        if spider.name == 'books':
            adapter = ItemAdapter(item)
            adapter['price'] = adapter['price'].replace('£', '')
            return item
        return item
    

class SaveToSharedFilePipeline:
    def __init__(self):
        self.files = {}
        self.output_dir = "universities_output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.first_item = {}

    def open_spider(self, spider):
        filename = f"{spider.name[:-7] if spider.name.endswith('_spider') else spider.name}_output.json"
        file_path = os.path.join(self.output_dir, filename)
        self.files[spider.name] = open(file_path, 'w', encoding='utf-8')
        self.files[spider.name].write('[\n') 
        self.first_item[spider.name] = True  

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        # 格式轉換
        for field_name in adapter.keys():
            value = adapter.get(field_name)

            if field_name in {'min_tuition_fee', 'max_tuition_fee'}:  # 學費轉 float
                try:
                    adapter[field_name] = (
                        round(float(value), 2) if value is not None else value
                    )
                except ValueError:
                    adapter[field_name] = None
            else:  # 其他轉 string
                adapter[field_name] = str(value) if value is not None else value

        # 寫入檔案
        file = self.files[spider.name]
        line = json.dumps(adapter.asdict(), ensure_ascii=False)
        
        if self.first_item[spider.name]:
            self.first_item[spider.name] = False  
        else:
            file.write(',\n') 
        
        file.write(line)
        return item

    def close_spider(self, spider):
        file = self.files.pop(spider.name, None)
        if file:
            file.write('\n]') 
            file.close()
    
    def serialize_to_string(value):
        if value is not None:
            return str(value)
        else:
            return value

    def serialize_to_float(value):
        try:
            if value is not None:
                return round(float(value), 2)
            else:
                return value
        except ValueError:
            return None