import os
import subprocess

# spiders目錄路徑
spiders_dir = 'universities_scrapy/spiders'

# 獲取所有_spider.py結尾的檔案
# spider_files = [f for f in os.listdir(spiders_dir) if f.endswith('_spider.py')]
# 獲取所有_spider.py結尾的檔案，latrobe_spider除外
spider_files = [f for f in os.listdir(spiders_dir) 
                if f.endswith('_spider.py') and f != "latrobe_spider.py"]


def run_spiders():
    for spider_file in spider_files:
        # 去除副檔名.py
        spider_name = spider_file[:-3]
        
        # 執行scrapy crawl 命令
        command = f'uv run scrapy crawl {spider_name}'
        
        print(f'Running spider: {spider_name}')
        subprocess.run(command, shell=True, check=True)

        
    # 執行latrobe_spider
    command = f'uv run scrapy crawl latrobe_spider'
    print(f'Running spider: latrobe_spider')
    subprocess.run(command, shell=True, check=True)

if __name__ == "__main__":
    run_spiders()
