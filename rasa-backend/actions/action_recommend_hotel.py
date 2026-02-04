from difflib import get_close_matches
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import json
from rasa_sdk.events import FollowupAction, AllSlotsReset, SlotSet

from actions.utils.parse_data_with_gemini import parse_preference_with_gemini
from actions.utils.generate_response_from_gpt import generate_response_from_gpt 
from actions.utils.get_max_distance import get_max_distance
from actions.utils.convert_km_to_meter import convert_to_meters
from actions.utils.threshold_price_room import hitung_threshold_harga_kamar
from rapidfuzz import fuzz
from itertools import combinations

import os
from dotenv import load_dotenv

load_dotenv()  # load .env dari root project

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

def filter_hotels(hotels, parsed_preferences):
    # Ambil preferensi user
    slot_star = parsed_preferences.get("star")
    slot_type = parsed_preferences.get("type")
    slot_facility = parsed_preferences.get("facility")
    slot_location = parsed_preferences.get("location")
    slot_bed = parsed_preferences.get("bed")

    # ---- 1. Hard filter: harus memenuhi semua slot ----
    hard_filtered = []
    for hotel in hotels:
        match = True

        # star
        if slot_star and hotel.get("bintang", 0) != int(slot_star):
            match = False

        # tipe kamar
        if match and slot_type:
            hotel_tipe_list = [k["tipe"].lower() for k in hotel.get("kamar", [])]
            slot_type_list = slot_type if isinstance(slot_type, list) else [slot_type]
            slot_type_list = [s.lower() for s in slot_type_list]
            if not any(t in hotel_tipe_list for t in slot_type_list):
                match = False

        # fasilitas
        if match and slot_facility:
            hotel_facilities = [f.lower() for f in hotel.get("fasilitas", [])]
            slot_facility_list = slot_facility if isinstance(slot_facility, list) else [slot_facility]
            slot_facility_list = [f.lower() for f in slot_facility_list]
            if not all(f in hotel_facilities for f in slot_facility_list):
                match = False

        # lokasi
        if match and slot_location and "pantai" in slot_location.lower():
            jarak_str = hotel.get("jarak_ke_pantai", "999 km").replace(",", ".").strip()
            jarak_m = convert_to_meters(jarak_str)
            if jarak_m > get_max_distance(hotels, "jarak_ke_pantai"):
                match = False
                
        if match and slot_location and "kota" in slot_location.lower():
            jarak_str = hotel.get("jarak_ke_pusat_kota", "999 km").replace(",", ".").strip()
            jarak_m = convert_to_meters(jarak_str)
            if jarak_m > get_max_distance(hotels, "jarak_ke_pusat_kota"):
                match = False

        if match:
            hard_filtered.append(hotel)

    # ---- 2. Jika filter kosong, fallback: soft match subset kriteria ----
    if not hard_filtered:
        soft_filtered = []
        # buat list kombinasi slot yang bisa dipakai
        criteria = []
        if slot_star: criteria.append("star")
        if slot_type: criteria.append("type")
        if slot_facility: criteria.append("facility")
        if slot_location: criteria.append("location")
        if slot_bed: criteria.append("bed")

        # coba subset terbesar dulu
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
                            slot_type_list = slot_type if isinstance(slot_type, list) else [slot_type]
                            slot_type_list = [s.lower() for s in slot_type_list]
                            if not any(t in hotel_tipe_list for t in slot_type_list):
                                match = False
                        if c == "facility":
                            hotel_facilities = [f.lower() for f in hotel.get("fasilitas", [])]
                            slot_facility_list = slot_facility if isinstance(slot_facility, list) else [slot_facility]
                            slot_facility_list = [f.lower() for f in slot_facility_list]
                            if not all(f in hotel_facilities for f in slot_facility_list):
                                match = False
                        if c == "location" and "pantai" in slot_location.lower():
                            jarak_str = hotel.get("jarak_ke_pantai", "999 km").replace(",", ".").strip()
                            jarak_m = convert_to_meters(jarak_str)
                            if jarak_m > get_max_distance(hotels, "jarak_ke_pantai"):
                                match = False
                        if c == "location" and "kota" in slot_location.lower():
                            jarak_str = hotel.get("jarak_ke_pusat_kota", "999 km").replace(",", ".").strip()
                            jarak_m = convert_to_meters(jarak_str)
                            if jarak_m > get_max_distance(hotels, "jarak_ke_pusat_kota"):
                                match = False    
                        if c == "bed":
                            hotel_beds = [k["ranjang"].get("tipe", "").lower() for k in hotel.get("kamar", [])]
                            slot_bed_list = slot_bed if isinstance(slot_bed, list) else [slot_bed]
                            slot_bed_list = [b.lower() for b in slot_bed_list]
                            if not any(b in hotel_beds for b in slot_bed_list):
                                match = False
                    if match:
                        temp_filtered.append(hotel)
                if temp_filtered:
                    soft_filtered = temp_filtered
                    break  # ambil subset terbesar yang punya hasil
            if soft_filtered:
                break

        return [soft_filtered, True] if soft_filtered else [hotels, True]  # fallback terakhir ke semua hotel
    else:
        return [hard_filtered, False]


