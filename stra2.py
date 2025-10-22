# app.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Tuple
import re
import time

# optional imports that may not exist in all envs
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except Exception:
    PYPERCLIP_AVAILABLE = False

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except Exception:
    CLOUDSCRAPER_AVAILABLE = False

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, ConnectTimeout, ReadTimeout, ProxyError, SSLError

# -------------------------
# تنظیمات و UI اولیه (بدون تغییر عمده در ظاهر)
# -------------------------
st.set_page_config(layout="centered")
st.title("Heading Analyzer Tool")
st.markdown(
    "Enter multiple URLs (one per line) or upload an Excel file with URLs in column A to analyze their headings. "
    "This tool fetches webpages, counts headings, provides a tree view with copy functionality, HTTP status, and meta description."
)

# Text area for manual URLs
urls_input = st.text_area("URLs (one per line):", height=200)

# File uploader for Excel
uploaded_file = st.file_uploader("Upload Excel file (.xlsx):", type=["xlsx"])

# Keyword search option
enable_keyword_search = st.checkbox("Enable keyword search")

keywords = []
if enable_keyword_search:
    st.info("Enter up to 5 keywords to search for in the pages (one per line)")
    keyword_input = st.text_area("Keywords:", height=100, placeholder="Enter one keyword per line\nExample:\nseo\ndigital marketing\nweb analytics")
    if keyword_input:
        keywords = [k.strip() for k in keyword_input.split("\n") if k.strip()][:5]  # Limit to 5 keywords

# -------------------------
# لیست پراکسی (تو خواستی قابلیت دادن لیست باشه)
# من از لیست مثال تو استفاده کردم؛ اگر خواستی می‌تونی این لیست را در UI هم قرار بدیم تا داینامیک باشه.
# -------------------------
# Provided proxies (the ones you gave). Each entry: (type, host, port)
PROXY_ENTRIES = [
    ("HTTP", "46.249.100.124", 80),
    ("HTTP", "5.161.133.32", 80),
    ("SOCKS4", "78.38.67.210", 3636),
]

def build_proxies_list(entries):
    """
    Convert tuples into requests-compatible proxy dicts (one dict per proxy).
    Handles HTTP and SOCKS4 (requests needs requests[socks] for socks URLs).
    """
    proxies_list = []
    for ptype, host, port in entries:
        if ptype.upper() in ("HTTP", "HTTP/HTTPS", "HTTP(S)"):
            proxy_url = f"http://{host}:{port}"
            proxies_list.append({"http": proxy_url, "https": proxy_url, "label": f"http://{host}:{port}"})
        elif ptype.upper() in ("SOCKS4", "SOCKS5"):
            # requests requires pysocks/socks support; format: socks4://host:port
            proxy_url = f"socks4://{host}:{port}" if ptype.upper() == "SOCKS4" else f"socks5://{host}:{port}"
            proxies_list.append({"http": proxy_url, "https": proxy_url, "label": proxy_url})
        else:
            # unknown type treat as HTTP
            proxy_url = f"http://{host}:{port}"
            proxies_list.append({"http": proxy_url, "https": proxy_url, "label": proxy_url})
    return proxies_list

PROXIES_LIST = build_proxies_list(PROXY_ENTRIES)

# -------------------------
# توابع کمکی برای درخواست‌ها با retry و فیلد user-agent
# -------------------------
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def make_requests_session(retries=2, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504)):
    s = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=False  # to be permissive for all methods (urllib3 >=1.26 uses allowed_methods)
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(DEFAULT_HEADERS)
    return s

