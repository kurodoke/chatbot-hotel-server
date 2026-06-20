# -*- coding: utf-8 -*-
"""
LLM-as-a-Judge Evaluator -- Hotel Chatbot Fine-Tuning
======================================================
Generator  : ft:gpt-4.1-nano-2025-04-14:aa:hotel-recommed-ft4:CtrN2HoF
Judge      : gpt-4.1
Test Cases : 50 pesan otomatis
Aspek      : Naturalness | Relevance | Faithfulness | Format Compliance
OpenAI SDK : 0.27.x (legacy ChatCompletion API)
"""

import sys
import os
import io

# -- Fix Windows terminal encoding (cp1252 -> utf-8) -------------------
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONUTF8', '1')

# -- Pastikan path ke rasa-backend bisa di-import ---------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RASA_DIR = os.path.join(BASE_DIR, "rasa-backend")
sys.path.insert(0, RASA_DIR)

import json
import re
import time
import datetime
import requests
import openai
import pandas as pd
from itertools import combinations
from dotenv import load_dotenv
from rapidfuzz import fuzz

# -- Load env ----------------------------------------------------------
load_dotenv(os.path.join(BASE_DIR, ".env"))
openai.api_key = os.getenv("OPENAI_API_KEY")

# -- Konstanta Model ---------------------------------------------------
FINE_TUNED_MODEL = "ft:gpt-4.1-nano-2025-04-14:aa:hotel-recommed-ft4:CtrN2HoF"
JUDGE_MODEL      = "gpt-4.1"
GEMINI_URL       = "http://localhost:5007/generate"
HOTEL_DATA_PATH  = os.path.join(RASA_DIR, "data", "hotel_data.json")

# ======================================================================
# SYSTEM PROMPT GENERATOR (sama persis dengan produksi)
# ======================================================================
SYSTEM_PROMPT_GENERATOR = """Anda adalah asisten travel AI yang ahli membuat ulasan hotel terstruktur dan estetis dalam format Markdown.

Tugas:
1. Buat rekomendasi hotel berdasarkan data input dan preference user.
2. Jika match_status bernilai "fallback_recommendation":
   - WAJIB memulai dengan permintaan maaf yang sopan.
   - WAJIB menjelaskan bahwa hotel yang ditampilkan adalah alternatif terbaik.
   - DILARANG mengarang fakta, opini subjektif, atau klaim yang tidak ada di data.

ATURAN FORMAT (WAJIB DIIKUTI PERSIS):

1. Header utama WAJIB menggunakan format berikut:
   ### \U0001f50d **Rekomendasi Hotel Terbaik untuk Anda**
   Diikuti paragraf penjelasan yang:
   - Relevan dengan preference user
   - Jika fallback, berisi permintaan maaf + penjelasan alternatif terbaik

2. Setelah paragraf pembuka, WAJIB menampilkan pemisah:
   ***

3. Setiap hotel utama WAJIB menggunakan format berikut:
   #### \U0001f3e8 **[No]. [Nama Hotel]**

   ![[Nama Hotel]](http://localhost:3000/[nama-file-gambar].jpg)

   \u2b50 **Rating**: [Rating] \u2022 [Tipe]

   \U0001f4dd [Deskripsi singkat berbasis data, tanpa opini tambahan]

   \U0001f4b0 **Harga**: Rp[Harga] / malam \u2014 [Komentar netral berbasis data]

   \u2728 **Fasilitas Unggulan**:
\u25ab\ufe0f [Fasilitas 1]
\u25ab\ufe0f [Fasilitas 2]
\u25ab\ufe0f [Fasilitas 3]

   \U0001f517 **[Lihat Detail Hotel](URL)**

4. Setelah daftar hotel utama, WAJIB menampilkan pemisah:
   ***

5. Jika data alternatives tidak kosong, tampilkan dengan format:
   #### \U0001f4a1 **Alternatif Lain ([Label])**
**\U0001f3e8 [Nama Hotel]** \u2794 \U0001f4b0 Rp[Harga] / malam
\U0001f517 **[Lihat Detail](URL)**

6. Footer WAJIB ditampilkan di bagian paling bawah:
   <center>\u2139\ufe0f *Catatan: Harga dapat berubah sewaktu-waktu.*</center>

7. Gunakan Markdown standar.
   - BOLEH menggunakan <center>
   - BOLEH menggunakan ***
   - JANGAN menggunakan tag <br/>
   - JANGAN menambahkan section atau teks di luar format ini
"""

