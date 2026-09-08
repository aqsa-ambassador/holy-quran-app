import streamlit as st
import requests
import json
import streamlit.components.v1 as components

BASE_URL = "https://api.alquran.cloud/v1"

st.set_page_config(page_title="Holy Qur'an", page_icon="📖", layout="centered")


# ---------------------- Data helpers ----------------------

@st.cache_data(ttl=60 * 60 * 24)
def get_surah_list():
    r = requests.get(f"{BASE_URL}/surah", timeout=15)
    r.raise_for_status()
    return r.json()["data"]


@st.cache_data(ttl=60 * 60 * 24)
def get_surah_data(surah, edition):
    """Fetch a whole surah (all ayahs) for a given text or audio edition in one call."""
    r = requests.get(f"{BASE_URL}/surah/{surah}/{edition}", timeout=20)
    r.raise_for_status()
    return r.json()["data"]["ayahs"]


@st.cache_data(ttl=60 * 60 * 24)
def find_audio_edition(language):
    """Find an available audio edition (recitation) for a translation language."""
    r = requests.get(f"{BASE_URL}/edition?format=audio&language={language}", timeout=15)
    r.raise_for_status()
    data = r.json()["data"]
    return data[0]["identifier"] if data else None


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
surah_name = surahs[idx]["englishName"]

st.divider()
mode = st.radio("Aap kya karna chahte hain?", ["📖 Read (Parhna)", "🔊 Listen (Sunna)"], horizontal=True)

if mode.startswith("📖"):
    choice = st.radio("Translation bhi dikhayen?", ["Sirf Arabic", "Arabic + Urdu", "Arabic + English"])

    try:
        arabic_ayahs = get_surah_data(surah_number, "quran-uthmani")
    except Exception:
        st.error("Surah load nahi ho saki.")
        st.stop()

    urdu_ayahs = english_ayahs = None
    if "Urdu" in choice:
        urdu_ayahs = get_surah_data(surah_number, "ur.jalandhry")
    if "English" in choice:
        english_ayahs = get_surah_data(surah_number, "en.sahih")

    st.subheader(f"Surah {surah_name}")

    AYAHS_PER_PAGE = 10
    total_ayahs = len(arabic_ayahs)
    total_pages = max(1, (total_ayahs + AYAHS_PER_PAGE - 1) // AYAHS_PER_PAGE)

    # Reset to page 1 whenever the surah changes
    if st.session_state.get("read_surah") != surah_number:
        st.session_state["read_surah"] = surah_number
        st.session_state["read_page"] = 1

    if total_pages > 1:
        nav1, nav2, nav3 = st.columns([1, 2, 1])
        with nav1:
            if st.button("⬅️ Previous", disabled=st.session_state["read_page"] <= 1):
                st.session_state["read_page"] -= 1
        with nav3:
            if st.button("Next ➡️", disabled=st.session_state["read_page"] >= total_pages):
                st.session_state["read_page"] += 1
        with nav2:
            st.markdown(
                f"<div style='text-align:center'>Page {st.session_state['read_page']} of {total_pages}</div>",
                unsafe_allow_html=True,
            )

    page = st.session_state.get("read_page", 1)
    start = (page - 1) * AYAHS_PER_PAGE
    end = start + AYAHS_PER_PAGE

    for i in range(start, min(end, total_ayahs)):
        ayah = arabic_ayahs[i]
        st.markdown(f"**{ayah['numberInSurah']}.**")
        st.markdown(
            f"<div style='font-size:28px; text-align:right; direction:rtl; line-height:1.8'>{ayah['text']}</div>",
            unsafe_allow_html=True,
        )
        if urdu_ayahs:
            st.markdown(f"*Urdu:* {urdu_ayahs[i]['text']}")
        if english_ayahs:
            st.markdown(f"*English:* {english_ayahs[i]['text']}")
        st.markdown("---")

else:
    choice = st.radio(
        "Kis tarah sunna chahte hain?",
        ["Arabic + Urdu Translation", "Arabic + English Translation", "Sirf Arabic"],
    )

    try:
        arabic_ayahs = get_surah_data(surah_number, "ar.alafasy")
    except Exception:
        st.error("Surah audio load nahi hua.")
        st.stop()

    trans_ayahs = None
    lang_label = ""
    if choice != "Sirf Arabic":
        lang_code = "ur" if "Urdu" in choice else "en"
        lang_label = "Urdu" if lang_code == "ur" else "English"
        try:
            trans_edition = find_audio_edition(lang_code)
            trans_ayahs = get_surah_data(surah_number, trans_edition) if trans_edition else None
        except Exception:
            trans_ayahs = None
        if not trans_ayahs:
            st.warning(f"{lang_label} mein translation audio available nahi hai — sirf Arabic sunayenge.")

    st.subheader(f"Surah {surah_name}")

    # Build a continuous playlist: Arabic ayah, then its translation, then next ayah...
    tracks = []
    for i, ayah in enumerate(arabic_ayahs):
        tracks.append({"url": ayah["audio"], "label": f"Ayat {ayah['numberInSurah']} — Arabic"})
        if trans_ayahs:
            tracks.append(
                {"url": trans_ayahs[i]["audio"], "label": f"Ayat {ayah['numberInSurah']} — {lang_label} Translation"}
            )

    tracks_json = json.dumps(tracks)

    player_html = f"""
    <div style="font-family:sans-serif; color:#eee;">
      <button id="startBtn" style="padding:10px 18px;font-size:16px;border-radius:8px;
        border:none;background:#2e7d32;color:white;cursor:pointer;">▶️ Surah Sunna Shuru Karein</button>
      <div id="nowPlaying" style="font-size:16px;margin:12px 0 6px 0;"></div>
      <audio id="player" controls style="width:100%"></audio>
    </div>
    <script>
      const tracks = {tracks_json};
      let idx = 0;
      const player = document.getElementById('player');
      const label = document.getElementById('nowPlaying');
      const btn = document.getElementById('startBtn');

      function loadTrack(i) {{
        if (i >= tracks.length) {{
          label.innerText = "✅ Surah khatam ho gayi.";
          return;
        }}
        player.src = tracks[i].url;
        label.innerText = "🔊 " + tracks[i].label;
        player.play();
      }}

      btn.addEventListener('click', () => {{
        idx = 0;
        loadTrack(idx);
        btn.style.display = 'none';
      }});

      player.addEventListener('ended', () => {{
        idx++;
        loadTrack(idx);
      }});
    </script>
    """
    components.html(player_html, height=200)

st.caption("Data source: alquran.cloud API")
