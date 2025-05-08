def crawl_tuoitre_article(keyword, link, driver, title, pubDate):
    """
    Crawl bài báo từ Tuổi Trẻ.
    """
    if 'tuoitre.vn' not in link:
        return {'error': 'Liên kết không thuộc Tuổi Trẻ', 'link': link}
    
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from datetime import datetime, timezone
        from bs4 import BeautifulSoup
        driver.get(link)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'html.parser')
        
        article_data = {
            'link': link,
            'title': title.split('-')[0].strip() if title else None,
            'description': None,
            'pub_date': pubDate,
            'content': None,
            'source': 'tuoitre',
            'summary': None,
            'crawled_at': datetime.now(timezone.utc)
        }
        
        description_tag = soup.find('h2', class_='detail-sapo')
        if description_tag and description_tag.find('p'):
            article_data['description'] = description_tag.text.strip()
        
        content_tag = soup.find('div', class_='detail-content afcbc-body')
        if content_tag:
            article_data['content'] = ' '.join(p.text.strip() for p in content_tag.find_all('p') if p.text.strip())
        
        if article_data['content']:
            from app import summarize_content
            article_data['summary'] = summarize_content(keyword, article_data['content'])
        
        if article_data['content'] is not None and article_data['summary'] != 'None':
            return article_data
    
    except Exception as e:
        print(f"Error occurred while crawling Tuổi Trẻ {link}: {e}")
        return None