# ======================================================================
# JUDGE PROMPT
# ======================================================================
JUDGE_PROMPT = """Anda adalah evaluator independen chatbot rekomendasi hotel.

Anda akan diberikan:
1. INPUT DATA - berisi preferensi user dan data hotel yang dipilih sistem
2. GENERATED RESPONSE - respons yang dihasilkan oleh model AI fine-tuned

Nilai respons AI berdasarkan 4 aspek berikut (skala 1-5):

1. Naturalness (Kealamian Bahasa)
   - Apakah terdengar seperti manusia, tidak kaku?
   - Apakah kalimat mengalir dengan baik?
   - Apakah pemilihan kata terasa natural?

2. Relevance (Relevansi)
   - Apakah sesuai dengan preference user yang diminta?
   - Apakah hotel yang ditampilkan relevan dengan preferensi?
   - Apakah informasi yang diberikan berguna?

3. Faithfulness (Keakuratan Data)
   - Apakah semua informasi berasal dari data input yang diberikan?
   - Apakah ada indikasi mengarang fakta (hallucination)?
   - Apakah harga, nama, fasilitas sesuai dengan data?

4. Format Compliance (Kepatuhan Format)
   - Apakah menggunakan header yang benar?
   - Apakah menggunakan pemisah ***?
   - Apakah setiap hotel pakai format dengan nomor dan nama?
   - Apakah ada footer catatan harga?

Berikan output JSON valid saja. JANGAN tambahkan teks apapun di luar JSON.

Format output:
{
  "naturalness": <1-5>,
  "relevance": <1-5>,
  "faithfulness": <1-5>,
  "format_compliance": <1-5>,
  "overall": <rata-rata dari 4 aspek, 2 desimal>,
  "reasoning": "<penjelasan singkat dalam Bahasa Indonesia>"
}
"""

# ======================================================================
# 50 TEST CASES - Pesan yang sering digunakan user
# Kategori: harga, lokasi, fasilitas, tipe kamar, bintang, kombinasi, natural
# ======================================================================
TEST_MESSAGES = [
    # -- Berdasarkan Harga (5) -----------------------------------------
    "Rekomendasikan hotel yang murah di Bengkulu",
    "Cari hotel budget terjangkau untuk liburan keluarga",
    "Hotel paling murah yang ada di sini",
    "Saya cari hotel yang harganya ekonomis",
    "Ada hotel yang murah tapi nyaman?",

    # -- Berdasarkan Lokasi (5) ----------------------------------------
    "Hotel yang dekat pantai dong",
    "Saya ingin hotel yang dekat dengan pusat kota",
    "Carikan hotel yang dekat pantai di Bengkulu",
    "Hotel yang dekat dengan pusat perbelanjaan",
    "Cari hotel yang strategis di tengah kota",

    # -- Berdasarkan Fasilitas (10) ------------------------------------
    "Hotel yang ada kolam renangnya",
    "Rekomendasikan hotel dengan WiFi gratis",
    "Hotel yang ada restoran dan kafenya",
    "Cari hotel dengan fasilitas spa",
    "Hotel yang ada fitness center atau gym",
    "Hotel yang punya fasilitas rapat dan meeting room",
    "Cari hotel yang ada kolam renang dan restoran",
    "Hotel dengan layanan antar jemput bandara",
    "Hotel yang menyediakan sarapan pagi",
    "Cari hotel dengan parkir gratis",

    # -- Berdasarkan Tipe Kamar (10) -----------------------------------
    "Hotel yang ada kamar deluxe",
    "Saya mau kamar suite yang mewah",
    "Rekomendasikan hotel dengan kamar superior",
    "Cari hotel yang punya kamar family",
    "Hotel dengan kamar tipe twin bed",
    "Hotel yang ada kamar dengan king bed",
    "Saya butuh kamar double untuk berdua",
    "Cari hotel yang punya kamar junior suite",
    "Hotel dengan pilihan kamar yang bervariasi",
    "Rekomendasikan hotel dengan kamar deluxe twin",

    # -- Berdasarkan Bintang (5) ---------------------------------------
    "Hotel bintang 3 yang bagus",
    "Cari hotel bintang 4 di Bengkulu",
    "Saya ingin menginap di hotel bintang 2",
    "Rekomendasikan hotel bintang 3 yang terjangkau",
    "Hotel bintang 4 yang dekat pantai",

    # -- Kombinasi Kriteria (10) ---------------------------------------
    "Hotel murah yang dekat pantai",
    "Cari hotel bintang 3 dengan kolam renang",
    "Hotel dekat pusat kota dengan wifi gratis",
    "Rekomendasikan hotel murah dengan kamar deluxe",
    "Hotel bintang 3 yang ada restoran",
    "Cari hotel dekat pantai dengan kamar suite",
    "Hotel dengan kolam renang dan dekat kota",
    "Hotel murah dengan fasilitas lengkap",
    "Hotel bintang 2 yang nyaman dan murah",
    "Cari hotel yang ada spa dan kolam renang",

    # -- Gaya Percakapan Natural (5) ----------------------------------
    "Mau liburan, kira-kira hotel apa yang cocok buat keluarga?",
    "Lagi cari tempat menginap yang enak buat honeymoon",
    "Rekomendasiin dong hotel yang bagus buat liburan akhir tahun",
    "Pengen staycation, ada hotel yang recommend?",
    "Butuh hotel buat acara bisnis, ada yang punya ruang rapat?",
]