class ActionRecommendHotel(Action):

    def name(self) -> Text:
        return "action_recommend_hotel"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Load hotel data
        try:
            with open("data/hotel_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            dispatcher.utter_message(text="Maaf, data hotel tidak ditemukan.")
            return []

        hotels = data.get("hotel", [])
        user_text = tracker.latest_message.get("text")

        # ---- 1. Parsing preferences ----
        parsed_preferences = parse_preference_with_gemini(user_text)

        if DEBUG:
            print(f"parsed_preferences: {parsed_preferences}")  

        # Ambil slot dari tracker
        slot_price = parsed_preferences.get("price")
        slot_location = parsed_preferences.get("location")
        slot_type = parsed_preferences.get("type")
        slot_facility = parsed_preferences.get("facility")
        slot_bed = parsed_preferences.get("bed")
        slot_star = parsed_preferences.get("star")

        
        SlotSet("hotel", None)

        if (not any([slot_price, slot_location, slot_type, slot_facility, slot_bed, slot_star])):
            if (parsed_preferences.get("recommend")):
                dispatcher.utter_message(
                    text="Hotel seperti apa yang kamu inginkan? Misalnya murah, dekat pantai, kamar ukuran deluxe, atau punya restoran."
                )
                # chatbot menunggu jawaban user
                return [FollowupAction(name="action_listen")]
            else:
                return [FollowupAction(name="action_default_fallback")]

        # ---- 2. Ranking hotel (final weighted scoring) ----
        ranking = []  # simpan semua hasil skor

        # Hitung threshold otomatis dari semua harga kamar
        THRESHOLD_HARGA_GLOBAL = hitung_threshold_harga_kamar(data)

        # Hitung Jarak Otomatis
        MAX_JARAK_PANTAI = get_max_distance(hotels, "jarak_ke_pantai")
        MAX_JARAK_KOTA = get_max_distance(hotels, "jarak_ke_pusat_kota")

        # bobot default
        weight = {
            "harga": 0.25,
            "lokasi": 0.25,
            "tipe": 0.2,
            "fasilitas": 0.1,
            "rating": 0.1,
            "bed": 0.05,
            "star": 0.05
        }

        # boost dynamic berdasarkan slot user
        boost_factor = 1.5  # boost 50% untuk slot yang spesifik user sebut
        if slot_location:
            weight["lokasi"] *= boost_factor
        if slot_type:
            weight["tipe"] *= boost_factor
        if slot_facility:
            weight["fasilitas"] *= boost_factor
        if slot_price:
            weight["harga"] *= boost_factor
        if slot_bed:
            weight["bed"] *= boost_factor
        if slot_star:
            weight["star"] *= boost_factor

        # normalisasi total bobot supaya tetap 1
        total_w = sum(weight.values())
        for k in weight:
            weight[k] /= total_w

        # ---- Filter wajib (must-have) ----
        [filtered_hotels, isNotFound] = filter_hotels(hotels, parsed_preferences)

        for hotel in filtered_hotels:
            # ---- 1. Harga  ----
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

            # ---- 2. Lokasi ----
            score_lokasi = 0
            if slot_location:
                if "pantai" in slot_location.lower():
                    try:
                        jarak_str = hotel.get("jarak_ke_pantai", "0 km").replace(",", ".").strip()
                        jarak_m = convert_to_meters(jarak_str)
                        score_lokasi += max(0, 5 * (1 - jarak_m / MAX_JARAK_PANTAI))
                    except:
                        pass
                elif "kota" in slot_location.lower():
                    try:
                        jarak_str = hotel.get("jarak_ke_pusat_kota", "0 m").replace(",", ".").strip()
                        jarak_m = convert_to_meters(jarak_str)
                        score_lokasi += max(0, 2 * (1 - jarak_m / MAX_JARAK_KOTA))
                    except:
                        pass

            # ---- 3. Tipe kamar ----
            score_tipe = 0
            if slot_type:
                # pastikan slot_type selalu list
                if isinstance(slot_type, list):
                    slot_type_list = [s.lower() for s in slot_type]
                else:
                    slot_type_list = [slot_type.lower()]

                max_score = 0
                for kamar in hotel["kamar"]:
                    tipe_kamar = kamar.get("tipe", "").lower()
                    for tipe_user in slot_type_list:
                        similarity = fuzz.partial_ratio(tipe_user, tipe_kamar)
                        if similarity > max_score:
                            max_score = similarity

                # konversi similarity menjadi skor
                if max_score >= 90:
                    score_tipe += 3
                elif max_score >= 75:
                    score_tipe += 2
                elif max_score >= 50:
                    score_tipe += 1
                else:
                    score_tipe -= 1


            # ---- 4. Fasilitas (cumulative) ----
            score_fasilitas = 0
            if slot_facility:
                if isinstance(slot_facility, list):
                    facility_user_list = [f.lower() for f in slot_facility]
                else:
                    facility_user_list = [slot_facility.lower()]

                for f_usr in facility_user_list:
                    max_sim = 0
                    for f_hotel in hotel.get("fasilitas", []):
                        sim = fuzz.partial_ratio(f_usr, f_hotel.lower())
                        if sim > max_sim:
                            max_sim = sim
                    if max_sim >= 90:
                        score_fasilitas += 1.5
                    elif max_sim >= 75:
                        score_fasilitas += 1
                    elif max_sim >= 50:
                        score_fasilitas += 0.5

            # ---- 5. Rating / Sentiment ----
            score_rating = 0
            if "ulasan" in hotel and hotel["ulasan"]:
                total = 0
                for u in hotel["ulasan"]:
                    rating = u.get("rating", 0)
                    sentiment = u.get("sentiment", "neutral")
                    if sentiment == "positive":
                        total += 1
                    elif sentiment == "negative":
                        total -= 1
                    else:
                        total += 1
                score_rating += total / len(hotel["ulasan"])

            # ---- 6. Tipe bed/ranjang  ----
            score_bed = 0
            if slot_bed:
                if isinstance(slot_bed, list):
                    bed_user_list = [b.lower() for b in slot_bed]
                else:
                    bed_user_list = [slot_bed.lower()]

                for b_usr in bed_user_list:
                    max_sim = 0
                    for kamar in hotel["kamar"]:
                        sim = fuzz.partial_ratio(b_usr, kamar["ranjang"].get("tipe", "").lower())
                        if sim > max_sim:
                            max_sim = sim
                    if max_sim >= 90:
                        score_bed += 1.5
                    elif max_sim >= 75:
                        score_bed += 1
                    elif max_sim >= 50:
                        score_bed += 0.5

            # ---- 7. Bintang Hotel ----
            score_star = 0
            if slot_star:
                try:
                    # Ambil rata-rata star hotel
                    hotel_star = hotel.get("star", 0)
                    diff = abs(hotel_star - int(slot_star))
                    # semakin kecil diff → skor lebih tinggi
                    if diff == 0:
                        score_star = 2  # sangat cocok
                    elif diff == 1:
                        score_star = 1  # cukup cocok
                    else:
                        score_star = 0  # tidak cocok
                except:
                    pass

            # ---- 6. Total weighted score ----
            total_score = (
                score_harga * weight["harga"] +
                score_lokasi * weight["lokasi"] +
                score_tipe * weight["tipe"] +
                score_fasilitas * weight["fasilitas"] +
                score_rating * weight["rating"] +
                score_bed * weight["bed"] +
                score_star * weight["star"]
            )

            ranking.append((total_score, hotel))

        # ---- Sort & ambil top 3 ----
        ranking.sort(key=lambda x: x[0], reverse=True)
        top3 = ranking[:3]

        if not top3:
            dispatcher.utter_message(text="Maaf, saya tidak menemukan hotel sama sekali di database.")
            return [SlotSet("hotel", None)]
        
        # ---- Format hasil rekomendasi -----
        main_hotel_data = top3
        gpt_hotels_list = []
        gpt_alternatives_list = []
        
        if (ranking.__len__() > 3):
            alternative_hotels_data = ranking[3][1]
            gpt_alternatives_list.append({
                "nama": alternative_hotels_data.get("nama_hotel", "Hotel"),
                "rating": alternative_hotels_data.get("rating", 0),
                "tipe": alternative_hotels_data.get("tipe", "Hotel"),
                "bintang": alternative_hotels_data.get("star", 3),
                "harga": int(sum(k["harga"] for k in alternative_hotels_data["kamar"]) / len(alternative_hotels_data["kamar"])),
                "lokasi": alternative_hotels_data.get("alamat", "Bengkulu"), # Atau field lokasi spesifik
                "fasilitas": alternative_hotels_data.get("fasilitas", []),
                "link": alternative_hotels_data.get("link", {}).get("traveloka", "#")
            })
        else:
            alternative_hotels_data = []

        for h in main_hotel_data:
            h_data = h[1]
            gpt_hotels_list.append({
                "nama": h_data.get("nama_hotel", "Hotel"),
                "photo": h_data.get("photo", "http://localhost:3000/default_hotel.jpg"),
                "rating": h_data.get("rating", 0),
                "tipe": h_data.get("tipe", "Hotel"),
                "bintang": h_data.get("star", 3),
                "harga": int(sum(k["harga"] for k in h_data["kamar"]) / len(h_data["kamar"])),
                "lokasi": h_data.get("alamat", "Bengkulu"), # Atau field lokasi spesifik
                "fasilitas": h_data.get("fasilitas", []),
                "link": h_data.get("link", {}).get("traveloka", "#")
            })
            
        event = []
        if isNotFound:
            match_status = "fallback_recommendation"
            event.append(SlotSet("hotel", None))
        else:
            match_status = "exact_match"
            event.append(AllSlotsReset())
            event.append(SlotSet("hotel", main_hotel_data[0][1].get("nama_hotel", "").lower()))
            
        input_data_for_gpt = {
            "preference": user_text,
            "style": "structured_review",
            "match_status": match_status,
            "hotels": gpt_hotels_list,
            "alternatives": gpt_alternatives_list
        }
        
        gpt_response = generate_response_from_gpt(input_data_for_gpt)

        dispatcher.utter_message(text=gpt_response)
        return event

class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text="Maaf, saya tidak mengerti maksudmu. "
                 "Bisa dijelaskan lebih jelas supaya saya bisa bantu?"
        )
        
        return [AllSlotsReset()]

