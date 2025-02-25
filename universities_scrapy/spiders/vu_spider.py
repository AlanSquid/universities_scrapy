import scrapy
from universities_scrapy.items import UniversityScrapyItem 
import json
import re

class VuSpiderSpider(scrapy.Spider):
    name = "vu_spider"
    allowed_domains = ["www.vu.edu.au"]
    # start_urls = ["https://www.vu.edu.au/search?tab=vu_courses&page=1&sort=relevance&audience=international&f%5Bstudy_level%5D=Bachelor,Postgraduate"]
    start_urls = ["https://www.vu.edu.au/api/search"]
    all_course_url = []
    except_count = 0
    def start_requests(self):
        headers = {
            "Content-Type": "application/json"
        }
        
        self.query_data = self.query_data = {
            "body": {
                "from": 0, #改這個
                "size": 10,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "field_international": True
                                }
                            },
                            {
                                "terms": {
                                    "study_level": [
                                        "Bachelor",
                                        "Postgraduate"
                                    ]
                                }
                            }
                        ],
                        "should": [],
                        "must_not": []
                    }
                },
                "sort": [],
                "aggs": {
                    "unique_study_areas": {
                        "terms": {
                            "field": "study_areas",
                            "order": {
                                "_key": "asc"
                            },
                            "size": 100,
                            "min_doc_count": 0
                        }
                    },
                    "unique_study_level": {
                        "terms": {
                            "field": "study_level",
                            "order": {
                                "_key": "asc"
                            },
                            "size": 100,
                            "min_doc_count": 0
                        }
                    },
                    "unique_course_locations_search_index": {
                        "terms": {
                            "field": "course_locations_search_index",
                            "order": {
                                "_key": "asc"
                            },
                            "size": 100,
                            "min_doc_count": 0
                        }
                    },
                    "unique_course_delivery_modes_search_index": {
                        "terms": {
                            "field": "course_delivery_modes_search_index",
                            "order": {
                                "_key": "asc"
                            },
                            "size": 100,
                            "min_doc_count": 0
                        }
                    },
                    "unique_course_duration": {
                        "terms": {
                            "field": "course_duration",
                            "order": {
                                "_key": "asc"
                            },
                            "size": 100,
                            "min_doc_count": 0
                        }
                    }
                }
            },
            "index": "vu_courses"
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
        total_results = json_response["data"]["hits"]["total"]["value"]
        # 先取得總數量，如果總數大於10，修改size並重新發送請求
        if total_results > self.query_data["body"]["size"]:
            new_size = total_results
            self.query_data["body"]["size"] = new_size
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
            for hit in json_response["data"]["hits"]["hits"]:
                course_name = hit["_source"]["title"][0]  
                skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma", "Juris Doctor", "MBA"]
                keywords = ["Bachelor of", "Master of"]
                if not course_name or any(keyword in course_name for keyword in skip_keywords) or sum(course_name.count(keyword) for keyword in keywords) >= 2:
                    # print('跳過:',course_name)
                    continue
                duration_info = hit["_source"]["field_course_duration"][0]  
                if duration_info:
                    duration_info = duration_info.strip()
                    pattern = r"(\d+(\.\d+)?)\s+year[s]?\s+full time"
                    match = re.search(pattern, duration_info)
                    
                    if match:
                        duration = float(match.group(1))  
                    else:
                        duration = None 
                else:
                    duration_info = None

                study_level = hit["_source"]["study_level"][0] 
                degree_level_id = None
                if "bachelor" in study_level.lower():
                    degree_level_id = 1
                elif "postgraduate" in study_level.lower(): 
                    degree_level_id = 2   
                locations = hit["_source"]["course_locations_search_index"]
                campus = ", ".join(locations)
                url = hit["_source"]["entity_path_alias"][0]  
                course_url = f"https://www.vu.edu.au{url}/international"    
                self.all_course_url.append(course_url)
                yield response.follow(course_url, self.page_parse, meta={'duration_info': duration_info, 'campus': campus, 'degree_level_id': degree_level_id, "duration": duration})
    
    def page_parse(self, response): 
        course_name = response.css('h1::text').get()
        if course_name == None:
            # print("沒有資料，", response.url)
            self.except_count += 1
            return
        else:
            course_name = course_name.strip()

        eng_req_info = None
        eng_req = None
        ielts_info = response.css("div#vu-main-content div#entry-requirements div.vu--additional-data.item-type--collapsible_section div.vu-collapsible-section-content--parent div.vu-collapsible-section-content div.vu-markup.tide-wysiwyg.app-wysiwyg div.vu-markup__inner")
        ielts_requirement = ielts_info.xpath("//div[contains(., 'IELTS')]/p[contains(., 'IELTS')]").getall()
        if ielts_requirement:
            text = ' '.join(ielts_requirement).strip()
            patterns = [
                re.compile(r"(IELTS \(or equivalent\):.*?Listening, Reading, Writing and Speaking[.)])", re.DOTALL),
                re.compile(r"IELTS.*?minimum.*?overall score of (\d+(\.\d+)?) .*?minimum score of (\d+(\.\d+)?) in each of.*?(listening.*?reading.*?writing.*?speaking)", re.DOTALL | re.IGNORECASE),
                re.compile(r"IELTS \(or equivalent\):.*?Overall score\s*(of|or)?\s*(\d+(\.\d+)?).*?(Listening.*?(\d+(\.\d+)?)).*?(Reading.*?(\d+(\.\d+)?)).*?(Writing.*?(\d+(\.\d+)?)).*?(Speaking.*?(\d+(\.\d+)?))", re.DOTALL),
                re.compile(r"IELTS.*?Overall\s*(?:\d+(\.\d+)?)\s*with\s*Listening\s*(?:\d+(\.\d+)?),\s*Reading\s*(?:\d+(\.\d+)?),\s*Writing\s*(?:\d+(\.\d+)?),\s*Speaking\s*(?:\d+(\.\d+)?)", re.DOTALL),
                re.compile(r"IELTS \(or equivalent\):.*?Overall score\s*(of|or)?\s*(\d+(\.\d+)?)", re.DOTALL),
                re.compile(r"IELTS \(Academic\):\s*minimum overall band\s*of\s*(\d+(\.\d+)?)", re.DOTALL),
                re.compile(r"IELTS.*?minimum overall (?:band|score)\s*of\s*(\d+(\.\d+)?)", re.DOTALL),
                re.compile(r"IELTS.*?overall\s*(?:band|score)\s*of\s*(\d+(\.\d+)?)", re.DOTALL),
                re.compile(r"required to complete IELTS.*?Overall\s*(?:\d+(\.\d+)?)\s*with", re.DOTALL),
            ]

            for pattern in patterns:
                match = pattern.search(text,)
                if match:
                    eng_req_info = match.group(0).strip()
                    eng_req_info = re.sub(r'</p>.*$', '', eng_req_info, flags=re.DOTALL)  # Remove everything after </p>
                    eng_req_info = re.sub(r'<br>.*$', '', eng_req_info, flags=re.DOTALL)  # Remove everything after <br>
                    eng_req_info = eng_req_info.replace("&amp","")
                    # Bachelor of Nursing會少括號
                    if eng_req_info.count('(') > eng_req_info.count(')'):
                        eng_req_info += ')'
                    score_patterns = [
                        r'Overall\s*(?:score|band)?\s*(?:of|or)?\s*(\d+(?:\.\d+)?)',
                        r'Overall\s*(\d+(?:\.\d+)?)\s*with',
                        r'Overall\s*(\d+(?:\.\d+)?)'
                    ]
                    
                    for score_pattern in score_patterns:
                        score_match = re.search(score_pattern, eng_req_info, re.IGNORECASE)
                        if score_match:
                            eng_req = float(score_match.group(1))
                            break
                    
                    if eng_req:
                        break
        
        # 學費
        tuition_text = response.xpath("//div[contains(@class, 'vu-course-essentials-content-value')]//text()").getall()
        tuition_text = ''.join(tuition_text).strip()
        semester_tuition_fee = None
        match = re.search(r"AU\$(\d{1,3}(?:,\d{3})*)", tuition_text)
        if match:
            semester_tuition_fee = int(match.group(1).replace(",", ""))
        tuition_fee = semester_tuition_fee * 2
        university = UniversityScrapyItem()
        university['university_name'] = "Victoria University"
        university['name'] = course_name
        university['min_fee'] = tuition_fee
        university['max_fee'] = tuition_fee
        university['campus'] = response.meta["campus"]
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['duration'] = response.meta["duration"]
        university['duration_info'] = response.meta["duration_info"]
        university['degree_level_id'] = response.meta["degree_level_id"] 
        university['course_url'] = response.url

        yield university

    def closed(self, reason):    
        print(f'{self.name}爬蟲完畢\n維多利亞大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
        print(f'有 {self.except_count} 筆目前不開放申請\n')