assert len(TEST_MESSAGES) == 50, f"Harus tepat 50 test case, sekarang: {len(TEST_MESSAGES)}"


# ======================================================================
# FUNGSI HELPER (disalin dari action_recommend_hotel.py)
# ======================================================================

def convert_to_meters(s):
    if isinstance(s, str):
        if s.endswith('km'):
            return float(s[:-2]) * 1000
        elif s.endswith('m'):
            return float(s[:-1])
        else:
            raise ValueError('Invalid unit')
    elif isinstance(s, float):
        return s
    else:
        raise TypeError('Invalid input type')


def get_max_distance(data, field_name):
    distances = []
    for h in data:
        val = h.get(field_name)
        if val:
            try:
                val = val.replace(",", ".").strip()
                distances.append(convert_to_meters(val))
            except Exception:
                pass
    return max(distances) if distances else 5000


def hitung_threshold_harga_kamar(data):
    semua_harga = [
        kamar["harga"]
        for h in data.get("hotel", [])
        for kamar in h.get("kamar", [])
        if "harga" in kamar
    ]
    return sum(semua_harga) / len(semua_harga) if semua_harga else 500000


def filter_hotels(hotels, parsed_preferences):
    slot_star     = parsed_preferences.get("star")
    slot_type     = parsed_preferences.get("type")
    slot_facility = parsed_preferences.get("facility")
    slot_location = parsed_preferences.get("location")
    slot_bed      = parsed_preferences.get("bed")

    hard_filtered = []
    for hotel in hotels:
        match = True

        if slot_star and hotel.get("bintang", 0) != int(slot_star):
            match = False

        if match and slot_type:
            hotel_tipe_list = [k["tipe"].lower() for k in hotel.get("kamar", [])]
            slot_type_list  = slot_type if isinstance(slot_type, list) else [slot_type]
            slot_type_list  = [s.lower() for s in slot_type_list]
            if not any(t in hotel_tipe_list for t in slot_type_list):
                match = False

        if match and slot_facility:
            hotel_facilities   = [f.lower() for f in hotel.get("fasilitas", [])]
            slot_facility_list = slot_facility if isinstance(slot_facility, list) else [slot_facility]
            slot_facility_list = [f.lower() for f in slot_facility_list]
            if not all(f in hotel_facilities for f in slot_facility_list):
                match = False

        if match and slot_location and "pantai" in slot_location.lower():
            jarak_str = hotel.get("jarak_ke_pantai", "999 km").replace(",", ".").strip()
            jarak_m   = convert_to_meters(jarak_str)
            if jarak_m > get_max_distance(hotels, "jarak_ke_pantai"):
                match = False

        if match and slot_location and "kota" in slot_location.lower():
            jarak_str = hotel.get("jarak_ke_pusat_kota", "999 km").replace(",", ".").strip()
            jarak_m   = convert_to_meters(jarak_str)
            if jarak_m > get_max_distance(hotels, "jarak_ke_pusat_kota"):
                match = False

        if match:
            hard_filtered.append(hotel)

    if not hard_filtered:
        soft_filtered = []
        criteria = []
        if slot_star:     criteria.append("star")
        if slot_type:     criteria.append("type")
        if slot_facility: criteria.append("facility")
        if slot_location: criteria.append("location")
        if slot_bed:      criteria.append("bed")

        for r in range(len(criteria), 0, -1):
            for subset in combinations(criteria, r):
                temp_filtered = []
                for hotel in hotels:
                    match = True
                    for c in subset:
                        if c == "star" and hotel.get("bintang", 0) != int(slot_star):
                            match = False
                        if c == "type":
                            hotel_tipe_list = [k["tipe"].lower() for k in hotel.get("kamar", [])]
                            slot_type_list  = slot_type if isinstance(slot_type, list) else [slot_type]
                            if not any(t in hotel_tipe_list for t in [s.lower() for s in slot_type_list]):
                                match = False
                        if c == "facility":
                            hotel_facilities   = [f.lower() for f in hotel.get("fasilitas", [])]
                            slot_facility_list = slot_facility if isinstance(slot_facility, list) else [slot_facility]
                            if not all(f in hotel_facilities for f in [f.lower() for f in slot_facility_list]):
                                match = False
                        if c == "location" and slot_location and "pantai" in slot_location.lower():
                            jarak_str = hotel.get("jarak_ke_pantai", "999 km").replace(",", ".").strip()
                            if convert_to_meters(jarak_str) > get_max_distance(hotels, "jarak_ke_pantai"):
                                match = False
                        if c == "location" and slot_location and "kota" in slot_location.lower():
                            jarak_str = hotel.get("jarak_ke_pusat_kota", "999 km").replace(",", ".").strip()
                            if convert_to_meters(jarak_str) > get_max_distance(hotels, "jarak_ke_pusat_kota"):
                                match = False
                        if c == "bed":
                            hotel_beds    = [k["ranjang"].get("tipe", "").lower() for k in hotel.get("kamar", [])]
                            slot_bed_list = slot_bed if isinstance(slot_bed, list) else [slot_bed]
                            if not any(b in hotel_beds for b in [b.lower() for b in slot_bed_list]):
                                match = False
                    if match:
                        temp_filtered.append(hotel)
                if temp_filtered:
                    soft_filtered = temp_filtered
                    break
            if soft_filtered:
                break

        return [soft_filtered, True] if soft_filtered else [hotels, True]
    else:
        return [hard_filtered, False]


