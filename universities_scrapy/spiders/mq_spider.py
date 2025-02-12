import scrapy
from universities_scrapy.items import UniversityScrapyItem  
import re
import json

class MqSpiderSpider(scrapy.Spider):
    name = "mq_spider"
    allowed_domains = ["www.mq.edu.au","websearch.mq.edu.au"]
    # start_urls = ["https://www.mq.edu.au/search?query=&category=courses&start_rank=1"]
    start_urls = ["https://websearch.mq.edu.au/s/search.json?collection=mq-edu-au-push-courses&profile=international&query=!padrenull"]
    all_course_url = []
    results_quantity = 1
    except_count = 0
    
    def transform_url(self, url):
        parts = url.split("/study/")
        if len(parts) == 2:
            return f"{parts[0]}/study/page-data/{parts[1]}/page-data.json"
        return url  
    
    def parse(self, response):
        data = response.json()  
        for item in data['response']['resultPacket']['results']:
            course_name = item['metaData']['courseName']
            study_level = item['metaData']['studyLevel']
            keywords = ["Undergraduate", "Postgraduate"]
            skip_keywords = ["Doctor of", "Honours", "Graduate Certificate", "Diploma","Juris Doctor"]

            if not study_level  or any(keyword in course_name for keyword in skip_keywords) or not any(keyword in study_level for keyword in keywords) or  not "Course" in item['metaData']['courseType'] :
                # print('跳過:',course_name)
                continue

            if "Undergraduate" in study_level :
                degree_level_id = 1
            elif "Postgraduate" in study_level or "Master" in study_level:
                degree_level_id = 2
            else:
                degree_level_id = None

            courseDurationNum = item['metaData'].get('courseDurationNum', None)
            course_url = item['metaData']['identifier']
            self.all_course_url.append(course_url)
            new_course_url = self.transform_url(course_url)
            yield scrapy.Request(
                new_course_url, 
                method="GET",
                callback=self.page_parse, 
                meta=dict(
                    course_name = course_name,
                    degree_level_id = degree_level_id,
                    duration_info = courseDurationNum,
                    course_url = course_url,
                ))   

        self.results_quantity += 10
        
        # 檢查有沒有下一頁 
        if data['response']['resultPacket']['resultsSummary']['totalMatching'] >= self.results_quantity:
            new_url = f"https://websearch.mq.edu.au/s/search.json?collection=mq-edu-au-push-courses&profile=domestic&query=!padrenull&start_rank={self.results_quantity}"
            yield scrapy.Request(
                new_url,
                method="GET",
                callback=self.parse
            )
        # else:
            # print("結束",self.results_quantity)
    
    
    def page_parse(self, response):
        # 整理回傳的json
        data = response.json()  
        fields = data["result"]["data"]["current"]["fields"]
        nested_json = json.loads(fields["json"])
        organized_fields = {
            key: field["value"] if isinstance(field, dict) and "value" in field else field
            for key, field in nested_json.items()
        }
        if organized_fields["isOfferedToInternational"] == False:
            self.except_count += 1
            # print("此課程不開放國際生:",response.meta["course_name"]  )
            return
        
        # 取得英文門檻
        eng_req = organized_fields["ielts_overall_score"]
        # 篩選 key 以 `ielts_` 開頭的資料
        ielts_data = {k: v for k, v in organized_fields.items() if k.startswith("ielts_")}

        # 定義轉換標籤
        ielts_labels = {
            "ielts_overall_score": "IELTS overall",
            "ielts_listening_score": "listening",
            "ielts_reading_score": "reading",
            "ielts_speaking_score": "speaking",
            "ielts_writing_score": "writing"
        }
        # 取出 overall 分數，並從資料中刪除
        overall_score = f"{ielts_labels['ielts_overall_score']} {ielts_data.pop('ielts_overall_score')}"
        # 處理剩下的 IELTS 分數
        ielts_scores = [f"{ielts_labels[k]} {v}" for k, v in ielts_data.items()]
        # 合併結果，確保 overall 在最前面
        eng_req_info = ", ".join([overall_score] + ielts_scores)

        # 取得學費
        international_fee = next(
            (fee["estimated_annual_fee"] for fee in  organized_fields["fees"] if fee["fee_type"]["label"] == "International Fee-paying"), 
            None
        )

        # 解析duration
        matches = re.findall(r'(\d+(?:\.\d+)?)\s+years?', response.meta["duration_info"])
        duration = min(float(match) for match in matches) if matches else None

        # 提取符合條件的 location
        locations = {item["location"] for item in organized_fields["offering"] if "International students studying within Australia on a visa" in item["student_types"]}
        campus = ", ".join(locations)

        university = UniversityScrapyItem()
        university['university_id'] = 5
        university['name'] = response.meta["course_name"]  
        university['min_fee'] = international_fee
        university['max_fee'] = international_fee
        university['eng_req'] = eng_req
        university['eng_req_info'] = eng_req_info
        university['campus'] = campus
        university['duration'] = duration
        university['duration_info'] =  response.meta["duration_info"]
        university['degree_level_id'] =  response.meta["degree_level_id"]
        university['course_url'] = response.meta["course_url"]  

        yield university      

    def closed(self, reason):
        print(f'{self.name}爬蟲完畢\n麥覺理大學，共 {len(self.all_course_url) - self.except_count} 筆資料(已扣除不開放申請)')
