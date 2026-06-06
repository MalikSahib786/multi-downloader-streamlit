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

# Custom Styling
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
    .media-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 15px;
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
    .yt-btn {
        display: inline-block;
        background-color: #FF0000;
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
    .yt-btn:hover {
        background-color: #B71C1C;
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
# Streamlit crashes if callable returns None, so we always return a text fallback
def make_download_callback(url):
    def callback():
        bytes_data = fetch_media_bytes(url)
        if not bytes_data:
            return "Error: Direct server-side download failed. Please use the fallback browser link below.".encode('utf-8')
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

# --- UI LAYOUT ---
st.markdown('<div class="main-title">📥 Multi-Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Direct downloads for TikTok & IG. Secure browser pathways for YouTube.</div>', unsafe_allow_html=True)

url_input = st.text_input("Paste your link here:", placeholder="https://...")

if url_input:
    with st.spinner("Analyzing media link..."):
        data = cached_extract_logic(url_input)
        
        if data and data.get("status") == "success":
            st.success("Analysis Complete!")
            
            col1, col2 = st.columns([1, 1.3])
            
            with col1:
                if data.get("thumbnail"):
                    st.image(data["thumbnail"], width='stretch')
                else:
                    st.info("No cover thumbnail found.")
                    
            with col2:
                st.subheader(data.get("title", "Post Media"))
                source_platform = data.get('source', '').lower()
                st.write(f"**Platform:** {data.get('source', 'Social Media')}")
                st.write("---")

                options = data.get("options", [])
                slides = data.get("slides", [])

                # Determine if it's YouTube / Google Video
                is_youtube = "youtube" in source_platform or "youtube" in url_input.lower() or "youtu.be" in url_input.lower()

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
                    video_only_options = [opt for opt in options if opt["type"] == "video"]
                    best_option = video_only_options[0] if video_only_options else None

                    # A. YOUTUBE SPECIFIC DIRECT LINK (To bypass 403 blocks)
                    if is_youtube:
                        st.warning("⚠️ **YouTube Link Detected:** YouTube blocks proxy servers. Please use the direct links below to save your file securely.")
                        if best_option:
                            st.write("⭐ **Recommended Best Video:**")
                            st.markdown(
                                f'<a href="{best_option["url"]}" target="_blank" class="yt-btn">🔗 Open & Save Video ({best_option["label"].split("(")[-1]}</a>', 
                                unsafe_allow_html=True
                            )
                            st.info("💡 **Tip:** Video link open hone par right-click karke 'Save video as...' select karein.")
                            st.write("---")

                        st.write("### 🎛️ Other Resolutions:")
                        for i, opt in enumerate(options):
                            if best_option and opt["url"] == best_option["url"]:
                                continue
                            label_clean = opt["label"]
                            st.markdown(
                                f'<a href="{opt["url"]}" target="_blank" class="open-link-btn">🔗 Open {label_clean}</a>', 
                                unsafe_allow_html=True
                            )

                    # B. TIKTOK / INSTAGRAM DIRECT SERVER SAVE
                    else:
                        st.write("### ⬇️ Save to Device (Direct):")
                        if best_option:
                            st.write("⭐ **Recommended Best Video:**")
                            # Uses lambda callback to evaluate only on click
                            st.download_button(
                                label=f"🚀 Direct Download: {best_option['label']}",
                                data=make_download_callback(best_option["url"]),
                                file_name=f"video_{best_option['res_val']}p.mp4",
                                mime="video/mp4",
                                type="primary",
                                key="dl_best_native"
                            )
                            st.write("---")

                        for i, opt in enumerate(options):
                            if best_option and opt["url"] == best_option["url"]:
                                continue
                            ext = "mp4" if opt["type"] == "video" else "mp3"
                            mime_type = "video/mp4" if opt["type"] == "video" else "audio/mpeg"
                            
                            st.download_button(
                                label=f"📥 Download {opt['label']}",
                                data=make_download_callback(opt["url"]),
                                file_name=f"media_{opt.get('res_val', 'audio')}.{ext}",
                                mime=mime_type,
                                key=f"dl_native_{i}"
                            )

            # --- 3. PREVIEW PLAYER ---
            if not is_youtube:
                st.write("---")
                st.write("### 🎬 Instant Media Preview")
                preview_video = [opt for opt in options if opt["type"] == "video"]
                preview_audio = [opt for opt in options if opt["type"] == "audio"]
                
                if preview_video:
                    st.video(preview_video[0]["url"])
                elif preview_audio:
                    st.audio(preview_audio[0]["url"])

        else:
            st.error("Error: Could not retrieve media. Please make sure the link is correct and public.")