# ======================================================================
# PIPELINE: parse -> filter -> rank -> build input_data
# ======================================================================

def parse_preference(user_message: str) -> dict:
    """Panggil Gemini service lokal untuk parsing preferensi."""
    facility_mapping = [
        "Resepsionis", "Resepsionis 24 jam", "Keamanan 24 jam", "Laundry",
        "Penitipan bagasi", "Staff multibahasa", "Restoran ber-AC", "Sarapan",
        "Sarapan prasmanan", "Kafe", "ATM/Bank", "Salon kecantikan", "Mini market",
        "AC", "Aula", "Ruang keluarga", "Layanan kamar 24 jam", "Restoran",
        "WiFi di area umum", "Antar-jemput bandara", "Transportasi ke pantai",
        "Parkir berjaga", "TV kabel", "Meja", "Pancuran", "TV", "Ruang rapat",
        "Fasilitas rapat", "Printer", "Proyektor", "WiFi gratis", "Area parkir",
        "Kopi/teh di lobby", "Lift", "Layanan kamar", "Brankas", "Kulkas",
        "Bar", "Layanan pijat", "Parkir valet", "Kolam renang", "Teras rooftop",
        "Spa", "Pusat kebugaran", "Kolam renang indoor", "Kolam renang outdoor",
        "Kolam renang anak", "Penitipan anak", "Area main anak", "Taman",
        "Antar-jemput bandara berbiaya", "Sarapan a la carte",
    ]
    prompt = f"""
    Kamu adalah AI extractor preferensi hotel.
    Ambil preferensi dari pesan berikut dalam format JSON.
    Format output HARUS JSON valid:
    {{
      "recommend": "...",
      "price": "...",
      "location": "...",
      "facility": "...",
      "type": "...",
      "bed": "...",
      "star": "..."
    }}

    Daftar Fasilitas Valid: {", ".join(facility_mapping)}

    Aturan:
    - recommend: true jika user ingin rekomendasi, false jika tidak
    - price: "murah" atau "mahal"
    - location: "pantai" atau "kota"
    - facility: array fasilitas yang diminta, HARUS persis dari Daftar Fasilitas Valid. Jika tidak ada, null.
    - type: array tipe kamar. Jika tidak ada, null.
    - bed: jenis kasur ("twin", "double", "single", "king"). Jika tidak ada, null.
    - star: angka bintang saja (1-5). Jika tidak ada, null.
    - Jika tidak disebutkan, isi null.

    Pesan user:
    "{user_message}"
    """

    try:
        response = requests.post(GEMINI_URL, json={"prompt": prompt}, timeout=30)
        ai_reply = response.json()["reply"]
        text = re.sub(r"^```[a-zA-Z]*\n?", "", ai_reply.strip())
        text = re.sub(r"```$", "", text.strip()).strip().rstrip(",")
        data = json.loads(text)
        # Normalize comma-separated strings to lists
        for key, value in data.items():
            if isinstance(value, str) and "," in value:
                data[key] = [item.strip() for item in value.split(",") if item.strip()]
        return data
    except Exception as e:
        print(f"  [WARN] Gemini parse error: {e}")
        return {"recommend": True}


