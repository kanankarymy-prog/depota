import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# -----------------------------
# تنظیمات کلی اپ
# -----------------------------
st.set_page_config(page_title="HTML Tree Viewer", layout="wide")

st.title("🌐 HTML Tag Tree Viewer")
url = st.text_input("Enter URL:")

# -----------------------------
# تنظیمات پراکسی (در صورت نیاز)
# -----------------------------
USE_PROXY = True  # اگر نمی‌خوای پراکسی فعال باشه بذار False
PROXY = {
    "http": "http://46.209.15.187:8080",
    "https": "http://46.209.15.187:8080",
}

# -----------------------------
# تابع گرفتن HTML با هندل خطا و پراکسی
# -----------------------------
def fetch_html(url):
    try:
        if USE_PROXY:
            response = requests.get(url, timeout=10, proxies=PROXY)
        else:
            response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.ProxyError:
        st.warning("⚠️ Proxy failed — retrying without proxy...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            st.error(f"❌ Failed to fetch {url}: {e}")
            return None
    except Exception as e:
        st.error(f"❌ Error fetching {url}: {e}")
        return None

# -----------------------------
# تابع ساخت درخت HTML
# -----------------------------
def build_tree(element, level=0):
    indent = "  " * level
    result = f"{indent}<{element.name}>\n"
    for child in element.children:
        if child.name:
            result += build_tree(child, level + 1)
    return result

# -----------------------------
# رابط کاربری و نمایش
# -----------------------------
if url:
    html_content = fetch_html(url)

    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        body = soup.body

        if body:
            tree_text = build_tree(body)

            st.subheader("HTML Tag Tree")
            st.code(tree_text, language="html")

            st.subheader("Table of Tags")
            tags = [tag.name for tag in soup.find_all()]
            df = pd.DataFrame({"Tag": tags})
            st.dataframe(df)
        else:
            st.warning("No <body> tag found in this page.")
