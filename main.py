import streamlit as st
import requests
from io import BytesIO
from pydub import AudioSegment

BASE_URL = "https://api.alquran.cloud/v1"

st.set_page_config(page_title="Holy Qur'an", page_icon="📖", layout="centered")


# ---------------------- Data helpers ----------------------

@st.cache_data(ttl=60 * 60 * 24)
def get_surah_list():
    r = requests.get(f"{BASE_URL}/surah", timeout=15)
    r.raise_for_status()
    return r.json()["data"]


@st.cache_data(ttl=60 * 60 * 24)
def get_text(surah, ayah, edition):
    r = requests.get(f"{BASE_URL}/ayah/{surah}:{ayah}/{edition}", timeout=15)
    r.raise_for_status()
    return r.json()["data"]["text"]


@st.cache_data(ttl=60 * 60 * 24)
def get_audio_url(surah, ayah, edition):
    r = requests.get(f"{BASE_URL}/ayah/{surah}:{ayah}/{edition}", timeout=15)
    r.raise_for_status()
    return r.json()["data"]["audio"]


@st.cache_data(ttl=60 * 60 * 24)
def find_audio_edition(language):
    """Find an available audio edition (recitation) for a translation language."""
    r = requests.get(f"{BASE_URL}/edition?format=audio&language={language}", timeout=15)
    r.raise_for_status()
    data = r.json()["data"]
    return data[0]["identifier"] if data else None


@st.cache_data(ttl=60 * 60 * 24)
def download_audio_bytes(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def merge_audio(bytes1, bytes2):
    seg1 = AudioSegment.from_file(BytesIO(bytes1))
    seg2 = AudioSegment.from_file(BytesIO(bytes2))
    combined = seg1 + AudioSegment.silent(duration=400) + seg2
    out = BytesIO()
    combined.export(out, format="mp3")
    return out.getvalue()


# ---------------------- UI ----------------------

st.title("📖 Holy Qur'an — Read & Listen")

try:
    surahs = get_surah_list()
except Exception:
    st.error("Quran data load nahi ho saka. Internet connection check karein.")
    st.stop()

surah_labels = [f"{s['number']}. {s['englishName']} ({s['name']})" for s in surahs]
idx = st.selectbox("Surah chuniye", range(len(surahs)), format_func=lambda i: surah_labels[i])
surah_number = surahs[idx]["number"]
ayah_count = surahs[idx]["numberOfAyahs"]
ayah_number = st.number_input("Ayat number", min_value=1, max_value=ayah_count, value=1, step=1)

st.divider()
mode = st.radio("Aap kya karna chahte hain?", ["📖 Read (Parhna)", "🔊 Listen (Sunna)"], horizontal=True)

try:
    arabic_text = get_text(surah_number, ayah_number, "quran-uthmani")
except Exception:
    st.error("Ayat load nahi ho saki.")
    st.stop()

if mode.startswith("📖"):
    choice = st.radio("Translation bhi dikhayen?", ["Sirf Arabic", "Arabic + Urdu", "Arabic + English"])
    st.markdown(
        f"<div style='font-size:30px; text-align:right; direction:rtl; line-height:1.8'>{arabic_text}</div>",
        unsafe_allow_html=True,
    )
    if "Urdu" in choice:
        st.markdown(f"**Urdu Translation:** {get_text(surah_number, ayah_number, 'ur.jalandhry')}")
    if "English" in choice:
        st.markdown(f"**English Translation:** {get_text(surah_number, ayah_number, 'en.sahih')}")

else:
    choice = st.radio(
        "Kis tarah sunna chahte hain?",
        ["Arabic + Urdu Translation", "Arabic + English Translation", "Sirf Arabic"],
    )
    st.markdown(
        f"<div style='font-size:26px; text-align:right; direction:rtl'>{arabic_text}</div>",
        unsafe_allow_html=True,
    )

    reciter = "ar.alafasy"  # Arabic recitation (Mishary Alafasy)
    try:
        arabic_audio_url = get_audio_url(surah_number, ayah_number, reciter)
    except Exception:
        st.error("Arabic audio load nahi hua.")
        st.stop()

    if choice == "Sirf Arabic":
        st.audio(arabic_audio_url)
    else:
        lang_code = "ur" if "Urdu" in choice else "en"
        with st.spinner("Audio taiyar ho raha hai..."):
            try:
                trans_edition = find_audio_edition(lang_code)
                if trans_edition:
                    trans_audio_url = get_audio_url(surah_number, ayah_number, trans_edition)
                    arabic_bytes = download_audio_bytes(arabic_audio_url)
                    trans_bytes = download_audio_bytes(trans_audio_url)
                    merged = merge_audio(arabic_bytes, trans_bytes)
                    st.audio(merged, format="audio/mp3")
                else:
                    st.warning("Is language mein translation audio available nahi — sirf Arabic chala rahe hain.")
                    st.audio(arabic_audio_url)
            except Exception:
                st.warning("Translation audio jorne mein masla aaya — sirf Arabic chala rahe hain.")
                st.audio(arabic_audio_url)

st.caption("Data source: alquran.cloud API")
