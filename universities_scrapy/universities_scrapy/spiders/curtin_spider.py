import scrapy
import json

class CurtinSpiderSpider(scrapy.Spider):
    name = "curtin_spider"
    allowed_domains = ["curtin.edu.au"]  # 修改為正確的域名
    start_urls = ["https://www.curtin.edu.au/students/wp-json/student-fee-calculator/getCalculatorData?studyMode=7&year=2024"]

    custom_settings = {
        'ROBOTSTXT_OBEY': False,  # 如果需要的話可以設置為 False
    }

    def start_requests(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": "https://www.curtin.edu.au/students/essentials/fees/understanding-your-fees/tuition-fees/student-fee-calculator/",
            "x-wp-nonce": "2cb94a5e28",
        }

        yield scrapy.Request(
            url=self.start_urls[0],
            callback=self.parse,
            headers=headers,
            dont_filter=True  # 添加這個參數來避免過濾
        )

    def parse(self, response):
        if response.status == 200:
            self.logger.debug(f"Response body: {response.text}")
            
            try:
                data = response.json()
                # 根據實際返回的數據結構修改解析邏輯
                if 'courses' in data:
                    for course in data['courses']:
                        yield {
                            "id": course.get("id"),
                            "course_code": course.get("course_code"),
                            "title": course.get("title"),
                            "cost_per_credit_point": course.get("cost_per_credit_point"),
                            "year_id": course.get("year_id"),
                            "created_at": course.get("created_at"),
                            "last_updated": course.get("last_updated")
                        }
                else:
                    self.logger.error("No courses data found in response")
                    self.logger.debug(f"Response structure: {data.keys()}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Raw response: {response.text}")
        else:
            self.logger.error(f"Failed to retrieve data, status code: {response.status}")