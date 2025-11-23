# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
# from rasa_sdk.events import SlotSet, AllSlotsReset
# import json
# import google.generativeai as genai
# from rapidfuzz import fuzz

# # Setup Gemini
# genai.configure(api_key="YOUR_GEMINI_API_KEY")

# # ======================================================
# # FUNCTION: PARSE USER PREFERENCES WITH GEMINI
# # ======================================================
# def parse_preference_with_gemini(user_message: str):
#     prompt = f"""
#     Kamu adalah AI extractor preferensi hotel.
#     Ambil preferensi dari pesan berikut dalam format JSON.
#     Format output HARUS JSON valid:
#     {{
#       "price": "...",
#       "location": "...",
#       "facility": "...",
#       "type": "..."
#     }}

#     Aturan:
#     - price: "murah" atau "mahal".
#     - location: "pantai" atau "kota".
#     - facility: fasilitas yang diminta user, contoh "gym", "wifi", "kolam renang".
#     - type: tipe kamar seperti "deluxe", "suite", "sea view".
#     - Jika tidak disebutkan, isi null.

#     Pesan user:
#     "{user_message}"
#     """

#     response = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)

#     try:
#         text = response.text
#         return json.loads(text)
#     except:
#         return {}


# # ======================================================
# # ACTION: Menyimpan Preferensi Multi-turn dengan Gemini
# # ======================================================
# class ActionCollectPreference(Action):

#     def name(self):
#         return "action_collect_preference"

#     def run(self, dispatcher, tracker, domain):

#         user_msg = tracker.latest_message.get("text")
#         existing_pref = tracker.get_slot("preferences_json")

#         preferences = {}
#         if existing_pref:
#             preferences = json.loads(existing_pref)

#         # Extract preference dari pesan user
#         new_pref = parse_preference_with_gemini(user_msg)

#         # Merge/value override
#         for k, v in new_pref.items():
#             if v and v != "null":
#                 preferences[k] = v

#         dispatcher.utter_message(
#             text=f"Baik! Preferensimu sekarang sudah diperbarui:\n{preferences}"
#         )

#         return [SlotSet("preferences_json", json.dumps(preferences))]


# # ======================================================
# # ACTION: TOP-3 REKOMENDASI HOTEL (Scoring)
# # ======================================================
# class ActionRecommendHotelMulti(Action):

#     def name(self):
#         return "action_recommend_hotel_multi"

#     def run(self, dispatcher, tracker, domain):

#         # Load hotel JSON
#         with open("data/hotel_data.json", "r", encoding="utf-8") as f:
#             data = json.load(f)

#         hotels = data["hotel"]
#         pref_raw = tracker.get_slot("preferences_json")

#         if not pref_raw:
#             dispatcher.utter_message(text="Kamu belum memberikan preferensi hotel.")
#             return []

#         preferences = json.loads(pref_raw)

#         price_pref = preferences.get("price")
#         loc_pref = preferences.get("location")
#         facility_pref = preferences.get("facility")
#         type_pref = preferences.get("type")

#         scored = []

#         # ============== SCORING =================
#         for hotel in hotels:
#             score = 0

#             # --- harga ---
#             if price_pref:
#                 harga = sum(k["harga"] for k in hotel["kamar"]) / len(hotel["kamar"])
#                 if price_pref == "murah":
#                     score += max(0, 500000 - harga) / 100000
#                 elif price_pref == "mahal":
#                     score += max(0, harga - 500000) / 100000

#             # --- lokasi ---
#             if loc_pref:
#                 if loc_pref == "pantai":
#                     jarak = hotel.get("jarak_ke_pantai", "10 km")
#                 else:
#                     jarak = hotel.get("jarak_ke_pusat_kota", "10 km")

#                 jarak_m = float(jarak.lower().replace("km", "")) * 1000
#                 score += max(0, 3000 - jarak_m) / 1000

#             # --- fasilitas ---
#             if facility_pref:
#                 fasilitas = [f.lower() for f in hotel.get("fasilitas", [])]
#                 sim = max([fuzz.partial_ratio(facility_pref, f) for f in fasilitas] + [0])
#                 score += sim / 50

#             # --- tipe kamar ---
#             if type_pref:
#                 max_sim = 0
#                 for k in hotel["kamar"]:
#                     sim = fuzz.partial_ratio(type_pref.lower(), k["tipe"].lower())
#                     max_sim = max(max_sim, sim)
#                 score += max_sim / 50

#             scored.append((score, hotel))

#         # Sort top 3
#         scored.sort(key=lambda x: x[0], reverse=True)
#         top3 = scored[:3]

#         # Format dengan Gemini
#         prompt = f"""
#         Formatkan rekomendasi hotel berikut secara menarik, alami, dan mudah dipahami.
#         Tampilkan dalam format:

#         1. Nama hotel – skor
#            - Alamat:
#            - Fasilitas penting:
#            - Link:
#            - Cocok karena:

#         Data hotel:
#         {json.dumps([{
#             "name": h[1]["nama_hotel"],
#             "score": h[0],
#             "address": h[1]["alamat"],
#             "fasilitas": h[1]["fasilitas"],
#             "link": h[1]["link"]["traveloka"]
#         } for h in top3], indent=2)}
#         """

#         res = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)

#         dispatcher.utter_message(res.text)

#         return []


# # ======================================================
# # RESET SLOT
# # ======================================================
# class ActionResetPreferences(Action):
#     def name(self):
#         return "action_reset_preferences"

#     def run(self, dispatcher, tracker, domain):
#         return [SlotSet("preferences_json", None), AllSlotsReset()]