def build_input_data(user_text: str, data: dict):
    """Jalankan seluruh pipeline scoring & filtering, return (input_data, match_status)."""
    hotels = data.get("hotel", [])
    parsed = parse_preference(user_text)

    slot_price    = parsed.get("price")
    slot_location = parsed.get("location")
    slot_type     = parsed.get("type")
    slot_facility = parsed.get("facility")
    slot_bed      = parsed.get("bed")
    slot_star     = parsed.get("star")

    # Jika tidak ada slot apapun, pakai semua hotel
    if not any([slot_price, slot_location, slot_type, slot_facility, slot_bed, slot_star]):
        parsed["recommend"] = True

    THRESHOLD_HARGA_GLOBAL = hitung_threshold_harga_kamar(data)
    MAX_JARAK_PANTAI       = get_max_distance(hotels, "jarak_ke_pantai")
    MAX_JARAK_KOTA         = get_max_distance(hotels, "jarak_ke_pusat_kota")

    weight = {
        "harga": 0.25, "lokasi": 0.25, "tipe": 0.2,
        "fasilitas": 0.1, "rating": 0.1, "bed": 0.05, "star": 0.05
    }
    boost_factor = 1.5
    if slot_location: weight["lokasi"]    *= boost_factor
    if slot_type:     weight["tipe"]      *= boost_factor
    if slot_facility: weight["fasilitas"] *= boost_factor
    if slot_price:    weight["harga"]     *= boost_factor
    if slot_bed:      weight["bed"]       *= boost_factor
    if slot_star:     weight["star"]      *= boost_factor

    total_w = sum(weight.values())
    for k in weight:
        weight[k] /= total_w

    [filtered_hotels, isNotFound] = filter_hotels(hotels, parsed)

    ranking = []
    for hotel in filtered_hotels:
        score_harga = 0
        if slot_price:
            try:
                harga_rata2 = sum(k["harga"] for k in hotel["kamar"]) / len(hotel["kamar"])
            except ZeroDivisionError:
                harga_rata2 = 0
            if slot_price.lower() == "murah":
                score_harga += max(0, THRESHOLD_HARGA_GLOBAL - harga_rata2) / 100000
            elif slot_price.lower() == "mahal":
                score_harga += max(0, harga_rata2 - THRESHOLD_HARGA_GLOBAL) / 100000

        score_lokasi = 0
        if slot_location:
            if "pantai" in slot_location.lower():
                try:
                    jarak_str  = hotel.get("jarak_ke_pantai", "0 km").replace(",", ".").strip()
                    jarak_m    = convert_to_meters(jarak_str)
                    score_lokasi += max(0, 5 * (1 - jarak_m / MAX_JARAK_PANTAI))
                except Exception:
                    pass
            elif "kota" in slot_location.lower():
                try:
                    jarak_str  = hotel.get("jarak_ke_pusat_kota", "0 m").replace(",", ".").strip()
                    jarak_m    = convert_to_meters(jarak_str)
                    score_lokasi += max(0, 2 * (1 - jarak_m / MAX_JARAK_KOTA))
                except Exception:
                    pass

        score_tipe = 0
        if slot_type:
            slot_type_list = slot_type if isinstance(slot_type, list) else [slot_type]
            slot_type_list = [s.lower() for s in slot_type_list]
            max_score      = 0
            for kamar in hotel["kamar"]:
                tipe_kamar = kamar.get("tipe", "").lower()
                for tipe_user in slot_type_list:
                    similarity = fuzz.partial_ratio(tipe_user, tipe_kamar)
                    if similarity > max_score:
                        max_score = similarity
            if max_score >= 90:   score_tipe += 3
            elif max_score >= 75: score_tipe += 2
            elif max_score >= 50: score_tipe += 1
            else:                 score_tipe -= 1

        score_fasilitas = 0
        if slot_facility:
            facility_user_list = slot_facility if isinstance(slot_facility, list) else [slot_facility]
            facility_user_list = [f.lower() for f in facility_user_list]
            for f_usr in facility_user_list:
                max_sim = 0
                for f_hotel in hotel.get("fasilitas", []):
                    sim = fuzz.partial_ratio(f_usr, f_hotel.lower())
                    if sim > max_sim:
                        max_sim = sim
                if max_sim >= 90:   score_fasilitas += 1.5
                elif max_sim >= 75: score_fasilitas += 1
                elif max_sim >= 50: score_fasilitas += 0.5

        score_rating = 0
        if "ulasan" in hotel and hotel["ulasan"]:
            total = 0
            for u in hotel["ulasan"]:
                sentiment = u.get("sentiment", "neutral")
                if sentiment == "positive":  total += 1
                elif sentiment == "negative": total -= 1
                else:                         total += 1
            score_rating += total / len(hotel["ulasan"])

        score_bed = 0
        if slot_bed:
            bed_user_list = slot_bed if isinstance(slot_bed, list) else [slot_bed]
            bed_user_list = [b.lower() for b in bed_user_list]
            for b_usr in bed_user_list:
                max_sim = 0
                for kamar in hotel["kamar"]:
                    sim = fuzz.partial_ratio(b_usr, kamar["ranjang"].get("tipe", "").lower())
                    if sim > max_sim:
                        max_sim = sim
                if max_sim >= 90:   score_bed += 1.5
                elif max_sim >= 75: score_bed += 1
                elif max_sim >= 50: score_bed += 0.5

        score_star = 0
        if slot_star:
            try:
                hotel_star = hotel.get("star", hotel.get("bintang", 0))
                diff       = abs(hotel_star - int(slot_star))
                if diff == 0:   score_star = 2
                elif diff == 1: score_star = 1
                else:           score_star = 0
            except Exception:
                pass

        total_score = (
            score_harga     * weight["harga"]     +
            score_lokasi    * weight["lokasi"]    +
            score_tipe      * weight["tipe"]      +
            score_fasilitas * weight["fasilitas"] +
            score_rating    * weight["rating"]    +
            score_bed       * weight["bed"]       +
            score_star      * weight["star"]
        )
        ranking.append((total_score, hotel))

    ranking.sort(key=lambda x: x[0], reverse=True)
    top3 = ranking[:3]

    if not top3:
        return None, "no_hotels"

    match_status = "fallback_recommendation" if isNotFound else "exact_match"

    gpt_hotels_list       = []
    gpt_alternatives_list = []

    if len(ranking) > 3:
        alt = ranking[3][1]
        gpt_alternatives_list.append({
            "nama":      alt.get("nama_hotel", "Hotel"),
            "rating":    alt.get("rating", 0),
            "tipe":      alt.get("tipe", "Hotel"),
            "bintang":   alt.get("bintang", alt.get("star", 3)),
            "harga":     int(sum(k["harga"] for k in alt["kamar"]) / len(alt["kamar"])),
            "lokasi":    alt.get("alamat", "Bengkulu"),
            "fasilitas": alt.get("fasilitas", []),
            "link":      alt.get("link", {}).get("traveloka", "#"),
        })

    for h in top3:
        h_data = h[1]
        gpt_hotels_list.append({
            "nama":      h_data.get("nama_hotel", "Hotel"),
            "photo":     h_data.get("photo", "http://localhost:3000/default_hotel.jpg"),
            "rating":    h_data.get("rating", 0),
            "tipe":      h_data.get("tipe", "Hotel"),
            "bintang":   h_data.get("bintang", h_data.get("star", 3)),
            "harga":     int(sum(k["harga"] for k in h_data["kamar"]) / len(h_data["kamar"])),
            "lokasi":    h_data.get("alamat", "Bengkulu"),
            "fasilitas": h_data.get("fasilitas", []),
            "link":      h_data.get("link", {}).get("traveloka", "#"),
        })

    input_data = {
        "preference":   user_text,
        "style":        "structured_review",
        "match_status": match_status,
        "hotels":       gpt_hotels_list,
        "alternatives": gpt_alternatives_list,
    }
    return input_data, match_status


