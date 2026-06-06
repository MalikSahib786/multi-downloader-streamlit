import streamlit as st
import yt_dlp
import requests
from bs4 import BeautifulSoup
from functools import lru_cache

# Page Configurations
st.set_page_config(
    page_title="High-Speed Multi-Downloader",
    page_icon="📥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom Styling (Button aur UI ko khoobsurat banane ke liye)
st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF4B4B;
        margin-bottom: 5px;
    }
    .subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 30px;
    }
    .download-btn {
        display: inline-block;
        background-color: #FF4B4B;
        color: white !important;
        padding: 10px 20px;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        width: 100%;
        margin: 5px 0;
        transition: background-color 0.3s;
    }
    .download-btn:hover {
        background-color: #D32F2F;
    }
</style>
""", unsafe_allow_html=True)

MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'

def format_size(bytes_size):
    if not bytes_size: return "Unknown"
    mb = bytes_size / 1024 / 1024
    return f"{round(mb, 1)} MB"

@lru_cache(maxsize=50)
def cached_extract_logic(url: str):
    # Twitter Link Fix
    if "x.com" in url: 
        url = url.replace("x.com", "twitter.com")

    try:
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True, 
            'noplaylist': True,
            'force_ipv4': True, 
            'nocheckcertificate': True,
            'user_agent': MOBILE_UA,
            'socket_timeout': 10,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_options = {}
            audio_option = None
            formats = info.get('formats', [])
            duration = info.get('duration', 0)

            for f in formats:
                # 1. AUDIO FORMAT
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    size = f.get('filesize') or f.get('filesize_approx')
                    if not size and f.get('tbr') and duration: 
                        size = (f.get('tbr') * 1024 * duration) / 8
                    
                    audio_option = {
                        "type": "audio",
                        "label": f"🎵 Audio Only ({format_size(size)})",
                        "url": f['url']
                    }

                # 2. VIDEO WITH AUDIO FORMAT (MP4 Only)
                elif f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4':
                    height = f.get('height', 0)
                    if not height: 
                        continue
                    
                    size = f.get('filesize') or f.get('filesize_approx')
                    if not size and f.get('tbr') and duration: 
                        size = (f.get('tbr') * 1024 * duration) / 8

                    current_stored = video_options.get(height)
                    if not current_stored or (size and current_stored['raw_size'] and size > current_stored['raw_size']):
                        video_options[height] = {
                            "type": "video",
                            "label": f"🎥 {height}p HD ({format_size(size)})",
                            "res_val": height,
                            "raw_size": size,
                            "url": f['url']
                        }

            final_options = list(video_options.values())
            final_options.sort(key=lambda x: x['res_val'], reverse=True)
            
            if audio_option: 
                final_options.append(audio_option)

            # Auto fallback link
            if not final_options:
                direct_url = info.get('url')
                if direct_url: 
                    final_options.append({"type": "video", "label": "🎥 Best Quality (Auto)", "url": direct_url})

            return {
                "status": "success",
                "title": info.get('title') or "Video",
                "thumbnail": info.get('thumbnail'),
                "source": info.get('extractor_key'),
                "options": final_options
            }

    except Exception as e:
        # Fallback to Image Scraper
        return try_social_image_scrape(url)

def try_social_image_scrape(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            return {
                "status": "success",
                "title": soup.title.string or "Image",
                "thumbnail": og_img['content'],
                "source": "Image Scraper",
                "options": [{"type": "image", "label": "🖼️ Download Image (HD)", "url": og_img['content']}]
            }
    except: 
        pass
    return None

# --- UI LAYOUT ---
st.markdown('<div class="main-title">📥 Multi-Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Download videos and audio from TikTok, YouTube, Instagram, Facebook, and Twitter instantly.</div>', unsafe_allow_html=True)

url_input = st.text_input("Paste video or image link here:", placeholder="https://...")

if url_input:
    with st.spinner("Processing link... Please wait"):
        data = cached_extract_logic(url_input)
        
        if data and data.get("status") == "success":
            st.success("Analysis Complete!")
            
            # Columns setup for Thumbnail and download options
            col1, col2 = st.columns([1, 1.5])
            
            with col1:
                if data.get("thumbnail"):
                    st.image(data["thumbnail"], use_container_width=True)
                else:
                    st.info("No thumbnail available.")
                    
            with col2:
                st.subheader(data.get("title", "Media Details"))
                st.write(f"**Platform Source:** {data.get('source', 'Unknown')}")
                st.write("---")
                st.write("### Download Links:")
                
                options = data.get("options", [])
                if options:
                    for opt in options:
                        # UI-Friendly custom HTML button for direct browser download
                        st.markdown(
                            f'<a href="{opt["url"]}" target="_blank" class="download-btn">{opt["label"]}</a>', 
                            unsafe_allow_html=True
                        )
                else:
                    st.warning("No downloadable formats detected.")
        else:
            st.error("Could not retrieve media options. Please ensure the link is public and correct.")
