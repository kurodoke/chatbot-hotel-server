from difflib import get_close_matches
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import json
from rasa_sdk.events import FollowupAction, AllSlotsReset, SlotSet

from actions.utils.get_max_distance import get_max_distance
from actions.utils.convert_km_to_meter import convert_to_meters
from actions.utils.threshold_price_room import hitung_threshold_harga_kamar
from rapidfuzz import fuzz

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

        # Ambil slot dari tracker
        slot_price = tracker.get_slot("price")
        slot_location = tracker.get_slot("location")
        slot_type = tracker.get_slot("type")
        slot_facility = tracker.get_slot("facility")
        slot_bed = tracker.get_slot("bed")
        slot_star = tracker.get_slot("star")
        
        SlotSet("hotel", None)

        user_message = tracker.latest_message.get("text", "")

        # ---- 1. Cek apakah preferensi jelas ----
        if not any([slot_price, slot_location, slot_type, slot_facility]):
            if any(word in user_message for word in ["hotel", "berikan", "rekomendasikan", "rekomendasi", "cari", "temukan", "carikan", "tampilkan"]):
                dispatcher.utter_message(
                    text="Hotel seperti apa yang kamu inginkan? Misalnya murah, dekat pantai, atau punya restoran."
                )
                # chatbot menunggu jawaban user
                return [FollowupAction(name="action_listen")]
            else:
                return [FollowupAction(name="action_default_fallback")]

        # ---- 2. Ranking hotel ----
        best_hotel = None
        best_score = -9999

        # Hitung threshold otomatis dari semua harga kamar
        THRESHOLD_HARGA_GLOBAL = hitung_threshold_harga_kamar(data)
        
        # Hitung Jarak Otomatis
        MAX_JARAK_PANTAI = get_max_distance(hotels, "jarak_ke_pantai")
        MAX_JARAK_KOTA = get_max_distance(hotels, "jarak_ke_pusat_kota")

        for hotel in hotels:
            score = 0

            if slot_price:
                try:
                    harga_rata2 = sum(k["harga"] for k in hotel["kamar"]) / len(hotel["kamar"])
                except ZeroDivisionError:
                    harga_rata2 = 0  # kalau hotel tidak punya data kamar

                if slot_price.lower() == "murah":
                    # semakin di bawah rata-rata global, skor makin tinggi
                    score += max(0, THRESHOLD_HARGA_GLOBAL - harga_rata2) / 100000

                elif slot_price.lower() == "mahal":
                    # semakin di atas rata-rata global, skor makin tinggi
                    score += max(0, harga_rata2 - THRESHOLD_HARGA_GLOBAL) / 100000

                else:
                    dispatcher.utter_message("Maaf, kamu ingin hotel dengan harga murah atau mahal?")
                    return [FollowupAction(name="action_listen")]

            if slot_location:
                if "pantai" in slot_location.lower():
                    try:
                        jarak_str = hotel.get("jarak_ke_pantai", "0 km").replace(",", ".").strip()
                        jarak_m = convert_to_meters(jarak_str)
                        score += max(0, 5 * (1 - (jarak_m / MAX_JARAK_PANTAI)))
                    except Exception as e:
                        print(f"Error hitung jarak pantai: {e}")

                elif "kota" in slot_location.lower():
                    try:
                        jarak_str = hotel.get("jarak_ke_pusat_kota", "0 m").replace(",", ".").strip()
                        jarak_m = convert_to_meters(jarak_str)
                        score += max(0, 2 * (1 - (jarak_m / MAX_JARAK_KOTA)))
                    except Exception as e:
                        print(f"Error hitung jarak kota: {e}")

            # Tipe kamar
            if slot_type:
                tipe_user = slot_type.lower()
                max_score = 0

                for kamar in hotel["kamar"]:
                    tipe_kamar = kamar["tipe"].lower()
                    # hitung similarity
                    similarity = fuzz.partial_ratio(tipe_user, tipe_kamar)
                    if similarity > max_score:
                        max_score = similarity

                # konversi similarity menjadi skor
                if max_score >= 90:
                    score += 3  # sangat cocok
                elif max_score >= 75:
                    score += 2  # cukup cocok
                elif max_score >= 50:
                    score += 1  # kurang cocok
                else:
                    score -= 1  # tidak cocok

            # Fitur lain / facility
            if slot_facility:
                facility_user = slot_facility.lower()
                max_similarity = 0

                for f in hotel.get("fasilitas", []):
                    similarity = fuzz.partial_ratio(facility_user, f.lower())
                    if similarity > max_similarity:
                        max_similarity = similarity

                # konversi similarity menjadi skor
                if max_similarity >= 90:
                    score += 1.5  # sangat cocok
                elif max_similarity >= 75:
                    score += 1  # cukup cocok
                elif max_similarity >= 50:
                    score += 0.5  # kurang cocok

            # Rating & sentiment
            if "ulasan" in hotel and hotel["ulasan"]:
                try:
                    total = 0
                    for u in hotel["ulasan"]:
                        rating = u.get("rating", 0)
                        sentiment = u.get("sentiment", "neutral")

                        if sentiment == "positive":
                            total += rating
                        elif sentiment == "negative":
                            total -= rating
                        else:
                            total += rating * 0.5  # netral

                    score += total / len(hotel["ulasan"])
                except Exception as e:
                    print(f"Error hitung ulasan: {e}")


            if score > best_score:
                best_score = score
                best_hotel = hotel

        # ---- 3. Hasil rekomendasi ----
        event = []
        if best_hotel:
            nama = best_hotel.get("nama_hotel", "Nama tidak tersedia")
            alamat = best_hotel.get("alamat", "Alamat tidak tersedia")
            link = best_hotel.get("link", {}).get("traveloka", "#")
            dispatcher.utter_message(
                text=f"✨ Rekomendasi terbaik untuk kamu: *{nama}*.\n"
                     f"📍 Alamat: {alamat}\n"
                     f"🔗 Link: {link}"
            )
            event.append(AllSlotsReset())
            event.append(SlotSet("hotel", best_hotel.get("nama_hotel", None).lower()))
        else:
            dispatcher.utter_message(
                text="Maaf, saya belum menemukan hotel yang sesuai preferensimu."
            )
            event.append(SlotSet("hotel", None))

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
