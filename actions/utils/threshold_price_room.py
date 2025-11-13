def hitung_threshold_harga_kamar(data):
    semua_harga = [
        kamar["harga"]
        for h in data.get("hotel", [])
        for kamar in h.get("kamar", [])
        if "harga" in kamar
    ]
    
    return sum(semua_harga) / len(semua_harga) if semua_harga else 500000


