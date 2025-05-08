from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai
import os
import time
import threading
import schedule
import re
from datetime import datetime, timedelta

from utils.vnexpress import crawl_vnexpress_article
from utils.dantri import crawl_dantri_article
from utils.tuoitre import crawl_tuoitre_article
from utils.thanhnien import crawl_thanhnien_article
from utils._24h import crawl_24h_article
from utils.baobinhphuoc import crawl_baobinhphuoc_article
from utils.baocongthuong import crawl_baocongthuong_article
from utils.baodautu import crawl_baodautu_article
from utils.baophapluat import crawl_baophapluat_article
from utils.baophunuthudo import crawl_baophunuthudo_article
from utils.baoquocte import crawl_baoquocte_article
from utils.baochinhphu import crawl_baochinhphu_article
from utils.baoxaydung import crawl_baoxaydung_article
from utils.bbc import crawl_bbc_article
from utils.cand import crawl_cand_article
from utils.congngheviet import crawl_congngheviet_article
from utils.dantoc import crawl_dantoc_article
from utils.genz import crawl_genz_article
from utils.giaoducthoidai import crawl_giaoducthoidai_article
from utils.laodong import crawl_laodong_article
from utils.nhandan import crawl_nhandan_article
from utils.nld import crawl_nld_article
from utils.nongnghiepmoitruong import crawl_nongnghiepmoitruong_article
from utils.phongvu import crawl_phongvu_article
from utils.qdnd import crawl_qdnd_article
from utils.soha import crawl_soha_article
from utils.suckhoedoisong import crawl_suckhoedoisong_article
from utils.tapchicongsan import crawl_tapchicongsan_article
from utils.thanhtra import crawl_thanhtra_article
from utils.thoibaonganhang import crawl_thoibaonganhang_article
from utils.thoibaotaichinhvietnam import crawl_thoibaotaichinhvietnam_article
from utils.tinnhanhchungkhoan import crawl_tinnhanhchungkhoan_article
from utils.toquoc import crawl_toquoc_article
from utils.tuoitrethudo import crawl_tuoitrethudo_article
from utils.vietnam import crawl_vietnam_article
from utils.vietnamnet import crawl_vietnamnet_article
from utils.vietnamnews import crawl_vietnamnews_article
from utils.vietnamplus import crawl_vietnamplus_article


app = Flask(__name__)

# Cấu hình Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDKEnG-QYRkJzYpZd5ibmVswhAjtsnFOkU")
genai.configure(api_key=GEMINI_API_KEY)

def connect_to_mongodb():
    try:
        client = MongoClient("mongodb+srv://Death:DeathA_1205@death.8wudq.mongodb.net/ThayUy?retryWrites=true&w=majority&appName=Death")
        client.admin.command('ping')
        print("MongoDB conneted")
        db = client['CoLy']
        return db
    except ConnectionFailure as e:
        print(f"Không thể kết nối với MongoDB: {e}")
        return None

def summarize_content(keyword, content, max_sentences=12): #GeminiAPI
    if not content or len(content.strip()) < 80:
        return None
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"Hãy đọc nội dung sau và so sánh với nội dung mà từ khóa '{keyword}' yêu cầu. "
            f"Nếu nội dung không liên quan hoặc không phù hợp, hãy trả về kết quả rỗng. "
            f"Nếu nội dung phù hợp, hãy tóm tắt nội dung đó trong tối đa {max_sentences} câu, "
            f"đảm bảo bao quát toàn bộ nội dung và giữ lại các thông tin quan trọng. "
            f"Nếu nội dung là tiếng nước ngoài, hãy dịch sang tiếng Việt một cách chính xác và tự nhiên, "
            f"phù hợp với phong cách báo chí và dễ hiểu với người đọc thông thường.\n\n"
            f"{content}"
        )

        response = model.generate_content(prompt)
        summary = response.text.strip()
        return summary if summary else None
    
    except Exception as e:
        print(f"Error summarizing content: {e}")
        return None

def create_collection_with_ttl(db, collection_name): #collection tu dong xoa sau 3 ngay
    collection = db[collection_name]
    collection.create_index("crawled_at", expireAfterSeconds=259200) #tinh bang giay
    return collection