# ======================================================================
# GENERATOR: Fine-tuned GPT (openai legacy v0.27.x)
# ======================================================================

def generate_response(input_data: dict) -> str:
    """Panggil fine-tuned GPT model (openai 0.27.x legacy API)."""
    response = openai.ChatCompletion.create(
        model=FINE_TUNED_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_GENERATOR},
            {"role": "user",   "content": json.dumps(input_data, ensure_ascii=False)},
        ],
        temperature=0.45,
    )
    return response["choices"][0]["message"]["content"]


# ======================================================================
# JUDGE: GPT-4.1 (openai legacy v0.27.x)
# ======================================================================

def judge_response(input_data: dict, generated_response: str) -> dict:
    """Panggil GPT-4.1 sebagai judge (openai 0.27.x legacy API)."""
    evaluation_prompt = (
        "INPUT DATA:\n\n"
        + json.dumps(input_data, indent=2, ensure_ascii=False)
        + "\n\nGENERATED RESPONSE:\n\n"
        + generated_response
    )

    response = openai.ChatCompletion.create(
        model=JUDGE_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user",   "content": evaluation_prompt},
        ],
        # response_format hanya ada di SDK >= 1.x, parse manual di sini
    )
    raw = response["choices"][0]["message"]["content"]
    # Bersihkan markdown code block jika ada
    raw = re.sub(r'^```[a-zA-Z]*\n?', '', raw.strip())
    raw = re.sub(r'```$', '', raw.strip()).strip()
    return json.loads(raw)


