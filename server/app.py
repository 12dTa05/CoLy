from flask import Flask, request, jsonify, session
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
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
from datetime import datetime, timedelta, timezone

from newspaper import Article
import tldextract

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
CORS(app)
bcrypt = Bcrypt(app)
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
jwt = JWTManager(app)

# Cấu hình Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBjb1Ez_KrFfXrWsCrlvyk3SPB9ZqKhyBI") #AIzaSyBuvd60gK2qW7znvFW-8I6A7ReE1Sc1TOE , AIzaSyDKEnG-QYRkJzYpZd5ibmVswhAjtsnFOkU, AIzaSyBjb1Ez_KrFfXrWsCrlvyk3SPB9ZqKhyBI
genai.configure(api_key=GEMINI_API_KEY)

def connect_to_mongodb():
    try:
        client = MongoClient("mongodb+srv://Death:DeathA_1205@death.8wudq.mongodb.net/CoLy?retryWrites=true&w=majority&appName=Death")
        client.admin.command('ping')
        print("MongoDB connected")
        db = client['CoLy']
        
        # Tạo indexes
        db.articles.create_index("expires_at", expireAfterSeconds=0)
        db.articles.create_index("keywords")
        db.articles.create_index("real_link", unique=True)
        db.user_keyword_subscriptions.create_index([("user_id", 1), ("keyword_id", 1)], unique=True)
        
        return db
    except ConnectionFailure as e:
        print(f"Không thể kết nối với MongoDB: {e}")
        return None