def crawl_google_news(keyword): #crawl RSS
    url = f"https://news.google.com/rss/search?q={keyword}&hl=vi&gl=VN&ceid=VN:vi"

    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-data-{int(time.time())}")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--host-resolver-rules='MAP * 8.8.8.8, EXCLUDE localhost'")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'xml')
        items = soup.find_all('item')
        news_data = []
        
        for item in items:
            news_item = {
                'title': item.find('title').text if item.find('title') else None,
                'link': item.find('link').text if item.find('link') else None,
                'pub_date': item.find('pubDate').text if item.find('pubDate') else None,
                'description': item.find('description').text if item.find('description') else None,
                'source': item.find('source').text if item.find('source') else None,
                'source_url': item.find('source')['url'] if item.find('source') and item.find('source').has_attr('url') else None
            }
            news_data.append(news_item)
        
        return news_data, driver
    
    except Exception as e:
        print(f"Error occurred while crawling RSS: {e}")
        return None, driver

def get_real_url_after_redirect(driver, google_news_url): #lay URL thuc de thuc hien soup
    try:
        driver.get(google_news_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            if links and len(links) > 0:
                for link in links:
                    href = link.get_attribute('href')
                    if href and 'news.google.com' not in href:
                        link.click()
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        break
        except Exception as e:
            print(f"Lỗi khi thử click vào link: {e}")
            
        time.sleep(5)
        
        current_url = driver.current_url
        
        if 'news.google.com' not in current_url:
            return current_url
        
        html = driver.page_source
        canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', html, re.IGNORECASE)
        if canonical_match:
            canonical_url = canonical_match.group(1)
            if canonical_url and 'news.google.com' not in canonical_url:
                return canonical_url
        
        og_url_match = re.search(r'<meta\s+property=["\']og:url["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if og_url_match:
            og_url = og_url_match.group(1)
            if og_url and 'news.google.com' not in og_url:
                return og_url
                
        canonical_element = driver.find_elements(By.CSS_SELECTOR, "link[rel='canonical']")
        if canonical_element and len(canonical_element) > 0:
            canonical_url = canonical_element[0].get_attribute('href')
            if canonical_url and 'news.google.com' not in canonical_url:
                return canonical_url
        
        og_url_element = driver.find_elements(By.CSS_SELECTOR, "meta[property='og:url']")
        if og_url_element and len(og_url_element) > 0:
            og_url = og_url_element[0].get_attribute('content')
            if og_url and 'news.google.com' not in og_url:
                return og_url

        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes and len(iframes) > 0:
                for i, iframe in enumerate(iframes):
                    try:
                        driver.switch_to.frame(iframe)
                        
                        # Tìm thẻ canonical trong iframe
                        canonical_in_iframe = driver.find_elements(By.CSS_SELECTOR, "link[rel='canonical']")
                        if canonical_in_iframe and len(canonical_in_iframe) > 0:
                            canonical_url = canonical_in_iframe[0].get_attribute('href')
                            if canonical_url and 'news.google.com' not in canonical_url:
                                driver.switch_to.default_content()
                                return canonical_url
                        
                        driver.switch_to.default_content()
                    except Exception as e:
                        driver.switch_to.default_content()
        except Exception as e:
            pass
                            
        # Kiểm tra nếu có thẻ a với href không phải Google News
        links = driver.find_elements(By.TAG_NAME, "a")
        if links and len(links) > 0:
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and 'news.google.com' not in href:
                        return href
                except:
                    continue
        
        # Trả về URL hiện tại nếu không tìm thấy URL nào khác
        return current_url
        
    except Exception as e:
        print(f"Lỗi khi truy cập URL {google_news_url}: {e}")
        return None

def visit_article_links(keyword, news_data, driver, collection):
    """
    Truy cập từng liên kết bài báo và crawl nội dung.
    """
    for item in news_data:
        link = item['link']
        title = item['title']
        pubDate = item['pub_date']
        if not link:
            continue
        
        try:
            print(f"Đang truy cập: {link}")
            
            # Lấy URL thực sau khi chuyển hướng
            real_url = get_real_url_after_redirect(driver, link)
            if not real_url:
                print(f"Không thể lấy URL thực từ: {link}")
                continue
                
            print(f"URL thực: {real_url}")
            
            # Xác định nguồn dựa trên URL thực
            source_type = None
            source_mapping = {
                'vnexpress.net': ('vnexpress', crawl_vnexpress_article),
                'dantri.com.vn': ('dantri', crawl_dantri_article),
                'tuoitre.vn': ('tuoitre', crawl_tuoitre_article),
                'thanhnien.vn': ('thanhnien', crawl_thanhnien_article),
                '24h.com.vn': ('24h', crawl_24h_article),
                'baobinhphuoc.com.vn': ('baobinhphuoc', crawl_baobinhphuoc_article),
                'congthuong.vn': ('baocongthuong', crawl_baocongthuong_article),
                'baodautu.vn': ('baodautu', crawl_baodautu_article),
                'baophapluat.vn': ('baophapluat', crawl_baophapluat_article),
                'baophunuthudo.vn': ('baophunuthudo', crawl_baophunuthudo_article),
                'baoquocte.vn': ('baoquocte', crawl_baoquocte_article),
                'baochinhphu.vn': ('baochinhphu', crawl_baochinhphu_article),
                'baoxaydung.vn': ('baoxaydung', crawl_baoxaydung_article),
                'bbc.com': ('bbc', crawl_bbc_article),
                'cand.com.vn': ('cand', crawl_cand_article),
                'congngheviet.com': ('congngheviet', crawl_congngheviet_article),
                'genz.com.vn': ('genz', crawl_genz_article),
                'giaoducthoidai.vn': ('giaoducthoidai', crawl_giaoducthoidai_article),
                'laodong.vn': ('laodong', crawl_laodong_article),
                'nhandan.vn': ('nhandan', crawl_nhandan_article),
                'nld.com.vn': ('nld', crawl_nld_article),
                'nongnghiepmoitruong.vn': ('nongnghiepmoitruong', crawl_nongnghiepmoitruong_article),
                'phongvu.vn': ('phongvu', crawl_phongvu_article),
                'qdnd.vn': ('qdnd', crawl_qdnd_article),
                'soha.vn': ('soha', crawl_soha_article),
                'suckhoedoisong.vn': ('suckhoedoisong', crawl_suckhoedoisong_article),
                'tapchicongsan.org.vn': ('tapchicongsan', crawl_tapchicongsan_article),
                'thanhtra.com.vn': ('thanhtra', crawl_thanhtra_article),
                'thoibaonganhang.vn': ('thoibaonganhang', crawl_thoibaonganhang_article),
                'thoibaotaichinhvietnam.vn': ('thoibaotaichinhvietnam', crawl_thoibaotaichinhvietnam_article),
                'tinnhanhchungkhoan.vn': ('tinnhanhchungkhoan', crawl_tinnhanhchungkhoan_article),
                'toquoc.vn': ('toquoc', crawl_toquoc_article),
                'tuoitrethudo.vn': ('tuoitrethudo', crawl_tuoitrethudo_article),
                'vietnam.vn': ('vietnam', crawl_vietnam_article),
                'vietnamnet.vn': ('vietnamnet', crawl_vietnamnet_article),
                'vietnamnews.vn': ('vietnamnews', crawl_vietnamnews_article),
                'vietnamplus.vn': ('vietnamplus', crawl_vietnamplus_article),
            }


            for domain, (source_type, crawl_func) in source_mapping.items():
                if domain in real_url:
                    article_data = crawl_func(keyword, real_url, driver, title, pubDate)
                    break
            else:
                print(f"Không hỗ trợ nguồn: {real_url}")
                continue
            
            # Cập nhật thông tin nguồn
            if article_data and 'error' not in article_data:
                article_data['original_link'] = link
                article_data['real_link'] = real_url
                article_data['source_url'] = real_url
                if source_type:
                    article_data['source'] = source_type
            
            if collection is not None and article_data:
                collection.insert_one(article_data)
            
            time.sleep(5)
            
        except Exception as e:
            print(f"Lỗi khi xử lý bài báo từ {link}: {e}")

def crawl_in_background(keyword, db):
    """
    Chạy crawl trong luồng nền và lưu vào collection riêng của từ khóa.
    """
    collection = create_collection_with_ttl(db, keyword)
    driver = None
    try:
        news_data, driver = crawl_google_news(keyword)
        if news_data:
            visit_article_links(keyword, news_data, driver, collection)
    except Exception as e:
        print(f"Lỗi khi crawl tin tức cho từ khóa {keyword}: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def cleanup_collections():
    """
    Xóa collection nếu không có cập nhật mới trong 2 ngày.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để dọn dẹp collections")
        return
    
    keywords_collection = db['keywords']
    keywords = [k['keyword'] for k in keywords_collection.find()]
    
    for keyword in keywords:
        collection = db[keyword]
        latest_article = collection.find_one(sort=[('crawled_at', -1)])
        
        if latest_article:
            latest_time = latest_article['crawled_at']
            if datetime.utcnow() - latest_time > timedelta(days=2):
                print(f"Drop collection {keyword} vì không có cập nhật trong 2 ngày.")
                db.drop_collection(keyword)
                keywords_collection.delete_one({'keyword': keyword})
        else:
            print(f"Drop collection {keyword} vì không có dữ liệu.")
            db.drop_collection(keyword)
            keywords_collection.delete_one({'keyword': keyword})

def crawl_all_keywords():
    """
    Crawl bài báo cho tất cả từ khóa trong collection keywords.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để crawl tất cả từ khóa")
        return
    
    keywords_collection = db['keywords']
    keywords = [k['keyword'] for k in keywords_collection.find()]
    
    for keyword in keywords:
        print(f"Crawl theo lịch cho từ khóa: {keyword}")
        threading.Thread(target=crawl_in_background, args=(keyword, db)).start()

def schedule_tasks():
    """
    Lập lịch crawl và cleanup.
    """
    # Crawl hàng ngày lúc 8:00 sáng
    schedule.every().day.at("08:00").do(crawl_all_keywords)
    # Cleanup collection lúc 2:00 sáng
    schedule.every().day.at("02:00").do(cleanup_collections)
    
    # Chạy lịch trong luồng nền
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    threading.Thread(target=run_schedule, daemon=True).start()

@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    keywords = [k['keyword'] for k in keywords_collection.find()]
    return jsonify({'keywords': keywords})

@app.route('/api/keywords', methods=['POST'])
def add_keyword():
    data = request.get_json()
    keyword = data.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Từ khóa không hợp lệ'}), 400
    
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    if keywords_collection.find_one({'keyword': keyword}):
        return jsonify({'message': f'Từ khóa "{keyword}" đã tồn tại'}), 200
    
    keywords_collection.insert_one({'keyword': keyword})
    create_collection_with_ttl(db, keyword)
    
    return jsonify({'message': f'Đã thêm từ khóa "{keyword}"'}), 200

@app.route('/api/keywords/<keyword>', methods=['DELETE'])
def delete_keyword(keyword):
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    result = keywords_collection.delete_one({'keyword': keyword})
    
    if result.deleted_count > 0:
        db.drop_collection(keyword)
        return jsonify({'message': f'Đã xóa từ khóa "{keyword}" và collection tương ứng'}), 200
    return jsonify({'error': f'Từ khóa "{keyword}" không tồn tại'}), 404

@app.route('/api/crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    keyword = data.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Từ khóa không hợp lệ'}), 400
    
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    if not keywords_collection.find_one({'keyword': keyword}):
        return jsonify({'error': f'Từ khóa "{keyword}" không tồn tại'}), 404
    
    threading.Thread(target=crawl_in_background, args=(keyword, db)).start()
    
    return jsonify({'message': f'Đã bắt đầu crawl cho từ khóa "{keyword}"'}), 200

@app.route('/api/articles', methods=['GET'])
def get_articles():
    keyword = request.args.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Yêu cầu cung cấp từ khóa'}), 400
    
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    if not keywords_collection.find_one({'keyword': keyword}):
        return jsonify({'error': f'Từ khóa "{keyword}" không tồn tại'}), 404
    
    collection = db[keyword]
    
    articles = list(collection.find({}, {
        '_id': 0,
        'title': 1,
        'link': 1,
        'description': 1,
        'pub_date': 1,
        'content': 1,
        'text_content': 1,
        'source': 1,
        'summary': 1,
        'crawled_at': 1
    }).sort('crawled_at', -1).limit(50))
    
    return jsonify({'articles': articles})

@app.route('/api/daily-report', methods=['GET'])
def get_daily_report():
    keyword = request.args.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Yêu cầu cung cấp từ khóa'}), 400
    
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keywords_collection = db['keywords']
    if not keywords_collection.find_one({'keyword': keyword}):
        return jsonify({'error': f'Từ khóa "{keyword}" không tồn tại'}), 404
    
    collection = db[keyword]
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    articles = list(collection.find({
        'crawled_at': {'$gte': today}
    }, {
        '_id': 0,
        'title': 1,
        'link': 1,
        'description': 1,
        'summary': 1,
        'source': 1
    }).sort('crawled_at', -1))
    
    report = {
        'keyword': keyword,
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'total_articles': len(articles),
        'articles': articles
    }
    
    return jsonify(report)

if __name__ == '__main__':
    schedule_tasks()
    app.run(debug=True, host='0.0.0.0', port=5000)