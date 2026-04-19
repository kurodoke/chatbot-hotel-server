
import json
from dotenv import load_dotenv
import requests


load_dotenv()


import json
import re

facility_mapping = [
  "Resepsionis",
  "Resepsionis 24 jam",
  "Keamanan 24 jam",
  "Laundry",
  "Penitipan bagasi",
  "Staff multibahasa",
  "Surat kabar di lobby",
  "Surat kabar",
  "Restoran ber-AC",
  "Sarapan",
  "Sarapan prasmanan",
  "Sarapan berbiaya",
  "Kafe",
  "Ruang makan",
  "Tanpa minuman beralkohol",
  "ATM/Bank",
  "Salon kecantikan",
  "Mini market",
  "Salon rambut",
  "Laundry Swadaya",
  "Toko",
  "Supermarket",
  "AC",
  "Aula",
  "Ruang keluarga",
  "Alat pemanas",
  "Area bebas asap rokok",
  "Area merokok",
  "Layanan kamar 24 jam",
  "Restoran",
  "Restoran untuk sarapan",
  "Restoran untuk makan malam",
  "Restoran untuk makan siang",
  "WiFi di area umum",
  "Antar-jemput bandara",
  "Transportasi ke pantai",
  "Parkir berjaga",
  "Transportasi ke pusat perbelanjaan",
  "Transportasi ke pusat perbelanjaan berbiaya",
  "TV kabel",
  "Meja",
  "Pancuran",
  "TV",
  "Ruang rapat",
  "Fasilitas rapat",
  "Printer",
  "Proyektor",
  "Jalan bagi penyandang disabilitas",
  "Lokasi mudah diakses",
  "Aksesibel bagi penyandang disabilitas",
  "WiFi gratis",
  "Area parkir",
  "Kopi/teh di lobby",
  "Lift",
  "Layanan kamar",
  "Brankas",
  "Kamar dengan pintu penghubung",
  "Brankas kamar",
  "Kulkas",
  "Makan malam dari menu",
  "Makan siang dari menu",
  "Bar",
  "Concierge/layanan tamu",
  "Internet Kamar",
  "WiFi di area umum berbiaya",
  "Layanan pijat",
  "Parkir valet",
  "Antar-jemput bandara berbiaya",
  "Banquet",
  "Pengering pakaian",
  "Perapian di lobby",
  "Kolam renang",
  "Teras rooftop",
  "Bebas rokok",
  "Teras",
  "Bellboy",
  "Late check-out",
  "Fasilitas nikah",
  "Sarapan a la carte",
  "Fasilitas bisnis",
  "Teater/auditorium",
  "Toko oleh-oleh",
  "Parkir bus/truk",
  "Penitipan anak",
  "Area main anak",
  "Sarapan kontinental",
  "Sarapan dengan makanan hangat",
  "Makan malam bermenu",
  "Menu makan siang",
  "Makanan ringan",
  "Penjaga pintu",
  "Porter",
  "Layanan sektretarial",
  "Transportasi di area hotel berbiaya",
  "Transportasi ke taman rekreasi berbiaya",
  "Spa",
  "Fasilitas komputer",
  "Fotocopy",
  "Pusat kebugaran",
  "Kolam renang indoor",
  "Penyewaan sepeda",
  "Sewa mobil",
  "Kolam renang anak",
  "Kolam renang outdoor",
  "Ruang santai",
  "Sarapan dan makan malam",
  "Sarapan dan makan siang",
  "Parkir bagi penyandang disabilitas",
  "Taman",
  "Layanan medis",
  "Ponsel",
  "Pengering rambut"
]

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

    Daftar Fasilitas Valid: {", ".join(facility_mapping)}

    Aturan:
    - recommend: state kalau textnya mengiginkan rekomendasi atau tidak, contoh "berikan", "rekomendasikan", "rekomendasi", "cari", "temukan", "carikan", "tampilkan", ambil true atau false saja.
    - price: "murah" atau "mahal".
    - location: "pantai" atau "kota".
    - facility: fasilitas yang diminta user, contoh "Pusat kebugaran", "WiFi gratis", "Kolam renang". jika data hanya satu saja maka wrap langsung pakai array contoh: ["Pusat kebugaran"], HARUS persis dengan "Daftar Fasilitas Valid". Jika tidak ada, isi null.
    - type: tipe kamar seperti "deluxe", "suite", "sea view". jika data hanya satu saja maka wrap langsung pakai array contoh: ["deluxe"]
    - bed: jenis kasur seperti "twin", "double", "single", "king".
    - star: rating hotel, contoh "bintang 4", "bintang 3", "bintang 2", "bintang 1". ambil angka saja
    - Jika tidak disebutkan, isi null.

    Aturan Khusus Fasilitas:
    1. Jika fasilitas yang diminta user kurang jelas, gunakan sinonim atau bahasa Inggris, konversikan ke nilai terdekat di "Daftar Fasilitas Valid".
    2. Contoh konversi:
       - "Kid's Club" -> "Penitipan anak"
       - "swimming pool" -> "Kolam renang"
       - "spa" -> "Spa"
       - "gym" atau "fitness center" -> "Pusat kebugaran"
       - "koneksi internet" -> "WiFi gratis"
    3. JANGAN pernah membuat fasilitas di luar daftar yang disediakan.

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