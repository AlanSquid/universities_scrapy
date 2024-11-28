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
        line = json.dumps(dict(item), ensure_ascii=False)
        file = self.files[spider.name]
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