def fetch_with_fallback(url: str, proxies_list: List[dict] = None, timeout_connect=10, timeout_read=20, allow_cloudscraper=True):
    """
    Attempts to fetch in this order:
      1. direct request
      2. sequentially try each proxy in proxies_list (if provided)
      3. cloudscraper (direct), then cloudscraper+proxy attempts
    Returns: (response_object, method_label)
    On failure raises the last exception (so caller can handle and show message).
    """
    session = make_requests_session()
    timeout = (timeout_connect, timeout_read)
    last_exc = None

    # 1) Direct attempt
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp, "direct"
    except (ConnectTimeout, ReadTimeout, ProxyError) as e:
        last_exc = e
    except RequestException as e:
        # If we got a response with status >=400 we may still want to return it (like 403)
        if hasattr(e, "response") and e.response is not None:
            return e.response, "direct_status_error"
        last_exc = e

    # 2) Try proxies one by one
    if proxies_list:
        for proxy in proxies_list:
            try:
                resp = session.get(url, proxies={"http": proxy["http"], "https": proxy["https"]}, timeout=timeout)
                resp.raise_for_status()
                return resp, f"proxy:{proxy['label']}"
            except (ConnectTimeout, ReadTimeout, ProxyError) as e:
                last_exc = e
                # small pause to avoid hammering unstable proxies
                time.sleep(0.5)
                continue
            except RequestException as e:
                # If response exists with status >=400 maybe return it
                if hasattr(e, "response") and e.response is not None:
                    return e.response, f"proxy_status_error:{proxy['label']}"
                last_exc = e
                time.sleep(0.5)
                continue

    # 3) cloudscraper fallback (if available)
    if CLOUDSCRAPER_AVAILABLE and allow_cloudscraper:
        try:
            scraper = cloudscraper.create_scraper(browser={"custom": DEFAULT_HEADERS})
            # try direct with cloudscraper
            try:
                resp = scraper.get(url, timeout=timeout)
                if getattr(resp, "status_code", 200) < 400:
                    return resp, "cloudscraper_direct"
            except Exception as e:
                last_exc = e

            # try cloudscraper with proxies
            if proxies_list:
                for proxy in proxies_list:
                    try:
                        resp = scraper.get(url, proxies={"http": proxy["http"], "https": proxy["https"]}, timeout=timeout)
                        if getattr(resp, "status_code", 200) < 400:
                            return resp, f"cloudscraper_proxy:{proxy['label']}"
                    except Exception as e:
                        last_exc = e
                        time.sleep(0.5)
                        continue
        except Exception as e:
            last_exc = e

    # If everything failed, raise last exception
    raise last_exc if last_exc is not None else RequestException("Unknown fetch error")

# -------------------------
# تابع اصلی (همان نام و خروجی که قبلاً داشتی) — با منطق fetch بهبود یافته
# خروجی: Tuple[int, dict, List[Tuple[str, str]], str, int, str, dict]
# یعنی: total, counts, structure, page_title, status_code, meta_desc, keyword_counts
# -------------------------
def get_headings(url: str, keywords: List[str] = None) -> Tuple[int, dict, List[Tuple[str, str]], str, int, str, dict]:
    try:
        # تلاش برای گرفتن صفحه با fallback پراکسی
        try:
            resp, method = fetch_with_fallback(url, proxies_list=PROXIES_LIST, timeout_connect=10, timeout_read=20, allow_cloudscraper=True)
        except Exception as e:
            # اگر همه جا شکست خورد، نمایش خطا در UI و برگرداندن مقدار خطا (همان رفتار قبلی)
            st.error(f"Error fetching {url}: {str(e)}")
            return 0, {}, [], "Error", getattr(getattr(e, "response", None), "status_code", 0), "Error", {}

        # resp ممکن است از cloudscraper یا requests باشد — هر دو .text را دارند
        status_code = getattr(resp, "status_code", 0)
        html = getattr(resp, "text", "")

        soup = BeautifulSoup(html, 'html.parser')
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        page_title = soup.find('title').text.strip() if soup.find('title') else "No Title"

        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag and 'content' in meta_desc_tag.attrs else "No Meta Description"

        counts = {'H1': 0, 'H2': 0, 'H3': 0, 'H4': 0, 'H5': 0, 'H6': 0}
        total = 0
        structure = []

        for h in headings:
            tag = h.name.upper()
            if tag in counts:
                counts[tag] += 1
                total += 1
                structure.append((tag, h.text.strip()))

        # Count keywords if provided
        keyword_counts = {}
        if keywords:
            text_content = soup.get_text().lower()
            for keyword in keywords:
                if keyword.strip():
                    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                    count = len(re.findall(pattern, text_content))
                    keyword_counts[keyword] = count

        # Optionally show a small note about fetch method (keeps UI کلی یکسان)
        if method and method != "direct":
            st.info(f"Fetched {url} via: {method}")

        return total, counts, structure, page_title, status_code, meta_desc, keyword_counts
    except Exception as e:
        st.error(f"Error fetching {url}: {str(e)}")
        return 0, {}, [], "Error", getattr(getattr(e, "response", None), "status_code", 0), "Error", {}

