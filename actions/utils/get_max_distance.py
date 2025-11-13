from actions.utils.convert_km_to_meter import convert_to_meters


def get_max_distance(data, field_name):
    distances = []
    for h in data:
        val = h.get(field_name)
        if val:
            try:
                val = val.replace(",", ".").strip()
                distances.append(convert_to_meters(val))
            except:
                pass
    return max(distances) if distances else 5000