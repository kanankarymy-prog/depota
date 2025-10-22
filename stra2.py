import streamlit as st
import requests
from bs4 import BeautifulSoup
from itertools import cycle
import traceback

# ==========================
# Proxy list (rotation)
# ==========================
proxies_list = [
    {"ip": "46.249.100.124", "port": "80", "type": "http"},
    {"ip": "5.161.133.32", "port": "80", "type": "http"},
    {"ip": "78.38.67.210", "port": "3636", "type": "socks4"},
]

proxy_cycle = cycle(proxies_list)


# ==========================
# Function to fetch URL
# ==========================
def fetch_url(url):
    """
    Fetch URL content by rotating through proxies until success.
    Handles decoding issues and proxy timeouts gracefully.
    """
    for proxy_data in proxy_cycle:
        proxy = {
            "http": f"{proxy_data['type']}://{proxy_data['ip']}:{proxy_data['port']}",
            "https": f"{proxy_data['type']}://{proxy_data['ip']}:{proxy_data['port']}",
        }

        try:
            st.write(f"🌐 Testing proxy: {proxy_data['ip']}:{proxy_data['port']} ({proxy_data['type']})")

            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                                       "Chrome/120.0.0.0 Safari/537.36"},
                proxies=proxy,
                timeout=12,
            )

            # Only continue if success
            if response.status_code == 200:
                try:
                    # try normal decode
                    html = response.content.decode("utf-8", errors="ignore")
                except Exception:
                    # fallback to text
                    html = str(response.text)

                if "<html" in html.lower():
                    return html
                else:
                    st.warning("⚠️ Response isn't valid HTML — skipping this proxy.")
            else:
                st.warning(f"⚠️ Status {response.status_code} from {proxy_data['ip']}")
        except Exception as e:
            st.warning(f"❌ Proxy {proxy_data['ip']} failed: {str(e)}")

    return None


# ==========================
# Streamlit UI
# ==========================
st.set_page_config(page_title="Multi-Proxy Fetcher", page_icon="🌍", layout="centered")

st.title("🌍 Multi-Proxy URL Fetcher")
st.markdown("**Automatically test multiple proxies to fetch any webpage (even Iranian sites).**")

url = st.text_input("🔗 Enter website URL:", "https://namnak.com/fall-rozane-30-mehr-1404.p111860")

if st.button("🚀 Fetch HTML"):
    if not url.startswith("http"):
        url = "https://" + url

    with st.spinner("⏳ Fetching page using proxies..."):
        try:
            html = fetch_url(url)
        except Exception as e:
            st.error("Unexpected error:\n\n" + traceback.format_exc())
            html = None

    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            st.success("✅ Page fetched successfully!")
            st.text_area("📄 HTML Preview (first 5000 chars)", soup.prettify()[:5000], height=400)
        except Exception as e:
            st.error(f"Error parsing HTML: {e}")
    else:
        st.error("❌ Could not fetch the page using any proxy.")
