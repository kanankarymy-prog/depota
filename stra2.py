import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# تنظیمات صفحه
st.set_page_config(page_title="Web Scraper", page_icon="🌐", layout="wide")

# CSS برای زیبایی
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🌐 Web Scraper Pro</div>', unsafe_allow_html=True)

def get_user_agent():
    """لیست User-Agent های مختلف برای جلوگیری از بلاک شدن"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return random.choice(user_agents)

def safe_request(url, max_retries=3):
    """درخواست امن با قابلیت تکرار"""
    headers = {
        'User-Agent': get_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for attempt in range(max_retries):
        try:
            # تأخیر تصادفی بین درخواست‌ها
            if attempt > 0:
                delay = random.uniform(2, 5)
                time.sleep(delay)
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # بررسی اینکه محتوای معتبر برگردانده شده
            if response.status_code == 200 and len(response.content) > 1000:
                return response
            else:
                st.warning(f"Attempt {attempt + 1}: Content too short, retrying...")
                
        except requests.exceptions.Timeout:
            st.warning(f"Attempt {attempt + 1}: Timeout occurred, retrying...")
        except requests.exceptions.HTTPError as e:
            st.error(f"Attempt {attempt + 1}: HTTP Error {e}")
            return None
        except requests.exceptions.RequestException as e:
            st.warning(f"Attempt {attempt + 1}: Connection error: {e}")
    
    st.error(f"Failed to fetch URL after {max_retries} attempts")
    return None

def extract_article_data(html_content):
    """استخراج داده‌های مقاله از محتوای HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # استخراج عنوان
    title = soup.find('title')
    title_text = title.get_text().strip() if title else "Title not found"
    
    # استخراج محتوای مقاله (با توجه به ساختار setare.com)
    content_selectors = [
        '.article-content',
        '.content',
        '.entry-content',
        'article',
        '.news-content',
        '.story__content'
    ]
    
    content = None
    for selector in content_selectors:
        content = soup.select_one(selector)
        if content:
            break
    
    # اگر محتوای خاصی پیدا نشد، از body استفاده کن
    if not content:
        content = soup.find('body')
    
    content_text = content.get_text().strip() if content else "Content not found"
    
    # پاکسازی متن
    content_text = ' '.join(content_text.split()[:500])  # محدودیت کاراکتر
    
    return {
        'title': title_text,
        'content': content_text,
        'success': True
    }

def main():
    # sidebar برای تنظیمات
    with st.sidebar:
        st.header("⚙️ Settings")
        max_retries = st.slider("Max Retries", 1, 5, 3)
        timeout = st.slider("Timeout (seconds)", 10, 30, 15)
        
        st.header("ℹ️ About")
        st.info("This app extracts article data from websites with anti-blocking features.")
    
    # بخش اصلی
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Enter URL")
        url = st.text_input(
            "Website URL",
            value="https://setare.com/fa/news/754575/",
            placeholder="https://example.com/article"
        )
        
        if st.button("🚀 Extract Article Data", type="primary"):
            if url:
                with st.spinner("🔄 Fetching data..."):
                    response = safe_request(url, max_retries)
                    
                    if response and response.status_code == 200:
                        data = extract_article_data(response.content)
                        
                        if data['success']:
                            st.markdown('<div class="success-box">✅ Data extracted successfully!</div>', unsafe_allow_html=True)
                            
                            st.subheader("📰 Article Title")
                            st.write(data['title'])
                            
                            st.subheader("📖 Article Content")
                            st.write(data['content'])
                            
                            # دکمه کپی کردن
                            if st.button("📋 Copy Content"):
                                st.code(data['content'], language='text')
                                st.success("Content ready to copy!")
                        else:
                            st.markdown('<div class="error-box">❌ Failed to extract article data</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="error-box">❌ Failed to fetch URL</div>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ Please enter a URL")
    
    with col2:
        st.subheader("💡 Tips")
        st.info("""
        - Use reputable news websites
        - Avoid sites with heavy anti-bot protection
        - Some sites may block automated requests
        - Try different URLs if one fails
        """)
        
        st.subheader("✅ Supported Sites")
        st.write("""
        - Setare.com
        - Most news websites
        - Blogs and articles
        """)

if __name__ == "__main__":
    main()
