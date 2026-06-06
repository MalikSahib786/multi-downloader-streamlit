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

# Custom Premium Styling
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
    .best-download-btn {
        display: inline-block;
        background-color: #2E7D32;
        color: white !important;
        padding: 14px 20px;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        width: 100%;
        margin: 8px 0;
        font-size: 1.1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: background-color 0.3s;
    }
    .best-download-btn:hover {
        background-color: #1B5E20;
    }
    .media-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 15px;
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
            'socket_timeout': 12,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_options = {}
            audio_option = None
            slides = []
            
            # --- DETECT MULTIPLE SLIDES/PHOTOS (TikTok Photo Slideshow / IG Carousel) ---
            # Checks if yt-dlp parsed multiple entries/images in playlist/slideshow mode
            if info.get('_type') == 'playlist' or 'entries' in info:
                for entry in info.get('entries', []):
                    if entry:
                        slide_url = entry.get('url')
                        if not slide_url and entry.get('formats'):
                            slide_url = entry['formats'][-1].get('url')
                        if slide_url:
                            slides.append({
                                "url": slide_url,
                                "title": entry.get('title') or f"Slide {len(slides)+1}"
                            })

            formats = info.get('formats', [])
            duration = info.get('duration', 0)

            for f in formats:
                # 1. AUDIO FORMATS
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    size = f.get('filesize') or f.get('filesize_approx')
                    if not size and f.get('tbr') and duration: 
                        size = (f.get('tbr') * 1024 * duration) / 8
                    
                    audio_option = {
                        "type": "audio",
                        "label": f"🎵 Audio Only ({format_size(size)})",
                        "url": f['url']
                    }

                # 2. VIDEO WITH AUDIO (MP4 Preference)
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

            # Fallback to direct url if no structured video options detected
            if not video_options and not slides:
                direct_url = info.get('url')
                if direct_url:
                    video_options[9999] = {
                        "type": "video",
                        "label": "🎥 Best Quality (Auto)",
                        "res_val": 9999,
                        "raw_size": 0,
                        "url": direct_url
                    }

            final_options = list(video_options.values())
            final_options.sort(key=lambda x: x['res_val'], reverse=True)
            
            if audio_option: 
                final_options.append(audio_option)

            return {
                "status": "success",
                "title": info.get('title') or "Social Media Media",
                "thumbnail": info.get('thumbnail'),
                "source": info.get('extractor_key'),
                "options": final_options,
                "slides": slides
            }

    except Exception as e:
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
                "title": soup.title.string or "Scraped Image",
                "thumbnail": og_img['content'],
                "source": "Image Parser",
                "options": [],
                "slides": [{"url": og_img['content'], "title": "Scraped Photo"}]
            }
    except: 
        pass
    return None

# --- STREAMLIT UI ---
st.markdown('<div class="main-title">📥 Multi-Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Download videos, slideshows, and audio from all major social platforms.</div>', unsafe_allow_html=True)

url_input = st.text_input("Paste your social link here:", placeholder="https://...")

if url_input:
    with st.spinner("Analyzing media link..."):
        data = cached_extract_logic(url_input)
        
        if data and data.get("status") == "success":
            st.success("Analysis Complete!")
            
            # Divide UI layout into columns
            col1, col2 = st.columns([1, 1.3])
            
            with col1:
                if data.get("thumbnail"):
                    st.image(data["thumbnail"], width='stretch')
                else:
                    st.info("No cover thumbnail found.")
                    
            with col2:
                st.subheader(data.get("title", "Post Media"))
                st.write(f"**Platform detected:** {data.get('source', 'Unknown Source')}")
                st.write("---")

                options = data.get("options", [])
                slides = data.get("slides", [])

                # --- 1. HANDLE SLIDESHOW / PHOTO SLIDES (TikTok & IG Carousel) ---
                if slides:
                    st.write(f"### 📸 Photos Found ({len(slides)})")
                    st.write("This post contains multiple images. You can preview and download them below:")
                    
                    for i, slide in enumerate(slides):
                        with st.expander(f"🖼️ View Photo {i+1}"):
                            st.image(slide['url'], width='stretch')
                            st.markdown(
                                f'<a href="{slide["url"]}" target="_blank" class="download-btn">📥 Download Photo {i+1}</a>', 
                                unsafe_allow_html=True
                            )

                # --- 2. HANDLE VIDEO/AUDIO OPTIONS ---
                if options:
                    # Find and isolate the ultimate best-quality video format
                    video_only_options = [opt for opt in options if opt["type"] == "video"]
                    best_option = video_only_options[0] if video_only_options else None
                    
                    # Highlight "Auto Best" Quality Option
                    if best_option:
                        st.write("### ⭐ Recommended Quality:")
                        st.markdown(
                            f'<a href="{best_option["url"]}" target="_blank" class="best-download-btn">🚀 Best Quality: {best_option["label"].replace("🎥", "")} (Auto)</a>', 
                            unsafe_allow_html=True
                        )
                        st.write("---")

                    # List other available quality formats
                    st.write("### 🎛️ Other Formats:")
                    for opt in options:
                        st.markdown(
                            f'<a href="{opt["url"]}" target="_blank" class="download-btn">{opt["label"]}</a>', 
                            unsafe_allow_html=True
                        )

            # --- 3. BUILT-IN ON-PAGE PREVIEW PLAYER ---
            st.write("---")
            st.write("### 🎬 Instant Media Preview")
            
            preview_video = [opt for opt in options if opt["type"] == "video"]
            preview_audio = [opt for opt in options if opt["type"] == "audio"]
            
            if preview_video:
                st.video(preview_video[0]["url"])
            elif preview_audio:
                st.audio(preview_audio[0]["url"])
            elif slides:
                # If it's a slideshow, show a simple preview of the first image
                st.image(slides[0]["url"], caption="First Slide Preview", width='stretch')
            else:
                st.info("Direct preview player not available for this format. Please use the download links above.")
        else:
            st.error("Error: Could not retrieve media formats. Please make sure the link is public.")