# ======================================================================
# OUTPUT FORMATTER
# ======================================================================

def format_score(val):
    """Warna skor ANSI: hijau (>=4), kuning (>=3), merah (<3)."""
    try:
        v = float(val)
        if v >= 4.0:   return f"\033[92m{v:.2f}\033[0m"
        elif v >= 3.0: return f"\033[93m{v:.2f}\033[0m"
        else:           return f"\033[91m{v:.2f}\033[0m"
    except Exception:
        return str(val)


def print_results_table(scores: list):
    """Cetak tabel hasil evaluasi ke terminal."""
    W = 120
    print("\n" + "=" * W)
    header = (
        f"  {'#':>3}  |  {'PESAN USER':<40}  |  {'Nat':>4}  |  {'Rel':>4}  |  "
        f"{'Faith':>5}  |  {'Fmt':>4}  |  {'Ovr':>5}  |  REASONING"
    )
    print(header)
    print("-" * W)

    for i, row in enumerate(scores, 1):
        msg    = row["message"][:38] + ".." if len(row["message"]) > 40 else row["message"]
        nat    = format_score(row.get("naturalness",      "ERR"))
        rel    = format_score(row.get("relevance",        "ERR"))
        faith  = format_score(row.get("faithfulness",     "ERR"))
        fmt    = format_score(row.get("format_compliance","ERR"))
        ovr    = format_score(row.get("overall",          "ERR"))
        reason = str(row.get("reasoning", ""))[:38]
        ok     = "OK" if row.get("status") == "ok" else "ERR"

        print(
            f"  {i:>3}  |  {msg:<40}  |  {nat:>4}  |  {rel:>4}  |  "
            f"{faith:>5}  |  {fmt:>4}  |  {ovr:>5}  |  {reason}"
        )

    print("-" * W)

    valid = [r for r in scores if r.get("status") == "ok"]
    if valid:
        df  = pd.DataFrame(valid)
        avg = df[["naturalness", "relevance", "faithfulness", "format_compliance", "overall"]].mean()
        print(
            f"\n  {'RATA-RATA':>44}  |  {format_score(avg['naturalness']):>4}  |  "
            f"{format_score(avg['relevance']):>4}  |  {format_score(avg['faithfulness']):>5}  |  "
            f"{format_score(avg['format_compliance']):>4}  |  {format_score(avg['overall']):>5}"
        )
        print(f"\n  [OK] Evaluasi selesai: {len(valid)}/{len(scores)} berhasil\n")
        print("=" * W + "\n")
    return valid


