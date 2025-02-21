import scrapy
from universities_scrapy.items import UniversityScrapyItem
from scrapy_playwright.page import PageMethod
import json
import re


class BondSpiderSpider(scrapy.Spider):
    name = "bond_spider"
    allowed_domains = ["bond.edu.au"]
    all_course_url = []
    start_urls = ["https://bond.edu.au/api/v1/elasticsearch/bond_prod_default/_search"]
    # start_urls = ["https://bond.edu.au/study/program-finder?program_category%5B%5D=Undergraduate&program_category%5B%5D=Postgraduate&delivery_mode%5B%5D=On-Campus&student_type%5B%5D=International+students"]

    def start_requests(self):
        headers = {
            "Content-Type": "application/json"
        }
        
        self.query_data = {
            "_source": [
                "url",
                "title",
                "copy",
                "breadcrumb",
                "category",
                "card"
            ],
            "size": 12,
            "from": 0,
            "query": {
                "bool": {
                    "should": [
                        {
                            "rank_feature": {
                                "field": "rank",
                                "linear": {},
                                "boost": 0.1
                            }
                        }
                    ],
                    "filter": [
                        {
                            "terms": {
                                "top_filter": [
                                    "Program",
                                    "Microcredential"
                                ]
                            }
                        },
                        {
                            "terms": {
                                "program_category": [
                                    "Undergraduate",
                                    "Postgraduate"
                                ]
                            }
                        },
                        {
                            "terms": {
                                "delivery_mode": [
                                    "On-Campus"
                                ]
                            }
                        },
                        {
                            "terms": {
                                "student_type": [
                                    "International students"
                                ]
                            }
                        }
                    ]
                }
            }
        }

        yield scrapy.Request(
            self.start_urls[0],
            headers=headers,
            method="POST",
            body=json.dumps(self.query_data),
            callback=self.parse_api_response
        )

    def parse_api_response(self, response):
        json_response = response.json()
        total_results = json_response["hits"]["total"]["value"]
        # 先取得總數量，如果總數大於12，修改size並重新發送請求
        if total_results > self.query_data["size"]:
            new_size = total_results
            self.query_data["size"] = new_size
            # 再次發送請求，使用更新的size值
            yield scrapy.Request(
                self.start_urls[0],
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
                body=json.dumps(self.query_data),
                callback=self.parse_api_response
            )
        else:
            # with open("organized_fields.json", "w", encoding="utf-8") as f:
            #     json.dump(json_response, f, ensure_ascii=False, indent=4)
            hits = json_response["hits"]["hits"]            
            for hit in hits:
                course_name = hit["_source"]["title"][0]
                # 跳過雙學位, Honours, Online, Graduate Certificate, Diploma
                skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
                keywords = ["Bachelor of", "Master of"]
                if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                    # print('跳過:',course_name)
                    continue
                course_name = course_name.split(" - ")[0]
                url = hit["_source"]["url"][0]
                course_url = response.urljoin(url) 
                self.all_course_url.append(course_url)
                hit_id = hit["_id"]
                match = re.search(r'(\d+)', hit_id)
                if match:
                    extracted_number = match.group(1)
                    yield scrapy.Request(
                       (f"https://bond.edu.au/api/program-details/{extracted_number}"),
                        headers={
                            "Content-Type": "application/json"
                        },
                        method="GET",
                        callback=self.parse_course_page,
                        meta=dict(
                            hit_id = extracted_number,
                            course_name = course_name,
                            course_url = course_url
                        )
                    )              

    # 基本資料
    def parse_course_page(self, response):       
        json_response = response.json()
        programs_id = json_response["programs"][0]["id"]
        location = json_response["programs"][0]["offerings"][0]["location"]      
        # print("location:",location)
        duration_info = json_response["programs"][0]["duration"]
        # print("duration:",duration)
        degree_level = json_response["programs"][0]["type"]
        degree_level_id = None
        if "bachelor" in degree_level.lower():
            degree_level_id = 1
        elif "master" in degree_level.lower(): 
            degree_level_id = 2        
        
        # 初始化一個用來保存資料的字典
        course_data = {
            "course_name": response.meta["course_name"],
            "course_url": response.meta["course_url"],
            "location": location,
            "duration_info": duration_info,
            "degree_level_id" : degree_level_id
        }

        # 學費 API 請求
        if programs_id:
            fee_url = f"https://bond.edu.au/api/program-fees/{response.meta['hit_id']}/{programs_id}"
            yield scrapy.Request(
                fee_url,
                headers={"Content-Type": "application/json"},
                method="GET",
                callback=self.parse_fee,
                meta=dict(
                    course_data = course_data
                )            
            )
    
    def parse_fee(self, response):       
        json_response = response.json()

        fees = json_response.get("fees", [])
        # 過濾出 year=2025 的費用資料
        fee_2025 = next((fee for fee in fees if fee["year"] == "2025"), None)

        if fee_2025:
            total_fee = fee_2025.get("international", {}).get("total", None)
        else:
            total_fee = None

        course_data = response.meta["course_data"]
        
        if '92 weeks' in course_data["duration_info"]:
            years = 2
            duration = 2
        else:
            # 提取 年、月
            year_match = re.search(r'(\d+)\s*year', course_data["duration_info"])
            month_match = re.search(r'(\d+)\s*month', course_data["duration_info"])

            years = int(year_match.group(1)) if year_match else 0
            months = int(month_match.group(1)) if month_match else 0

            # 換算成年數
            years =  years + (months / 12)
            duration = years
        # 如果不到一年，就當作是一年
         
        if 0 < years < 1:
            years = 1

        if years > 0:
            year_fee = total_fee / years
             
        else:
            year_fee = None
        course_data["duration"] = duration
        course_data["year_fee"] = year_fee
        # 請求英文門檻api
        eng_req_url = f"{course_data['course_url']}/entry_requirements"
        yield scrapy.Request(
            eng_req_url,
            callback=self.parse_eng_req,
            meta=dict(
                course_data = course_data
            )            
        )

    def parse_eng_req(self, response):       
        course_data = response.meta["course_data"]
        eng_req_text = response.css("div.block-block-english-proficiency-requirements")
        if eng_req_text:
            ielts_text = eng_req_text.xpath(
                '//dd[contains(., "IELTS") and contains(., "Overall")]//text()'
            ).getall()
            eng_req_info = ''.join(ielts_text).strip() if ielts_text else None
            match = re.search(r'Overall score (\d+(\.\d+)?)', eng_req_info)
            if match:
                eng_req = float(match.group(1))
            else:
                eng_req = None
        else:
            eng_req = None
            eng_req_info=None
    
        university = UniversityScrapyItem()
        university['university_id'] = 16
        university['name'] = course_data["course_name"]
        university['min_fee'] = course_data["year_fee"]
        university['max_fee'] = course_data["year_fee"]
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['campus'] = course_data["location"]
        university['duration'] = course_data["duration"]
        university['duration_info'] =  course_data["duration_info"]
        university['degree_level_id'] =  course_data["degree_level_id"]
        university['course_url'] = course_data["course_url"]  

        yield university      
       
    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n邦德大學，共{len(self.all_course_url)}筆資料\n')














        
    # def start_requests(self):
    #     for url in self.start_urls:
    #         yield scrapy.Request(url, self.parse, meta=dict(
    #             playwright=True,
    #             playwright_page_methods=[
    #                 PageMethod('wait_for_selector', 'div#search-results')
    #             ]
    #         ))

    # def parse(self, response):
    #     cards = response.css("div#search-results div.uk-card-body")
    #     # with open("response.html", "w", encoding="utf-8") as f:
    #     #     f.write(response.text)
    #     for card in cards:
    #         url = card.css("a::attr(href)").get()
    #         course_url = response.urljoin(url)
    #         self.all_course_url.append()
    #         title = card.css("h3::text").get(course_url)