def summarize_content(keyword, content, max_sentences=12): #GeminiAPI
    if not content or len(content.strip()) < 80:
        return 'None'
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"Hãy đọc nội dung sau và so sánh với nội dung mà từ khóa '{keyword}' yêu cầu."
            f"Nếu nội dung không liên quan hoặc không phù hợp, hãy trả về đúng một dòng: 'None'."
            f"Nếu nội dung phù hợp, hãy tóm tắt nội dung đó trong tối đa {max_sentences} câu,"
            f"đảm bảo bao quát toàn bộ nội dung và giữ lại các thông tin quan trọng."
            f"Nếu nội dung là tiếng nước ngoài, hãy dịch sang tiếng Việt một cách chính xác và tự nhiên,"
            f"phù hợp với phong cách báo chí và dễ hiểu với người đọc thông thường.\n\n"
            f"{content}"
        )

        response = model.generate_content(prompt)
        summary = response.text.strip()

        return summary if summary else None
    
    except Exception as e:
        print(f"Error summarizing content: {e}")
        return 'None'

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
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            if links and len(links) > 0:
                for link in links:
                    href = link.get_attribute('href')
                    if href and 'news.google.com' not in href:
                        link.click()
                        WebDriverWait(driver, 12).until(
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

def visit_article_links(keyword, news_data, driver, db, keyword_id):
    """
    Xử lý bài báo và lưu vào collection articles.
    """
    article_count = 0
    time.sleep(12)
    
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
            
            # Kiểm tra xem bài báo đã tồn tại chưa
            existing_article = db.articles.find_one({'real_link': real_url})
            if existing_article:
                # Nếu đã tồn tại nhưng chưa liên kết với từ khóa hiện tại
                if ObjectId(keyword_id) not in existing_article.get('keywords', []):
                    db.articles.update_one(
                        {'_id': existing_article['_id']},
                        {'$addToSet': {'keywords': ObjectId(keyword_id)}}
                    )
                    article_count += 1
                continue
            
            # Xác định nguồn và crawl nội dung
            article_data = None
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
            
            # Nếu không tìm thấy nguồn cụ thể, sử dụng newspaper library
            if not article_data:
                try:
                    article = Article(real_url)
                    article.download()
                    article.parse()

                    summary = summarize_content(keyword, article.text)
                    if summary == 'None':
                        continue
                    else:                        
                        article_data = {
                            'title': title.split('-')[0].strip() if title else None,
                            'description': article.meta_description,
                            'pub_date': pubDate,
                            'content': article.text,
                            'source': f"{(tldextract.extract(real_url)).domain}.{(tldextract.extract(real_url)).suffix}",
                            'summary': summary
                        }
                except Exception as e:
                    print(e)
                    continue
            
            if article_data:
                # Cập nhật thông tin bài báo
                article_data.update({
                    'link': link,
                    'real_link': real_url,
                    'original_link': link,
                    'keywords': [ObjectId(keyword_id)],
                    'crawled_at': datetime.now(timezone.utc),
                    'expires_at': datetime.now(timezone.utc) + timedelta(days=30)  # TTL 30 ngày
                })
                
                # Lưu bài báo vào collection
                db.articles.insert_one(article_data)
                article_count += 1
                
        except Exception as e:
            print(f"Lỗi khi xử lý bài báo từ {link}: {e}")
            time.sleep(5)
    
    return article_count

def crawl_in_background(keyword, db, keyword_id, job_id):
    """
    Chạy crawl trong luồng nền và lưu vào collection articles.
    Tự động tạo bài tổng hợp sau khi crawl xong.
    """
    try:
        # Cập nhật trạng thái job
        db.crawl_jobs.update_one(
            {'_id': job_id},
            {'$set': {'status': 'running'}}
        )
        
        # Thực hiện crawl
        news_data, driver = crawl_google_news(keyword)
        article_count = 0
        
        if news_data:
            article_count = visit_article_links(keyword, news_data, driver, db, keyword_id)
        
        # Cập nhật thông tin từ khóa
        db.keywords.update_one(
            {'_id': ObjectId(keyword_id)},
            {
                '$set': {'last_crawled_at': datetime.now(timezone.utc)},
                '$inc': {'article_count': article_count}
            }
        )
        
        # Cập nhật trạng thái job
        db.crawl_jobs.update_one(
            {'_id': job_id},
            {
                '$set': {
                    'status': 'completed',
                    'finished_at': datetime.now(timezone.utc),
                    'article_count': article_count
                }
            }
        )
        
        # Tạo bài tổng hợp ngay sau khi crawl xong
        if article_count >= 3:  # Chỉ tạo bài tổng hợp nếu có ít nhất 3 bài báo mới
            today = datetime.now(timezone.utc)
            summary_id = generate_daily_summary(keyword, keyword_id, today, db)
            
            if summary_id:
                # Cập nhật job với thông tin bài tổng hợp
                db.crawl_jobs.update_one(
                    {'_id': job_id},
                    {'$set': {'summary_id': summary_id}}
                )
                print(f"Đã tạo bài tổng hợp cho từ khóa '{keyword}'")
        
    except Exception as e:
        print(f"Lỗi khi crawl tin tức cho từ khóa {keyword}: {e}")
        # Cập nhật trạng thái job thất bại
        db.crawl_jobs.update_one(
            {'_id': job_id},
            {
                '$set': {
                    'status': 'failed',
                    'finished_at': datetime.now(timezone.utc),
                    'error': str(e)
                }
            }
        )
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def cleanup_expired_articles():
    """
    Xóa các bài báo hết hạn và cập nhật số lượng bài báo cho từ khóa.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để dọn dẹp bài báo")
        return
    
    # Lấy danh sách từ khóa
    keywords = list(db.keywords.find({}, {'_id': 1}))
    
    for keyword in keywords:
        keyword_id = keyword['_id']
        
        # Đếm số bài báo hiện tại của từ khóa
        article_count = db.articles.count_documents({'keywords': keyword_id})
        
        # Cập nhật số lượng bài báo
        db.keywords.update_one(
            {'_id': keyword_id},
            {'$set': {'article_count': article_count}}
        )

def cleanup_inactive_keywords():
    """
    Xóa các từ khóa không có người đăng ký.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để dọn dẹp từ khóa")
        return
    
    # Lấy danh sách từ khóa có người đăng ký
    subscribed_keywords = set()
    subscriptions = db.user_keyword_subscriptions.find({}, {'keyword_id': 1})
    
    for subscription in subscriptions:
        subscribed_keywords.add(subscription['keyword_id'])
    
    # Lấy tất cả từ khóa
    all_keywords = list(db.keywords.find({}, {'_id': 1}))
    
    # Xóa các từ khóa không có người đăng ký
    for keyword in all_keywords:
        if keyword['_id'] not in subscribed_keywords:
            db.keywords.delete_one({'_id': keyword['_id']})
            print(f"Đã xóa từ khóa không hoạt động: {keyword['_id']}")

def auto_crawl_all_keywords():
    """
    Tự động crawl tất cả từ khóa hoạt động.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để tự động crawl")
        return
    
    # Lấy danh sách từ khóa có người đăng ký
    subscribed_keywords = set()
    subscriptions = db.user_keyword_subscriptions.find({}, {'keyword_id': 1})
    
    for subscription in subscriptions:
        subscribed_keywords.add(subscription['keyword_id'])
    
    # Crawl các từ khóa có người đăng ký
    for keyword_id in subscribed_keywords:
        keyword_data = db.keywords.find_one({'_id': keyword_id})
        if keyword_data and keyword_data.get('status') == 'active':
            # Tạo job crawl mới
            job_id = db.crawl_jobs.insert_one({
                'keyword_id': keyword_id,
                'status': 'pending',
                'started_at': datetime.now(timezone.utc),
                'triggered_by': 'system'
            }).inserted_id
            
            # Bắt đầu crawl trong luồng riêng
            threading.Thread(target=crawl_in_background, args=(keyword_data['keyword'], db, keyword_id, job_id)).start()
            print(f"Tự động crawl từ khóa: {keyword_data['keyword']}")

            time.sleep(90)

def generate_daily_summary(keyword, keyword_id, date, db):
    """
    Tạo bài tổng hợp hàng ngày cho từng từ khóa sử dụng phương pháp phân nhóm và hai API Gemini.
    """
    # Lấy tất cả bài báo của từ khóa trong ngày
    start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    articles = list(db.articles.find({
        'keywords': ObjectId(keyword_id),
        'crawled_at': {'$gte': start_date, '$lte': end_date}
    }).sort('crawled_at', -1))
    
    if not articles or len(articles) < 3:
        print(f"Không đủ bài báo để tổng hợp cho từ khóa '{keyword}' ngày {date.strftime('%Y-%m-%d')}")
        return None

    # Tóm tắt từng bài báo bằng TextRank
    summarized_articles = []
    for article in articles:
        content = article.get('summary') or article.get('content') or ''
        short_summary = textrank_summarize(content, sentence_count=5)
        summarized_articles.append({
            'title': article['title'],
            'url': article['real_link'],
            'summary': short_summary
        })

    # Phân nhóm bài báo thành các nhóm nhỏ hơn
    chunk_size = 5  # Theo yêu cầu của Đại ca
    article_chunks = [summarized_articles[i:i+chunk_size] for i in range(0, len(summarized_articles), chunk_size)]
    
    # Tạo tóm tắt cho từng nhóm
    chunk_summaries = []
    for chunk_index, chunk in enumerate(article_chunks):
        chunk_prompt = f"""
        Hãy tạo một đoạn tổng hợp thông tin ngắn về chủ đề "{keyword}" dựa trên các bài báo sau.
        Hãy trích dẫn nguồn thông tin bằng cú pháp [tiêu đề](url).
        Đoạn tổng hợp cần ngắn gọn nhưng vẫn bao quát được nội dung chính của các bài báo.
        
        Dữ liệu các bài báo (Nhóm {chunk_index + 1}/{len(article_chunks)}):
        """
        
        for i, article in enumerate(chunk):
            chunk_prompt += f"""
            --- Bài {i+1} ---
            Tiêu đề: {article['title']}
            URL: {article['url']}
            Nội dung: {article['summary']}
            """
        
        try:
            # Sử dụng Gemini Flash cho phần tóm tắt nhóm (API thứ nhất)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(chunk_prompt)
            chunk_summaries.append(response.text.strip())
            
            # Đợi 1 giây để tránh gọi API quá nhanh
            import time
            time.sleep(1)
            
        except Exception as e:
            print(f"Lỗi khi tóm tắt nhóm bài báo {chunk_index + 1}: {e}")
            # Nếu có lỗi, thêm một phần tóm tắt đơn giản
            simple_summary = f"Nhóm {chunk_index + 1} bao gồm các bài báo: " + ", ".join([a['title'] for a in chunk])
            chunk_summaries.append(simple_summary)
    
    # Tạo prompt cuối cùng với các tóm tắt nhóm
    final_prompt = f"""
    Viết một bài tổng hợp tin tức ngày {date.strftime('%Y-%m-%d')} về chủ đề "{keyword}", dựa trên các tóm tắt nhóm bài báo sau.
    
    Yêu cầu quan trọng:
    1. Viết như một bài báo chính thức, với văn phong mạch lạc, chuyên nghiệp, báo chí
    2. Cấu trúc bài viết rõ ràng với mở bài, thân bài và kết luận
    3. Mỗi khi đưa ra thông tin cụ thể từ một bài báo, PHẢI đặt tham chiếu đến bài báo gốc bằng cú pháp [tiêu đề](URL)
    4. Diễn đạt bằng từ ngữ sáng tạo, tránh sao chép nguyên văn
    5. Đặt tựa đề phù hợp cho bài viết
    
    Dưới đây là các tóm tắt theo nhóm bài báo:
    """
    
    for i, summary in enumerate(chunk_summaries):
        final_prompt += f"\n--- Nhóm {i+1} ---\n{summary}\n"
    
    # Thêm danh sách tham chiếu
    reference_list = "\nDanh sách bài báo tham khảo:\n"
    for article in summarized_articles:
        reference_list += f"- [{article['title']}]({article['url']})\n"
    
    # Kiểm tra nếu prompt quá dài, có thể rút gọn phần danh sách tham khảo
    if len(final_prompt) + len(reference_list) > 100000:  # Giả sử giới hạn token
        reference_list = f"\nDanh sách bài báo tham khảo: (Tổng cộng {len(summarized_articles)} bài)\n"
        # Chỉ thêm 20 bài đầu tiên
        for article in summarized_articles[:20]:
            reference_list += f"- [{article['title']}]({article['url']})\n"
        reference_list += "- ... và các bài khác."
    
    final_prompt += reference_list

    try:
        # Sử dụng Gemini Pro cho bài tổng hợp cuối cùng (API thứ hai)
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBuvd60gK2qW7znvFW-8I6A7ReE1Sc1TOE") #AIzaSyBuvd60gK2qW7znvFW-8I6A7ReE1Sc1TOE , AIzaSyDKEnG-QYRkJzYpZd5ibmVswhAjtsnFOkU, AIzaSyBjb1Ez_KrFfXrWsCrlvyk3SPB9ZqKhyBI
        genai.configure(api_key=GEMINI_API_KEY)

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(final_prompt)
        summary_content = response.text.strip()
        
        print(f"Gemini API, độ dài: {len(summary_content)}")
        
        # Tạo phiên bản plain text (không có HTML)
        plain_content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', summary_content)
        
        # Lưu bài tổng hợp vào database
        article_ids = [article['_id'] for article in articles]
        article_sources = list(set(article['source'] for article in articles))
        
        # Kiểm tra xem đã có bài tổng hợp cho từ khóa và ngày này chưa
        existing_summary = db.daily_summaries.find_one({
            'keyword_id': ObjectId(keyword_id),
            'date': start_date
        })
        
        if existing_summary:
            # Cập nhật bài tổng hợp đã có
            db.daily_summaries.update_one(
                {'_id': existing_summary['_id']},
                {
                    '$set': {
                        'content': summary_content,
                        'plain_content': plain_content,
                        'article_count': len(articles),
                        'article_sources': article_sources,
                        'article_ids': article_ids,
                        'created_at': datetime.now(timezone.utc)
                    }
                }
            )
            summary_id = existing_summary['_id']
        else:
            # Tạo bài tổng hợp mới
            summary_id = db.daily_summaries.insert_one({
                'keyword_id': ObjectId(keyword_id),
                'keyword_text': keyword,
                'date': start_date,
                'content': summary_content,
                'plain_content': plain_content,
                'article_count': len(articles),
                'article_sources': article_sources,
                'article_ids': article_ids,
                'created_at': datetime.now(timezone.utc)
            }).inserted_id
        
        print(f"Đã tạo bài tổng hợp cho từ khóa '{keyword}' ngày {date.strftime('%Y-%m-%d')}")
        return summary_id
    
    except Exception as e:
        print(f"Lỗi khi tạo bài tổng hợp cuối cùng cho từ khóa '{keyword}': {e}")
        return None

def generate_all_summaries():
    """
    Tạo bài tổng hợp cho tất cả từ khóa có bài báo mới trong ngày.
    """
    db = connect_to_mongodb()
    if db is None:
        print("Không thể kết nối đến MongoDB để tạo bài tổng hợp")
        return
    
    # Lấy ngày hiện tại
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Lấy danh sách từ khóa có bài báo mới trong ngày
    pipeline = [
        {
            '$match': {
                'crawled_at': {'$gte': today}
            }
        },
        {
            '$unwind': '$keywords'
        },
        {
            '$group': {
                '_id': '$keywords',
                'count': {'$sum': 1}
            }
        },
        {
            '$match': {
                'count': {'$gte': 2}  # Chỉ tổng hợp từ khóa có ít nhất 2 bài
            }
        }
    ]
    
    keyword_stats = list(db.articles.aggregate(pipeline))
    
    for stat in keyword_stats:
        keyword_id = stat['_id']
        keyword_data = db.keywords.find_one({'_id': keyword_id})
        
        if keyword_data:
            generate_daily_summary(keyword_data['keyword'], keyword_id, today, db)
            # Đợi 10 giây giữa các lần gọi API để tránh quá tải
            time.sleep(12)

# Cập nhật lịch trình trong hàm schedule_tasks
def schedule_tasks():
    # Lịch crawl tự động hàng ngày
    schedule.every().day.at("07:00").do(auto_crawl_all_keywords)
    
    # Dọn dẹp bài báo và từ khóa không hoạt động
    schedule.every().day.at("02:00").do(cleanup_expired_articles)
    schedule.every().sunday.at("03:00").do(cleanup_inactive_keywords)
    
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    threading.Thread(target=run_schedule, daemon=True).start()

def serialize_mongo_doc(doc):
    """Chuyển đổi các giá trị ObjectId và datetime trong document MongoDB thành định dạng có thể serialize."""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_mongo_doc(item) for item in doc]
    
    if isinstance(doc, dict):
        for key, value in list(doc.items()):
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                doc[key] = serialize_mongo_doc(value)
        return doc
    
    if isinstance(doc, ObjectId):
        return str(doc)
    
    if isinstance(doc, datetime):
        return doc.isoformat()
    
    return doc

# API đăng ký người dùng
@app.route('/api/auth/register', methods=['POST'])
def register():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Thiếu thông tin đăng ký'}), 400
    
    # Kiểm tra user đã tồn tại
    if db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
        return jsonify({'error': 'Tên người dùng hoặc email đã tồn tại'}), 400
    
    # Mã hóa mật khẩu
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    # Thêm người dùng mới
    user_id = db.users.insert_one({
        'username': username,
        'email': email,
        'password': hashed_password,
        'role': 'user',
        'created_at': datetime.now(timezone.utc),
        'last_login': datetime.now(timezone.utc)
    }).inserted_id
    
    # Tạo token
    access_token = create_access_token(identity=str(user_id))
    
    return jsonify({
        'message': 'Đăng ký thành công',
        'access_token': access_token
    }), 201

# API đăng nhập
@app.route('/api/auth/login', methods=['POST'])
def login():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Vui lòng cung cấp tên đăng nhập và mật khẩu'}), 400
    
    user = db.users.find_one({'username': username})
    
    if user and bcrypt.check_password_hash(user['password'], password):
        # Cập nhật thời gian đăng nhập
        db.users.update_one({'_id': user['_id']}, {'$set': {'last_login': datetime.now(timezone.utc)}})
        
        # Tạo token
        access_token = create_access_token(identity=str(user['_id']))
        
        return jsonify({
            'message': 'Đăng nhập thành công',
            'access_token': access_token,
            'username': user['username']
        }), 200
    
    return jsonify({'error': 'Tên đăng nhập hoặc mật khẩu không đúng'}), 401

# API lấy thông tin người dùng
@app.route('/api/user/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    user_id = get_jwt_identity()
    
    user = db.users.find_one({'_id': ObjectId(user_id)}, {
        '_id': 0,
        'username': 1,
        'email': 1,
        'role': 1,
        'created_at': 1,
        'last_login': 1
    })
    
    if not user:
        return jsonify({'error': 'Không tìm thấy người dùng'}), 404
    
    return jsonify(user), 200

# API lấy danh sách từ khóa của người dùng
@app.route('/api/keywords', methods=['GET'])
@jwt_required()
def get_keywords():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    user_id = get_jwt_identity()
    
    # Lấy các từ khóa mà người dùng đã đăng ký
    pipeline = [
        {'$match': {'user_id': ObjectId(user_id)}},
        {'$lookup': {
            'from': 'keywords',
            'localField': 'keyword_id',
            'foreignField': '_id',
            'as': 'keyword_info'
        }},
        {'$unwind': '$keyword_info'},
        {'$project': {
            'id': {'$toString': '$keyword_info._id'},
            'keyword': '$keyword_info.keyword',
            'last_crawled_at': '$keyword_info.last_crawled_at',
            'article_count': '$keyword_info.article_count',
            'subscribed_at': 1,
            'notifications_enabled': 1
        }}
    ]
    
    subscriptions = list(db.user_keyword_subscriptions.aggregate(pipeline))

    serialized_subscriptions = serialize_mongo_doc(subscriptions)
    
    return jsonify({'keywords': subscriptions})

# API thêm từ khóa mới
@app.route('/api/keywords', methods=['POST'])
@jwt_required()
def add_keyword():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    data = request.get_json()
    keyword = data.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Từ khóa không hợp lệ'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra từ khóa đã tồn tại chưa
    existing_keyword = db.keywords.find_one({'keyword': keyword})
    
    if not existing_keyword:
        # Thêm từ khóa mới
        keyword_id = db.keywords.insert_one({
            'keyword': keyword,
            'created_at': datetime.now(timezone.utc),
            'created_by': ObjectId(user_id),
            'status': 'active',
            'article_count': 0
        }).inserted_id
    else:
        keyword_id = existing_keyword['_id']
        
        # Kiểm tra người dùng đã đăng ký từ khóa này chưa
        existing_subscription = db.user_keyword_subscriptions.find_one({
            'user_id': ObjectId(user_id),
            'keyword_id': keyword_id
        })

        
        if existing_subscription:
            return jsonify({'message': f'Đã đăng ký từ khóa "{keyword}"'}), 200
    
    # Thêm đăng ký từ khóa cho người dùng
    db.user_keyword_subscriptions.insert_one({
        'user_id': ObjectId(user_id),
        'keyword_id': keyword_id,
        'subscribed_at': datetime.now(timezone.utc),
        'notifications_enabled': True
    })
    
    return jsonify({
        'message': f'Đã thêm từ khóa "{keyword}"', 
        'id': str(keyword_id)
    }), 200

# API xóa đăng ký từ khóa
@app.route('/api/keywords/<keyword_id>', methods=['DELETE'])
@jwt_required()
def unsubscribe_keyword(keyword_id):
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    user_id = get_jwt_identity()
    
    # Xóa đăng ký từ khóa của người dùng
    result = db.user_keyword_subscriptions.delete_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if result.deleted_count > 0:
        return jsonify({'message': 'Đã hủy đăng ký từ khóa'}), 200
    
    return jsonify({'error': 'Không tìm thấy đăng ký từ khóa'}), 404

# API bắt đầu crawl cho từ khóa
@app.route('/api/crawl', methods=['POST'])
@jwt_required()
def start_crawl():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    data = request.get_json()
    keyword_id = data.get('keyword_id')
    
    if not keyword_id:
        return jsonify({'error': 'Thiếu ID từ khóa'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra từ khóa và quyền truy cập
    keyword_data = db.keywords.find_one({'_id': ObjectId(keyword_id)})
    if not keyword_data:
        return jsonify({'error': 'Không tìm thấy từ khóa'}), 404
    
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Kiểm tra xem đang có job crawl nào đang chạy không
    running_job = db.crawl_jobs.find_one({
        'keyword_id': ObjectId(keyword_id),
        'status': 'running'
    })
    
    if running_job:
        return jsonify({'message': 'Đang có tiến trình crawl đang chạy cho từ khóa này'}), 200
    
    # Tạo job crawl mới
    job_id = db.crawl_jobs.insert_one({
        'keyword_id': ObjectId(keyword_id),
        'status': 'pending',
        'started_at': datetime.now(timezone.utc),
        'triggered_by': ObjectId(user_id)
    }).inserted_id
    
    # Bắt đầu crawl trong luồng riêng
    threading.Thread(target=crawl_in_background, args=(keyword_data['keyword'], db, keyword_id, job_id)).start()
    
    return jsonify({
        'message': f'Đã bắt đầu crawl cho từ khóa "{keyword_data["keyword"]}"',
        'job_id': str(job_id)
    }), 200

# API lấy bài báo theo từ khóa
@app.route('/api/articles', methods=['GET'])
@jwt_required()
def get_articles():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keyword_id = request.args.get('keyword_id')
    
    if not keyword_id:
        return jsonify({'error': 'Yêu cầu cung cấp ID từ khóa'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra quyền truy cập từ khóa
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Lấy thông tin từ khóa
    keyword_data = db.keywords.find_one({'_id': ObjectId(keyword_id)})
    if not keyword_data:
        return jsonify({'error': 'Không tìm thấy từ khóa'}), 404
    
    # Lấy danh sách bài báo
    articles = list(db.articles.find(
        {'keywords': ObjectId(keyword_id)},
        {
            '_id': 1,
            'title': 1,
            'link': 1,
            'description': 1,
            'pub_date': 1,
            'source': 1,
            'summary': 1,
            'crawled_at': 1
        }
    ).sort('crawled_at', -1).limit(50))
    
    # Chuyển ObjectId thành string
    for article in articles:
        article['_id'] = str(article['_id'])
    
    return jsonify({
        'keyword': keyword_data['keyword'],
        'articles': articles
    })

# API lấy thông tin chi tiết bài báo
@app.route('/api/articles/<article_id>', methods=['GET'])
@jwt_required()
def get_article_detail(article_id):
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    user_id = get_jwt_identity()
    
    # Lấy thông tin bài báo
    article = db.articles.find_one({'_id': ObjectId(article_id)})
    if not article:
        return jsonify({'error': 'Không tìm thấy bài báo'}), 404
    
    # Kiểm tra quyền truy cập
    keyword_ids = article.get('keywords', [])
    has_access = False
    
    for keyword_id in keyword_ids:
        subscription = db.user_keyword_subscriptions.find_one({
            'user_id': ObjectId(user_id),
            'keyword_id': keyword_id
        })
        if subscription:
            has_access = True
            break
    
    if not has_access:
        return jsonify({'error': 'Bạn không có quyền truy cập bài báo này'}), 403
    
    # Chuyển ObjectId thành string
    article['_id'] = str(article['_id'])
    article['keywords'] = [str(kid) for kid in article['keywords']]
    
    return jsonify(article)

# API lấy báo cáo tin tức theo từ khóa
@app.route('/api/daily-report', methods=['GET'])
@jwt_required()
def get_daily_report():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keyword_id = request.args.get('keyword_id')
    
    if not keyword_id:
        return jsonify({'error': 'Yêu cầu cung cấp ID từ khóa'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra quyền truy cập từ khóa
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Lấy thông tin từ khóa
    keyword_data = db.keywords.find_one({'_id': ObjectId(keyword_id)})
    if not keyword_data:
        return jsonify({'error': 'Không tìm thấy từ khóa'}), 404
    
    # Lấy bài báo trong ngày
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    articles = list(db.articles.find(
        {
            'keywords': ObjectId(keyword_id),
            'crawled_at': {'$gte': today}
        },
        {
            '_id': 1,
            'title': 1,
            'link': 1,
            'description': 1,
            'summary': 1,
            'source': 1,
            'crawled_at': 1
        }
    ).sort('crawled_at', -1))
    
    # Chuyển ObjectId thành string
    for article in articles:
        article['_id'] = str(article['_id'])
    
    # Thống kê theo nguồn
    source_stats = {}
    for article in articles:
        source = article.get('source', 'Không xác định')
        if source in source_stats:
            source_stats[source] += 1
        else:
            source_stats[source] = 1
    
    report = {
        'keyword': keyword_data['keyword'],
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'total_articles': len(articles),
        'source_stats': source_stats,
        'articles': articles
    }
    
    return jsonify(report)

# API lấy lịch sử crawl của từ khóa
@app.route('/api/crawl-history', methods=['GET'])
@jwt_required()
def get_crawl_history():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keyword_id = request.args.get('keyword_id')
    
    if not keyword_id:
        return jsonify({'error': 'Yêu cầu cung cấp ID từ khóa'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra quyền truy cập từ khóa
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Lấy lịch sử crawl
    jobs = list(db.crawl_jobs.find(
        {'keyword_id': ObjectId(keyword_id)},
        {
            '_id': 1,
            'status': 1,
            'started_at': 1,
            'finished_at': 1,
            'article_count': 1,
            'error': 1
        }
    ).sort('started_at', -1).limit(10))
    
    # Chuyển ObjectId thành string
    for job in jobs:
        job['_id'] = str(job['_id'])
    
    return jsonify({'jobs': jobs})

# API lấy danh sách bài tổng hợp theo từ khóa
@app.route('/api/summaries', methods=['GET'])
@jwt_required()
def get_summaries():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    keyword_id = request.args.get('keyword_id')
    
    if not keyword_id:
        return jsonify({'error': 'Yêu cầu cung cấp ID từ khóa'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra quyền truy cập từ khóa
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Lấy danh sách bài tổng hợp
    summaries = list(db.daily_summaries.find(
        {'keyword_id': ObjectId(keyword_id)},
        {
            '_id': 1,
            'date': 1,
            'article_count': 1,
            'article_sources': 1,
            'created_at': 1
        }
    ).sort('date', -1).limit(10))
    
    # Chuyển ObjectId thành string
    for summary in summaries:
        summary['_id'] = str(summary['_id'])
    
    return jsonify({'summaries': summaries})

# API lấy chi tiết bài tổng hợp
@app.route('/api/summaries/<summary_id>', methods=['GET'])
@jwt_required()
def get_summary_detail(summary_id):
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    user_id = get_jwt_identity()
    
    # Lấy thông tin bài tổng hợp
    summary = db.daily_summaries.find_one({'_id': ObjectId(summary_id)})
    if not summary:
        return jsonify({'error': 'Không tìm thấy bài tổng hợp'}), 404
    
    # Kiểm tra quyền truy cập
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': summary['keyword_id']
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập bài tổng hợp này'}), 403
    
    # Chuyển ObjectId thành string
    summary['_id'] = str(summary['_id'])
    summary['keyword_id'] = str(summary['keyword_id'])
    
    # Chuyển danh sách ID bài báo thành string
    if 'article_ids' in summary:
        summary['article_ids'] = [str(aid) for aid in summary['article_ids']]
    
    return jsonify(summary)

# API tạo lại bài tổng hợp
@app.route('/api/summaries/regenerate', methods=['POST'])
@jwt_required()
def regenerate_summary():
    db = connect_to_mongodb()
    if db is None:
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu'}), 500
    
    data = request.get_json()
    keyword_id = data.get('keyword_id')
    date_str = data.get('date')  # Format: YYYY-MM-DD
    
    if not keyword_id or not date_str:
        return jsonify({'error': 'Thiếu thông tin cần thiết'}), 400
    
    user_id = get_jwt_identity()
    
    # Kiểm tra quyền truy cập từ khóa
    subscription = db.user_keyword_subscriptions.find_one({
        'user_id': ObjectId(user_id),
        'keyword_id': ObjectId(keyword_id)
    })
    
    if not subscription:
        return jsonify({'error': 'Bạn không có quyền truy cập từ khóa này'}), 403
    
    # Lấy thông tin từ khóa
    keyword_data = db.keywords.find_one({'_id': ObjectId(keyword_id)})
    if not keyword_data:
        return jsonify({'error': 'Không tìm thấy từ khóa'}), 404
    
    try:
        # Chuyển đổi date_str thành datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        
        # Tạo lại bài tổng hợp
        summary_id = generate_daily_summary(keyword_data['keyword'], keyword_id, date, db)
        
        if summary_id:
            return jsonify({
                'message': 'Đã tạo lại bài tổng hợp thành công',
                'summary_id': str(summary_id)
            }), 200
        else:
            return jsonify({'error': 'Không thể tạo bài tổng hợp'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

if __name__ == '__main__':
    schedule_tasks()
    app.run(debug=True, host='0.0.0.0', port=5000)