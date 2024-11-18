import scrapy
from scrapy_splash import SplashRequest 

lua_script = """
function main(splash, args)
  splash:set_viewport_size(1024, 768)
  assert(splash:go(args.url))
  
  while not splash:select('.lawyer-card-v2') do
    splash:wait(0.1)
    print('waiting...')
  end    
  return {html = splash:html()}
end
"""

class LawyersSpider(scrapy.Spider):
    name = "lawyers"
    allowed_domains = ["lawyercard.ai"]

    def start_requests(self):
        url = 'https://lawyercard.ai/lawyerCard'
        yield SplashRequest(
            url,
            self.parse,
            endpoint='execute',
            args={
                'lua_source': lua_script,
                'timeout': 90,
                'wait': 5,
            }
        )

    def parse(self, response):
        # 建立一個 response.html 檔案，將 response.body 寫入
        with open('response.html', 'w', encoding='utf-8') as f:
            f.write(response.body.decode('utf-8'))
        
        lawyer_cards = response.css('.lawyer-card-v2')    
        self.log(f'Found {len(lawyer_cards)} lawyer cards') 
