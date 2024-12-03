# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import traceback
import inspect
from collections.abc import AsyncIterable

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter


class UniversitiesScrapySpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    # 修改後可以根據result的類型來判斷是同步還是異步的處理
    def process_spider_output(self, response, result, spider):
        if isinstance(result, AsyncIterable):
            return self.process_spider_output_async(response, result, spider)
        else:
            return self.process_spider_output_sync(response, result, spider)
            
    def process_spider_output_sync(self, response, result, spider):
        for i in result:
            yield i

            
    async def process_spider_output_async(self, response, result, spider):
    # Called with the results returned from the Spider, after
    # it has processed the response.

        # Must return an iterable of Request, or item objects.
        async for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # 取得錯誤的堆疊跟蹤
        stack = traceback.extract_tb(exception.__traceback__)
        if stack:
            # 取得出錯的函數名稱
            error_function = stack[-1].name
        else:
            error_function = "Unknown function"

        # 自定義錯誤格式
        spider_name = spider.name
        request_url = response.url
        error_message = exception
        error_traceback = traceback.format_exc()

        spider.logger.error(f"\n========================================================\n"
                            f"* 發生錯誤的 Spider: 「{spider_name}」\n"
                            f"* 正在進行的 URL: {request_url}\n"
                            f"* 位於哪個 function: {error_function}\n"
                            f"========================================================\n"
                            )
        spider.logger.error(f"\n=============== Error Details ===============:\n"
                            f"{error_message}\n"
                            # f"=============== Traceback ===============:\n"
                            # f"{error_traceback}\n"
                            # f"============================================="
                            )

        # 你可以選擇返回 None 或繼續處理其他結果
        return None

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class UniversitiesScrapyDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)
