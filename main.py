import streamlit as st
import yt_dlp
import requests
from bs4 import BeautifulSoup
from functools import lru_cache
import io

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
    .open-link-btn {
        display: inline-block;
        background-color: #FF4B4B;
        color: white !important;
        padding: 12px 20px;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        width: 100%;
        margin: 5px 0;
        font-size: 1.1rem;
        transition: background-color 0.3s;
    }
    .open-link-btn:hover {
        background-color: #D32F2F;
    }
</style>
""", unsafe_allow_html=True)

MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'

def format_size(bytes_size):
    if not bytes_size: return "Unknown"
    mb = bytes_size / 1024 / 1024
    return f"{round(mb, 1)} MB"

# --- SERVER-SIDE STREAM DOWNLOADER ---
def fetch_media_bytes(url):
    headers = {
        'User-Agent': MOBILE_UA,
        'Referer': 'https://www.tiktok.com/' if 'tiktok' in url or 'byteoversea' in url else ''
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=25)
        response.raise_for_status()
        buffer = io.BytesIO()
        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
            if chunk:
                buffer.write(chunk)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Error streaming download: {e}")
        return None

# --- SAFE CALLBACK GENERATOR ---
def make_download_callback(url):
    def callback():
        bytes_data = fetch_media_bytes(url)
        if not bytes_data:
            return "Error: Direct server-side download failed.".encode('utf-8')
        return bytes_data
    return callback

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
st.markdown('<div class="subtitle">Direct, ad-free social media downloads in one click.</div>', unsafe_allow_html=True)

url_input = st.text_input("Paste your link here:", placeholder="https://...")

if url_input:
    with st.spinner("Analyzing media link..."):
        data = cached_extract_logic(url_input)
        
        if data and data.get("status") == "success":
            st.success("Analysis Complete!")
            
            options = data.get("options", [])
            slides = data.get("slides", [])
            source_platform = data.get('source', '').lower()
            is_youtube = "youtube" in source_platform or "youtube" in url_input.lower() or "youtu.be" in url_input.lower()

            # Separate video and audio options
            video_only_options = [opt for opt in options if opt["type"] == "video"]
            audio_only_options = [opt for opt in options if opt["type"] == "audio"]
            best_option = video_only_options[0] if video_only_options else None

            # Left and Right UI Column Setup
            col1, col2 = st.columns([1.1, 1.2])
            
            # --- LEFT COLUMN (PREVIEW PLAYER WITH POSTER IMAGE FIRST) ---
            with col1:
                st.write("### 🎬 Media Preview")
                if video_only_options:
                    video_url = video_only_options[0]["url"]
                    poster_url = data.get("thumbnail") or ""
                    
                    # HTML5 Video Tag with Poster (Thumbnail) shows first
                    st.markdown(
                        f'''
                        <video controls poster="{poster_url}" style="width:100%; border-radius:10px; background-color:black; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                            <source src="{video_url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        ''', 
                        unsafe_allow_html=True
                    )
                elif audio_only_options:
                    if data.get("thumbnail"):
                        st.image(data["thumbnail"], width='stretch')
                    st.audio(audio_only_options[0]["url"])
                elif slides:
                    st.image(slides[0]["url"], width='stretch')
                elif data.get("thumbnail"):
                    st.image(data["thumbnail"], width='stretch')
                else:
                    st.info("No interactive preview available.")
                    
            # --- RIGHT COLUMN (METADATA AND DOWNLOAD BUTTONS) ---
            with col2:
                st.subheader(data.get("title", "Post Media"))
                st.write(f"**Platform:** {data.get('source', 'Social Media')}")
                st.write("---")

                # --- 1. HANDLING SLIDESHOWS (TikTok / Instagram) ---
                if slides:
                    st.write(f"### 📸 Photos Found ({len(slides)})")
                    for i, slide in enumerate(slides):
                        with st.expander(f"🖼️ View Photo {i+1}"):
                            st.image(slide['url'], width='stretch')
                            st.download_button(
                                label=f"📥 Save Photo {i+1} to Device",
                                data=make_download_callback(slide["url"]),
                                file_name=f"photo_{i+1}.jpg",
                                mime="image/jpeg",
                                key=f"dl_slide_{i}"
                            )

                # --- 2. HANDLING VIDEOS & AUDIO ---
                if options:
                    st.write("### ⬇️ Download Media:")
                    
                    if best_option:
                        st.write("⭐ **Recommended Best Video:**")
                        
                        if is_youtube:
                            # YouTube uses direct browser streaming anchor to bypass geolocked cloud IP blocks
                            st.markdown(
                                f'<a href="{best_option["url"]}" download="video_{best_option["res_val"]}p.mp4" class="open-link-btn" style="background-color: #2E7D32;">🚀 Save Best Quality: {best_option["label"].replace("🎥", "")} (Auto)</a>', 
                                unsafe_allow_html=True
                            )
                        else:
                            # Direct server stream download
                            st.download_button(
                                label=f"🚀 Direct Download: {best_option['label']}",
                                data=make_download_callback(best_option["url"]),
                                file_name=f"video_{best_option['res_val']}p.mp4",
                                mime="video/mp4",
                                type="primary",
                                key="dl_best_native"
                            )
                        st.write("---")

                    # Other resolutions
                    for i, opt in enumerate(options):
                        if best_option and opt["url"] == best_option["url"]:
                            continue
                        ext = "mp4" if opt["type"] == "video" else "mp3"
                        mime_type = "video/mp4" if opt["type"] == "video" else "audio/mpeg"
                        
                        if is_youtube:
                            st.markdown(
                                f'<a href="{opt["url"]}" download="media_{opt.get("res_val", "audio")}.{ext}" class="open-link-btn">📥 Download {opt["label"]}</a>', 
                                unsafe_allow_html=True
                            )
                        else:
                            st.download_button(
                                label=f"📥 Download {opt['label']}",
                                data=make_download_callback(opt["url"]),
                                file_name=f"media_{opt.get('res_val', 'audio')}.{ext}",
                                mime=mime_type,
                                key=f"dl_native_{i}"
                            )

        else:
            st.error("Error: Could not retrieve media formats. Please make sure the link is public.")
