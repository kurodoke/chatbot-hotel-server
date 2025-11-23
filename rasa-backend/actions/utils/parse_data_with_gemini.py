
import json
from dotenv import load_dotenv
import requests


load_dotenv()


import json
import re

def parse_json(text: str):
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())

    text = text.strip().rstrip(",")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print("JSON parsing error:", e)
        print("Raw text:", text)
        return None

def normalize_fields(data: dict):
    for key, value in data.items():
        if isinstance(value, str) and "," in value:
            # split, trim, dan buang item kosong
            data[key] = [item.strip() for item in value.split(",") if item.strip()]
    return data


def parse_preference_with_gemini(user_message: str):
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

    Aturan:
    - recommend: state kalau textnya mengiginkan rekomendasi atau tidak, contoh "berikan", "rekomendasikan", "rekomendasi", "cari", "temukan", "carikan", "tampilkan", ambil true atau false saja.
    - price: "murah" atau "mahal".
    - location: "pantai" atau "kota".
    - facility: fasilitas yang diminta user, contoh "gym", "wifi", "kolam renang". jika data hanya satu saja maka wrap langsung pakai array contoh: ["gym"]
    - type: tipe kamar seperti "deluxe", "suite", "sea view". jika data hanya satu saja maka wrap langsung pakai array contoh: ["deluxe"]
    - bed: jenis kasur seperti "twin", "double", "single", "king".
    - star: rating hotel, contoh "bintang 4", "bintang 3", "bintang 2", "bintang 1". ambil angka saja
    - Jika tidak disebutkan, isi null.

    Pesan user:
    "{user_message}"
    """

    response = requests.post(
                "http://localhost:5007/generate",
                json={"prompt": prompt}
            )
    ai_reply = response.json()["reply"]
    try:
        data = parse_json(ai_reply)
        data = normalize_fields(data)
        return data
    except:
        return {}