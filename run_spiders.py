import importlib  # 動態導入模組
import pkgutil  # 對所有模組進行迭代
import universities_scrapy.spiders  # 導入spiders模組
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import scrapy

# 把所有spirder拿出來
def load_spiders(package):
    spiders = []
    package_path = package.__path__
    for _, module_name, is_pkg in pkgutil.iter_modules(package_path):
        if not is_pkg and module_name.endswith('_spider'):
            module = importlib.import_module(f"{package.__name__}.{module_name}")
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, scrapy.Spider) and obj.__module__ == module.__name__:
                    spiders.append(obj)
    return spiders

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())

    # 把所有spirder拿出來
    spiders = load_spiders(universities_scrapy.spiders)
    
    # 跌代spiders給CrawlerProcess執行
    for spider in spiders:
        process.crawl(spider)

    process.start() 