# -------------------------
# تابع ساخت درخت (همان که داشتی)
# -------------------------
def build_tree(structure: List[Tuple[str, str]]) -> str:
    """
    Build a indented tree representation of headings.
    Uses indentation to show nesting based on levels.
    """
    if not structure:
        return "No headings found."

    tree = ""
    min_level = min(int(tag[1]) for tag, _ in structure) if structure else 1

    for tag, text in structure:
        level = int(tag[1]) - min_level
        indent = "  " * level
        tree += f"{indent}- {tag}: {text}\n"

    return tree

# -------------------------
# حفظ state و رفتار اپ (بدون تغییر ظاهری زیاد)
# -------------------------
if 'results' not in st.session_state:
    st.session_state['results'] = {}

if st.button("Analyze Headings"):
    urls = []

    # Process manual input
    if urls_input:
        urls = [u.strip() for u in urls_input.split("\n") if u.strip()]

    # Process uploaded Excel
    if uploaded_file:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            if 'A' in df_uploaded.columns:  # Assuming column A is labeled as 'A' or first column
                urls.extend(df_uploaded['A'].dropna().astype(str).tolist())
            else:
                st.warning("No column 'A' found in the Excel file. Using the first column instead.")
                urls.extend(df_uploaded.iloc[:, 0].dropna().astype(str).tolist())
            urls = list(dict.fromkeys(urls))  # Remove duplicates while preserving order
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")

    if not urls:
        st.warning("Please enter at least one URL or upload a valid Excel file.")
    else:
        data = []
        structures = {}

        with st.spinner("Analyzing URLs..."):
            for url in urls:
                total, counts, struct, page_title, status_code, meta_desc, keyword_counts = get_headings(url, keywords if enable_keyword_search else None)
                row = {
                    "URL": url,
                    "Title": page_title,
                    "HTTP Status": status_code,
                    "Meta Description": meta_desc,
                    "Total Headings": total,
                    "H1": counts.get("H1", 0),
                    "H2": counts.get("H2", 0),
                    "H3": counts.get("H3", 0),
                    "H4": counts.get("H4", 0),
                    "H5": counts.get("H5", 0),
                    "H6": counts.get("H6", 0)
                }

                # Add keyword counts to row if enabled
                if enable_keyword_search and keywords:
                    for keyword in keywords:
                        row[keyword] = keyword_counts.get(keyword, 0)

                data.append(row)
                structures[url] = struct

        st.session_state['results'] = {'data': data, 'structures': structures}

# نمایش نتایج (همان UI قبلی)
if 'results' in st.session_state and st.session_state['results'].get('data'):
    df = pd.DataFrame(st.session_state['results']['data'])
    st.subheader("Headings Summary Table")
    st.dataframe(df, use_container_width=True, height=400)

    st.subheader("Tree Views")
    structures = st.session_state['results']['structures']
    for url in structures.keys():
        with st.expander(f"View Tree for {url}"):
            structure = structures.get(url, [])
            tree_text = build_tree(structure)
            st.code(tree_text, language="markdown")
            # Keep the same UI button "Copy Full Tree" but provide fallback for Streamlit Cloud
            if st.button("Copy Full Tree", key=f"copy_full_{url}"):
                if PYPERCLIP_AVAILABLE:
                    try:
                        pyperclip.copy(tree_text)
                        st.success("Copied full tree to clipboard!")
                    except Exception:
                        # fallback: show text area for manual copy
                        st.warning("Automatic clipboard not available in this environment. Copy manually below.")
                        st.text_area("Copy manually:", tree_text, height=200)
                else:
                    st.warning("Automatic clipboard not available in this environment. Copy manually below.")
                    st.text_area("Copy manually:", tree_text, height=200)