class ActionFacilityInfo(Action):

    def name(self) -> Text:
        return "action_facility_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        with open("data/hotel_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        slot_hotel = tracker.get_slot("hotel")
        slot_facility = tracker.get_slot("facility")
        hotels = data["hotel"]
        hotel = None
        
        intent = tracker.latest_message.get("intent", {}).get("name")
        
        if slot_hotel:
            hotel = next(
                (h for h in hotels if h.get("nama_hotel", "").lower() == slot_hotel.lower()),
                None
            )

        if not hotel:
            dispatcher.utter_message(text="Maaf, saya tidak tahu hotel mana yang kamu maksud.")
            return []
        
        facility = [f.lower() for f in hotel.get("fasilitas", [])]

        # ==== Bedakan jenis intent ====
        if intent == "ask_facility_specific" and slot_facility:
            user_facility = slot_facility.lower()
            close = get_close_matches(user_facility, facility, n=3, cutoff=0.5)
            if close:
                dispatcher.utter_message(
                    text=f"Iya, *{hotel['nama_hotel']}* punya fasilitas {user_facility}. "
                         f"Selain itu, juga ada fasilitas lain seperti {', '.join(facility)}."
                )
            else:
                dispatcher.utter_message(
                    text=f"Sepertinya *{hotel['nama_hotel']}* tidak memiliki fasilitas {user_facility}. "
                         f"Namun tersedia fasilitas lain seperti {', '.join(facility)}."
                )
        else:
            dispatcher.utter_message(
                text=f"Fasilitas yang tersedia di *{hotel['nama_hotel']}* antara lain: {', '.join(facility)}."
            )

        return [SlotSet("facility", None)]


class ActionLocationInfo(Action):

    def name(self) -> Text:
        return "action_location_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        with open("data/hotel_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        slot_hotel = tracker.get_slot("hotel")
        hotels = data["hotel"]
        hotel = None
        
        if slot_hotel:
            hotel = next(
                (h for h in hotels if h.get("nama_hotel", "").lower() == slot_hotel.lower()),
                None
            )

        if hotel:
            alamat = hotel.get("alamat", "tidak tersedia")
            jarak_kota = hotel.get("jarak_ke_pusat_kota", "tidak tersedia")
            jarak_pantai = hotel.get("jarak_ke_pantai", "tidak tersedia")
            dispatcher.utter_message(
                text=f"*{hotel['nama_hotel']}* berada di: {alamat}\nJarak ke pusat kota: {jarak_kota}\nJarak ke pantai: {jarak_pantai}"
            )
        else:
            dispatcher.utter_message(text="Maaf, hotel yang mana?")

        return []
