import math

def hitung_jarak(lat1, lon1, lat2, lon2):
    """Hitung jarak Haversine (meter)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def dalam_radius(lat_user, lon_user, lat_target, lon_target, radius_meter=100):
    """Cek apakah user ada dalam radius"""
    jarak = hitung_jarak(lat_user, lon_user, lat_target, lon_target)
    return jarak <= radius_meter, jarak