def save_results(scores: list, output_dir: str = "."):
    """Simpan hasil ke CSV dan JSON."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)

    valid = [r for r in scores if r.get("status") == "ok"]

    # -- CSV -----------------------------------------------------------
    csv_path = os.path.join(output_dir, f"llm_judge_results_{timestamp}.csv")
    if valid:
        df = pd.DataFrame(valid)
        cols_order = [
            "no", "message", "match_status",
            "naturalness", "relevance", "faithfulness", "format_compliance",
            "overall", "reasoning"
        ]
        cols_order = [c for c in cols_order if c in df.columns]
        df = df[cols_order]
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  [CSV] Tersimpan : {csv_path}")

    # -- JSON ----------------------------------------------------------
    json_path = os.path.join(output_dir, f"llm_judge_results_{timestamp}.json")

    # Buat salinan scores tanpa 'generated_response' (terlalu besar untuk JSON ringkas)
    results_clean = []
    for r in scores:
        rc = {k: v for k, v in r.items() if k != "generated_response"}
        results_clean.append(rc)

    summary = {
        "timestamp":       timestamp,
        "total_tests":     len(scores),
        "successful":      len(valid),
        "failed":          len(scores) - len(valid),
        "generator_model": FINE_TUNED_MODEL,
        "judge_model":     JUDGE_MODEL,
        "results":         results_clean,
    }
    if valid:
        df  = pd.DataFrame(valid)
        avg = df[["naturalness", "relevance", "faithfulness", "format_compliance", "overall"]].mean()
        summary["averages"] = {
            "naturalness":       round(float(avg["naturalness"]),       2),
            "relevance":         round(float(avg["relevance"]),         2),
            "faithfulness":      round(float(avg["faithfulness"]),      2),
            "format_compliance": round(float(avg["format_compliance"]), 2),
            "overall":           round(float(avg["overall"]),           2),
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  [JSON] Tersimpan : {json_path}\n")
    return csv_path, json_path


# ======================================================================
# MAIN
# ======================================================================

def main():
    print("\n" + "=" * 60)
    print("   [HOTEL] LLM-as-a-Judge -- Hotel Chatbot Evaluator")
    print(f"   Generator : {FINE_TUNED_MODEL[:48]}...")
    print(f"   Judge     : {JUDGE_MODEL}")
    print("   Test Cases: 50 pesan otomatis")
    print("=" * 60 + "\n")

    # Load hotel data
    print("[DATA] Memuat data hotel...", end=" ", flush=True)
    with open(HOTEL_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"OK ({len(data['hotel'])} hotel ditemukan)\n")

    # Cek koneksi Gemini lokal
    print("[LINK] Cek koneksi Gemini lokal (localhost:5007)...", end=" ", flush=True)
    gemini_ok = False
    try:
        r = requests.get("http://localhost:5007", timeout=5)
        gemini_ok = True
        print("ONLINE\n")
    except Exception:
        print("OFFLINE -- preference parsing akan gunakan fallback\n")

    scores     = []
    start_time = time.time()

    print(f"[START] Memulai evaluasi {len(TEST_MESSAGES)} test case...\n")

    for idx, message in enumerate(TEST_MESSAGES, 1):
        print(f"\n  -- Test #{idx:02d}/{len(TEST_MESSAGES)} " + "-" * 44)
        print(f"  [MSG] {message}")

        row = {
            "no":           idx,
            "message":      message,
            "status":       "error",
            "match_status": "unknown",
        }

        try:
            # 1. Parse + filter + rank -> build input_data
            print("  [1/3] Parsing + Filtering...", end=" ", flush=True)
            input_data, match_status = build_input_data(message, data)
            row["match_status"] = match_status

            if input_data is None:
                print("SKIP (tidak ada hotel)")
                row["reasoning"] = "Pipeline gagal menghasilkan input_data"
                scores.append(row)
                continue
            print(f"OK [{match_status}]")

            # 2. Generate dari fine-tuned GPT
            print("  [2/3] Generate (fine-tuned GPT)...", end=" ", flush=True)
            generated = generate_response(input_data)
            print(f"OK ({len(generated)} chars)")

            # 3. Judge dengan GPT-4.1
            print("  [3/3] Judge (GPT-4.1)...", end=" ", flush=True)
            judgment  = judge_response(input_data, generated)
            print("OK")

            row.update({
                "naturalness":       judgment.get("naturalness",       0),
                "relevance":         judgment.get("relevance",         0),
                "faithfulness":      judgment.get("faithfulness",      0),
                "format_compliance": judgment.get("format_compliance", 0),
                "overall":           judgment.get("overall",           0),
                "reasoning":         judgment.get("reasoning",         ""),
                "status":            "ok",
                "generated_response": generated,
            })

            nat   = judgment.get("naturalness",       "-")
            rel   = judgment.get("relevance",         "-")
            faith = judgment.get("faithfulness",      "-")
            fmt   = judgment.get("format_compliance", "-")
            ovr   = judgment.get("overall",           "-")
            print(f"  [SCORE] Nat:{nat} | Rel:{rel} | Faith:{faith} | Fmt:{fmt} | Ovr:{ovr}")
            print(f"  [NOTE]  {str(judgment.get('reasoning', ''))[:90]}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            row["reasoning"] = str(e)

        scores.append(row)

        # Jeda kecil untuk menghindari rate limit OpenAI
        if idx < len(TEST_MESSAGES):
            time.sleep(1.0)

    elapsed = time.time() - start_time
    print(f"\n\n  [TIME] Total waktu: {elapsed / 60:.1f} menit ({elapsed:.0f} detik)\n")

    # Tampilkan tabel ringkasan
    print_results_table(scores)

    # Simpan hasil ke disk
    output_dir = os.path.join(BASE_DIR, "evaluation_results")
    save_results(scores, output_dir=output_dir)

    # Ringkasan akhir
    valid = [r for r in scores if r.get("status") == "ok"]
    if valid:
        df  = pd.DataFrame(valid)
        avg = df[["naturalness", "relevance", "faithfulness", "format_compliance", "overall"]].mean()

        print("\n" + "=" * 55)
        print("   [SUMMARY] RINGKASAN EVALUASI AKHIR")
        print("-" * 55)
        print(f"   Naturalness       : {avg['naturalness']:.2f} / 5.00")
        print(f"   Relevance         : {avg['relevance']:.2f} / 5.00")
        print(f"   Faithfulness      : {avg['faithfulness']:.2f} / 5.00")
        print(f"   Format Compliance : {avg['format_compliance']:.2f} / 5.00")
        print("-" * 55)
        print(f"   Overall Average   : {avg['overall']:.2f} / 5.00")
        print(f"   Tests Berhasil    : {len(valid)}/{len(scores)}")
        print("=" * 55 + "\n")

    return scores


if __name__ == "__main__":
    main()
