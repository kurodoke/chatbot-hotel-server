# 🏨 LLM-as-a-Judge — Hotel Chatbot Evaluator

Script evaluasi otomatis untuk menilai kualitas output fine-tuned GPT pada sistem rekomendasi hotel Bengkulu.

---

## 📋 Arsitektur Evaluasi

```
User Message (50 test case)
        │
        ▼
┌─────────────────┐
│ Gemini Lokal    │  ← Parse preferensi user
│ (localhost:5007)│
└────────┬────────┘
         │ parsed_preferences
         ▼
┌─────────────────┐
│ Filter & Ranking│  ← Filter hotel + scoring algorithm
│ (hotel_data.json)│
└────────┬────────┘
         │ input_data (top 3 hotel)
         ▼
┌─────────────────┐
│ Fine-Tuned GPT  │  ← Generator: ft:gpt-4.1-nano (model produksi)
│ (Generator)     │
└────────┬────────┘
         │ generated_response
         ▼
┌─────────────────┐
│ GPT-4.1 Judge   │  ← Evaluator independen
└────────┬────────┘
         │ {naturalness, relevance, faithfulness, format_compliance, overall}
         ▼
   Tabel Hasil + CSV + JSON
```

---

## 🎯 Aspek Penilaian

| Aspek | Skala | Deskripsi |
|---|---|---|
| **Naturalness** | 1–5 | Kealamian bahasa, tidak kaku, mengalir |
| **Relevance** | 1–5 | Relevansi dengan preferensi user |
| **Faithfulness** | 1–5 | Akurasi data, tidak mengarang fakta |
| **Format Compliance** | 1–5 | Kepatuhan format Markdown yang diminta |
| **Overall** | 1–5 | Rata-rata dari 4 aspek |

---

## 🚀 Cara Menjalankan

### Prasyarat
Pastikan service Gemini lokal berjalan:
```bash
# Di terminal terpisah
cd genai-service
python app.py
```

### Install dependensi (jika belum)
```bash
pip install openai pandas rapidfuzz python-dotenv requests
```

### Jalankan evaluator
```bash
cd "d:\plan amv\Code\chatbot-hotel-server"
python llm_judge_evaluator.py
```

---

## 📊 Contoh Output

```
════════════════════════════════════════════════════════════════
   🏨  LLM-as-a-Judge — Hotel Chatbot Evaluator
   Generator : ft:gpt-4.1-nano-2025-04-14:aa:hotel-recommed-ft4...
   Judge     : gpt-4.1
   Test Cases: 50 pesan otomatis
════════════════════════════════════════════════════════════════

  ── Test #01 ────────────────────────────────────────
  💬 Pesan: Rekomendasikan hotel yang murah di Bengkulu
  ⚙️  Parsing preferences... ✅  [exact_match]
  🤖 Generating response (fine-tuned GPT)... ✅  (1243 chars)
  ⚖️  Judging response (GPT-4.1)... ✅
  📊 Skor → Nat:5 | Rel:5 | Faith:4 | Fmt:5 | Ovr:4.75
  💡 Bahasa natural dan format sesuai...

...

  ══════════════════════════════════════════════════════════
    📊  RINGKASAN EVALUASI AKHIR
  ──────────────────────────────────────────────────────────
    Naturalness      : 4.72 / 5.00
    Relevance        : 4.68 / 5.00
    Faithfulness     : 4.55 / 5.00
    Format Compliance: 4.91 / 5.00
  ──────────────────────────────────────────────────────────
    Overall Average  : 4.71 / 5.00
  ══════════════════════════════════════════════════════════
```

---

## 📁 Hasil Tersimpan

Setelah evaluasi selesai, hasil akan tersimpan di folder `evaluation_results/`:

- `llm_judge_results_YYYYMMDD_HHMMSS.csv` — Tabel lengkap (Excel-compatible)
- `llm_judge_results_YYYYMMDD_HHMMSS.json` — Data lengkap + metadata + rata-rata

---

## 📦 50 Test Cases

Mencakup variasi skenario:
- **Harga** (5 pesan): murah, budget, ekonomis
- **Lokasi** (5 pesan): dekat pantai, pusat kota, strategis
- **Fasilitas** (10 pesan): kolam renang, WiFi, spa, gym, restoran, dll
- **Tipe Kamar** (10 pesan): deluxe, suite, twin bed, king bed, dll
- **Bintang Hotel** (5 pesan): bintang 2, 3, 4
- **Kombinasi** (10 pesan): murah + pantai, bintang 3 + kolam renang, dll
- **Bahasa Natural** (5 pesan): liburan keluarga, honeymoon, staycation, dll

---

## ⚙️ Konfigurasi

Edit di `llm_judge_evaluator.py`:
```python
FINE_TUNED_MODEL = "ft:gpt-4.1-nano-2025-04-14:aa:hotel-recommed-ft4:CtrN2HoF"
JUDGE_MODEL      = "gpt-4.1"
GEMINI_URL       = "http://localhost:5007/generate"
```
