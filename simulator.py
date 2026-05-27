"""
simulator.py — Simülasyon motoru
Aktivite tanımları, sabitler, dağılım modelleri,
biyometrik hesaplamalar, geçmiş veri üretimi,
anomali/uyarı mantığı ve simülasyon döngüsü.
"""
import random, math, time
from datetime import datetime, timedelta
from db import get_db, db_get_distribution_settings, db_get_pattern_dist_settings

# ── SABİTLER ──────────────────────────────────────────────────────────────────

ACTIVITIES = [
    {"name": "Uyuyor",              "name_en": "Sleeping",        "icon": "😴", "color": "#85B7EB",
     "type": "sleep",  "cal_rate": 1.0,  "step_rate": 0,
     "hr_base": 55,  "hr_noise": 5,  "spo2_base": 97, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",       "dur_min": 360, "dur_max": 540},
    {"name": "Kahvaltı yapıyor",    "name_en": "Having breakfast","icon": "🍳", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 8.0,  "step_rate": 0,
     "hr_base": 72,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",       "dur_min": 20,  "dur_max": 40},
    {"name": "Egzersiz yapıyor",    "name_en": "Exercising",      "icon": "🏃", "color": "#534AB7",
     "type": "active", "cal_rate": 9.5,  "step_rate": 20,
     "hr_base": 145, "hr_noise": 15, "spo2_base": 96, "skin_temp": 37.4,
     "mood": "enerjik",     "location": "dışarı",   "dur_min": 30,  "dur_max": 60},
    {"name": "Çalışıyor",           "name_en": "Working",         "icon": "💻", "color": "#534AB7",
     "type": "active", "cal_rate": 2.2,  "step_rate": 0,
     "hr_base": 78,  "hr_noise": 6,  "spo2_base": 98, "skin_temp": 36.4,
     "mood": "odaklanmış",  "location": "ofis",     "dur_min": 60,  "dur_max": 180},
    {"name": "Televizyon izliyor",  "name_en": "Watching TV",     "icon": "📺", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.2,  "step_rate": 0,
     "hr_base": 65,  "hr_noise": 5,  "spo2_base": 98, "skin_temp": 36.3,
     "mood": "rahat",       "location": "ev",       "dur_min": 30,  "dur_max": 120},
    {"name": "Yemek yiyor",         "name_en": "Eating",          "icon": "🍽️", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 7.0,  "step_rate": 0,
     "hr_base": 75,  "hr_noise": 7,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",       "dur_min": 20,  "dur_max": 45},
    {"name": "Yürüyüşe çıkıyor",    "name_en": "Walking outside", "icon": "🚶", "color": "#534AB7",
     "type": "active", "cal_rate": 5.0,  "step_rate": 13,
     "hr_base": 95,  "hr_noise": 10, "spo2_base": 98, "skin_temp": 36.7,
     "mood": "keyifli",     "location": "dışarı",   "dur_min": 20,  "dur_max": 60},
    {"name": "Okuyuyor",            "name_en": "Reading",         "icon": "📖", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.1,  "step_rate": 0,
     "hr_base": 63,  "hr_noise": 4,  "spo2_base": 99, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",       "dur_min": 20,  "dur_max": 60},
    {"name": "Telefonda konuşuyor", "name_en": "On the phone",    "icon": "📱", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.3,  "step_rate": 2,
     "hr_base": 80,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.4,
     "mood": "meşgul",      "location": "ev",       "dur_min": 10,  "dur_max": 30},
    {"name": "Alışverişe gidiyor",  "name_en": "Shopping",        "icon": "🛍️", "color": "#534AB7",
     "type": "active", "cal_rate": 4.0,  "step_rate": 9,
     "hr_base": 90,  "hr_noise": 10, "spo2_base": 98, "skin_temp": 36.6,
     "mood": "keyifli",     "location": "dışarı",   "dur_min": 30,  "dur_max": 90},
    {"name": "Dinleniyor",          "name_en": "Resting",         "icon": "🛋️", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.0,  "step_rate": 0,
     "hr_base": 62,  "hr_noise": 4,  "spo2_base": 99, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",       "dur_min": 15,  "dur_max": 45},
    {"name": "Pişiriyor",           "name_en": "Cooking",         "icon": "👨‍🍳", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 3.0,  "step_rate": 3,
     "hr_base": 82,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",       "dur_min": 20,  "dur_max": 45},
    {"name": "Meditasyon yapıyor",  "name_en": "Meditating",      "icon": "🧘", "color": "#9FE1CB",
     "type": "rest",   "cal_rate": 0.9,  "step_rate": 0,
     "hr_base": 58,  "hr_noise": 3,  "spo2_base": 99, "skin_temp": 36.1,
     "mood": "huzurlu",     "location": "ev",       "dur_min": 15,  "dur_max": 40},
    {"name": "Bisiklet sürüyor",    "name_en": "Cycling",         "icon": "🚴", "color": "#534AB7",
     "type": "active", "cal_rate": 8.5,  "step_rate": 5,
     "hr_base": 135, "hr_noise": 18, "spo2_base": 96, "skin_temp": 37.2,
     "mood": "enerjik",     "location": "dışarı",   "dur_min": 30,  "dur_max": 75},
    {"name": "Dans ediyor",         "name_en": "Dancing",         "icon": "💃", "color": "#F4C0D1",
     "type": "active", "cal_rate": 7.0,  "step_rate": 10,
     "hr_base": 120, "hr_noise": 15, "spo2_base": 97, "skin_temp": 37.1,
     "mood": "neşeli",      "location": "ev",       "dur_min": 20,  "dur_max": 45},
    {"name": "Yoga yapıyor",        "name_en": "Doing yoga",      "icon": "🤸", "color": "#9FE1CB",
     "type": "active", "cal_rate": 4.0,  "step_rate": 1,
     "hr_base": 80,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.6,
     "mood": "huzurlu",     "location": "ev",       "dur_min": 20,  "dur_max": 50},
]

ANOMALY_RULES = [
    {"metric": "heart_rate",   "threshold": 160,  "direction": "above", "severity": "critical",
     "message_tr": "Kalp atışı kritik seviyede yüksek", "message_en": "Heart rate critically high"},
    {"metric": "heart_rate",   "threshold": 45,   "direction": "below", "severity": "warning",
     "message_tr": "Kalp atışı çok düşük",             "message_en": "Heart rate too low"},
    {"metric": "spo2",         "threshold": 93,   "direction": "below", "severity": "critical",
     "message_tr": "Oksijen doygunluğu düşük",         "message_en": "Oxygen saturation low"},
    {"metric": "skin_temp",    "threshold": 38.0, "direction": "above", "severity": "warning",
     "message_tr": "Vücut sıcaklığı yüksek (ateş?)",  "message_en": "Body temperature elevated"},
    {"metric": "steps",        "threshold": 15000,"direction": "above", "severity": "info",
     "message_tr": "Adım sayısı çok yüksek",           "message_en": "Step count too high"},
    {"metric": "calories",     "threshold": 3500, "direction": "above", "severity": "info",
     "message_tr": "Kalori tüketimi çok yüksek",       "message_en": "Calorie intake too high"},
    {"metric": "active_mins",  "threshold": 200,  "direction": "above", "severity": "warning",
     "message_tr": "Aktif süre çok uzun",              "message_en": "Active duration too long"},
    {"metric": "active_mins",  "threshold": 10,   "direction": "below", "severity": "info",
     "message_tr": "Gün boyu hareketsiz",              "message_en": "Inactive all day"},
    {"metric": "screen_mins",  "threshold": 300,  "direction": "above", "severity": "info",
     "message_tr": "Ekran süresi çok fazla",           "message_en": "Too much screen time"},
    {"metric": "stress_level", "threshold": 80,   "direction": "above", "severity": "warning",
     "message_tr": "Stres seviyesi çok yüksek",        "message_en": "Stress level very high"},
    {"metric": "hrv",          "threshold": 15,   "direction": "below", "severity": "warning",
     "message_tr": "Kalp ritmi değişkenliği düşük",    "message_en": "Low heart rate variability"},
]

AVATAR_COLORS = ["#CECBF6","#9FE1CB","#F5C4B3","#F4C0D1","#B5D4F4","#C0DD97","#FAC775","#F7C1C1"]

LOCATIONS = {
    "ev":     {"lat_base": 41.015, "lng_base": 28.979},
    "ofis":   {"lat_base": 41.042, "lng_base": 28.986},
    "dışarı": {"lat_base": 41.025, "lng_base": 28.975},
}

# Şehir bazlı koordinat merkezleri
CITY_COORDS = {
    "istanbul":   {"lat": 41.015, "lng": 28.979},
    "ankara":     {"lat": 39.925, "lng": 32.866},
    "izmir":      {"lat": 38.423, "lng": 27.143},
    "bursa":      {"lat": 40.183, "lng": 29.067},
    "antalya":    {"lat": 36.897, "lng": 30.713},
    "adana":      {"lat": 37.001, "lng": 35.321},
    "konya":      {"lat": 37.874, "lng": 32.493},
    "gaziantep":  {"lat": 37.066, "lng": 37.383},
    "mersin":     {"lat": 36.812, "lng": 34.641},
    "kayseri":    {"lat": 38.732, "lng": 35.487},
    "eskişehir":  {"lat": 39.776, "lng": 30.521},
    "diyarbakir": {"lat": 37.925, "lng": 40.208},
    "diyarbakır": {"lat": 37.925, "lng": 40.208},
    "samsun":     {"lat": 41.286, "lng": 36.330},
    "denizli":    {"lat": 37.774, "lng": 29.086},
    "trabzon":    {"lat": 41.003, "lng": 39.716},
    "bolu":       {"lat": 40.576, "lng": 31.588},
    "sakarya":    {"lat": 40.692, "lng": 30.434},
    "kocaeli":    {"lat": 40.765, "lng": 29.940},
    "tekirdag":   {"lat": 40.978, "lng": 27.515},
    "tekirdağ":   {"lat": 40.978, "lng": 27.515},
    "manisa":     {"lat": 38.614, "lng": 27.426},
    "balikesir":  {"lat": 39.649, "lng": 27.889},
    "balıkesir":  {"lat": 39.649, "lng": 27.889},
    "malatya":    {"lat": 38.355, "lng": 38.309},
    "erzurum":    {"lat": 39.905, "lng": 41.267},
}

def get_city_base(city: str, location_type: str) -> dict:
    """Kişinin şehrine göre konum merkezini döndürür."""
    key = city.strip().lower() if city else ""
    # Türkçe karakter normalize
    key = key.replace("ı","i").replace("ğ","g").replace("ü","u").replace("ş","s").replace("ö","o").replace("ç","c")
    city_center = CITY_COORDS.get(key) or CITY_COORDS.get(city.strip().lower(), CITY_COORDS["istanbul"])
    offsets = {
        "ev":     {"dlat":  0.000, "dlng":  0.000},
        "ofis":   {"dlat":  0.012, "dlng":  0.018},
        "dışarı": {"dlat":  0.006, "dlng": -0.005},
    }
    off = offsets.get(location_type, {"dlat": 0, "dlng": 0})
    return {"lat_base": city_center["lat"] + off["dlat"],
            "lng_base": city_center["lng"] + off["dlng"]}

WEATHER_CONDITIONS = [
    {"condition": "Güneşli",         "condition_en": "Sunny",        "icon": "☀️",  "temp_range": (20, 32)},
    {"condition": "Parçalı bulutlu", "condition_en": "Partly cloudy","icon": "⛅",  "temp_range": (18, 27)},
    {"condition": "Bulutlu",         "condition_en": "Cloudy",       "icon": "☁️",  "temp_range": (15, 22)},
    {"condition": "Yağmurlu",        "condition_en": "Rainy",        "icon": "🌧️", "temp_range": (12, 18)},
    {"condition": "Rüzgarlı",        "condition_en": "Windy",        "icon": "💨",  "temp_range": (10, 20)},
]

# Global simülasyon durumu
current_weather      = random.choice(WEATHER_CONDITIONS)
current_temp         = random.uniform(*current_weather["temp_range"])
weather_tick         = 0
sim_speed            = 1
activity_start_times = {}


# ── DAĞILIM MODELLERİ ─────────────────────────────────────────────────────────

def sample_distribution(dist_name, params, min_v=None, max_v=None):
    """
    Seçilen istatistiksel dağılımdan örnek üret.

    Desteklenen dağılımlar:
      normal      : mean, std
      uniform     : low, high
      exponential : scale, offset
      poisson     : lam
      lognormal   : mean, sigma
      triangular  : low, mode, high
      beta        : alpha, beta, scale
    """
    try:
        d = dist_name.lower()
        if d == "normal":
            v = random.gauss(params.get("mean", 75), params.get("std", 10))
        elif d == "uniform":
            v = random.uniform(params.get("low", 60), params.get("high", 90))
        elif d == "exponential":
            scale = params.get("scale", 20)
            v = random.expovariate(1.0 / max(scale, 0.001)) + params.get("offset", 0)
        elif d == "poisson":
            lam = params.get("lam", 5)
            L, k, p = math.exp(-lam), 0, 1.0
            while p > L:
                k += 1; p *= random.random()
            v = float(k - 1)
        elif d == "lognormal":
            v = random.lognormvariate(params.get("mean", 4.3), params.get("sigma", 0.5))
        elif d == "triangular":
            v = random.triangular(params.get("low", 0), params.get("high", 100), params.get("mode", 50))
        elif d == "beta":
            v = random.betavariate(params.get("alpha", 2), params.get("beta", 5)) * params.get("scale", 100)
        else:
            v = random.gauss(params.get("mean", 75), params.get("std", 10))
    except:
        v = params.get("mean", 75) + random.gauss(0, params.get("std", 10))
    if min_v is not None: v = max(min_v, v)
    if max_v is not None: v = min(max_v, v)
    return v


# Dağılım cache'leri
_dist_cache = {}
_dist_cache_time = 0
_pattern_dist_cache = {}
_pattern_dist_cache_time = 0


def get_dist_settings_cached():
    """Simülasyon dağılım ayarlarını önbellekten döndür (60 sn)."""
    global _dist_cache, _dist_cache_time
    now_t = time.time()
    if now_t - _dist_cache_time > 60:
        _dist_cache = db_get_distribution_settings()
        _dist_cache_time = now_t
    return _dist_cache


def get_pattern_dist_cached():
    """Örüntü analizi dağılım ayarlarını önbellekten döndür (60 sn)."""
    global _pattern_dist_cache, _pattern_dist_cache_time
    now_t = time.time()
    if now_t - _pattern_dist_cache_time > 60:
        _pattern_dist_cache = db_get_pattern_dist_settings()
        _pattern_dist_cache_time = now_t
    return _pattern_dist_cache


def invalidate_dist_cache():
    global _dist_cache_time; _dist_cache_time = 0

def invalidate_pattern_dist_cache():
    global _pattern_dist_cache_time; _pattern_dist_cache_time = 0


# ── BİYOMETRİK HESAPLAMALAR ───────────────────────────────────────────────────

def smooth(old, new, alpha=0.3):
    """Üstel hareketli ortalama (EMA) ile yumuşatma."""
    return old + alpha * (new - old)


def noisy(base, noise, min_v=None, max_v=None):
    """Gaussian gürültü ekle."""
    v = base + random.gauss(0, noise)
    if min_v is not None: v = max(min_v, v)
    if max_v is not None: v = min(max_v, v)
    return v


def compute_hrv(hr, stress):
    """Nabız ve stres değerinden HRV tahmin et."""
    base = 70 - (stress * 0.5) - (abs(hr - 65) * 0.3)
    return max(8, min(95, int(noisy(base, 6))))


def compute_health_score(sleep_mins, active_mins, avg_stress, avg_hr, spo2):
    """Günlük sağlık skoru (0-100)."""
    sleep_h      = sleep_mins / 60
    sleep_score  = 30 if 7 <= sleep_h <= 9 else (20 if 6 <= sleep_h < 7 else (10 if sleep_h > 0 else 0))
    active_score = 25 if active_mins >= 30 else int((active_mins / 30) * 25)
    stress_score = int((1 - min(avg_stress, 100) / 100) * 20)
    hr_score     = 15 if 60 <= avg_hr <= 100 else (8 if avg_hr > 0 else 0)
    spo2_score   = 10 if spo2 >= 96 else (5 if spo2 >= 93 else 0)
    return min(100, sleep_score + active_score + stress_score + hr_score + spo2_score)


def jitter_location(base_lat, base_lng, activity_type):
    """Aktivite tipine göre GPS koordinatı jitter ekle."""
    radius = 0.005 if activity_type == "active" else (0.0005 if activity_type in ["rest","sleep","meal"] else 0.001)
    angle  = random.uniform(0, 2 * math.pi)
    dist   = random.uniform(0, radius)
    return base_lat + dist * math.cos(angle), base_lng + dist * math.sin(angle)


# ── MARKOV GEÇİŞ SİSTEMİ ────────────────────────────────────────────────────

# Saat bloğu: 0-5=gece, 6-8=sabah, 8-12=öğleden önce, 12-14=öğle,
#             14-18=öğleden sonra, 18-21=akşam, 21-23=gece
def _hour_block(hour):
    if hour < 6:   return 0
    if hour < 8:   return 1
    if hour < 12:  return 2
    if hour < 14:  return 3
    if hour < 18:  return 4
    if hour < 21:  return 5
    return 6


def build_markov_matrix(conn, pid):
    """
    Kişinin aktivite geçmişinden Markov geçiş matrisini öğren ve veritabanına kaydet.
    Her (kaynak_aktivite, saat_bloğu) çifti için hedef aktivite olasılıklarını hesaplar.
    En az 10 kayıt varsa çalışır.
    """
    c = conn.cursor()
    rows = c.execute("""
        SELECT activity_name, start_time FROM activity_log
        WHERE person_id=? ORDER BY start_time ASC
    """, (pid,)).fetchall()

    if len(rows) < 10:
        return False  # Yeterli veri yok

    # Geçiş sayılarını say
    counts = {}  # {(from_act, to_act, hour_block): count}
    for i in range(len(rows) - 1):
        from_act = rows[i]["activity_name"]
        to_act   = rows[i+1]["activity_name"]
        try:
            dt    = datetime.fromisoformat(rows[i+1]["start_time"])
            hb    = _hour_block(dt.hour)
        except:
            continue
        key = (from_act, to_act, hb)
        counts[key] = counts.get(key, 0) + 1

    if not counts:
        return False

    # Toplam sayıları hesapla (normalleştirme için)
    totals = {}  # {(from_act, hour_block): total_count}
    for (from_act, to_act, hb), cnt in counts.items():
        key = (from_act, hb)
        totals[key] = totals.get(key, 0) + cnt

    # Veritabanına yaz
    now_iso = datetime.now().isoformat()
    for (from_act, to_act, hb), cnt in counts.items():
        total = totals.get((from_act, hb), 1)
        prob  = round(cnt / total, 4)
        c.execute("""
            INSERT INTO markov_transitions
                (person_id, from_activity, to_activity, hour_block, count, probability, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(person_id, from_activity, to_activity, hour_block) DO UPDATE SET
                count=excluded.count,
                probability=excluded.probability,
                updated_at=excluded.updated_at
        """, (pid, from_act, to_act, hb, cnt, prob, now_iso))

    conn.commit()
    return True


def get_markov_matrix(conn, pid):
    """
    Kişinin Markov geçiş matrisini veritabanından oku.
    {(from_activity, hour_block): [(to_activity, probability), ...]} formatında döner.
    """
    rows = conn.execute("""
        SELECT from_activity, to_activity, hour_block, probability
        FROM markov_transitions WHERE person_id=?
        ORDER BY from_activity, hour_block, probability DESC
    """, (pid,)).fetchall()

    matrix = {}
    for r in rows:
        key = (r["from_activity"], r["hour_block"])
        if key not in matrix:
            matrix[key] = []
        matrix[key].append((r["to_activity"], r["probability"]))
    return matrix


# Markov matrisi cache — pid → {matrix, timestamp}
_markov_cache = {}


def get_markov_cached(conn, pid):
    """Markov matrisini önbellekten getir (5 dk cache)."""
    now_t = time.time()
    if pid in _markov_cache and now_t - _markov_cache[pid]["ts"] < 300:
        return _markov_cache[pid]["matrix"]

    # Matris yoksa veya eski ise yeniden oluştur
    matrix = get_markov_matrix(conn, pid)
    if not matrix:
        build_markov_matrix(conn, pid)
        matrix = get_markov_matrix(conn, pid)

    _markov_cache[pid] = {"matrix": matrix, "ts": now_t}
    return matrix


def invalidate_markov_cache(pid=None):
    """Markov cache'ini temizle."""
    global _markov_cache
    if pid:
        _markov_cache.pop(pid, None)
    else:
        _markov_cache.clear()


def pick_activity_markov(pid, prev_activity_name, hour, conn):
    """
    Markov geçiş matrisine göre sonraki aktiviteyi seç.
    Matris yoksa veya geçiş bulunamazsa klasik saat bazlı seçime düşer.

    Hibrit yaklaşım:
    - %70 Markov olasılıklarına göre
    - %30 saat bazlı kurallara göre
    Bu karışım hem öğrenilmiş alışkanlıkları hem de saat gerçekçiliğini korur.
    """
    MARKOV_WEIGHT = 0.70

    if not prev_activity_name or random.random() > MARKOV_WEIGHT:
        return pick_activity_for_hour(hour)

    matrix = get_markov_cached(conn, pid)
    hb     = _hour_block(hour)
    key    = (prev_activity_name, hb)

    # Önce tam eşleşme dene (aktivite + saat bloğu)
    candidates = matrix.get(key, [])

    # Yoksa sadece aktiviteye bak (tüm saat blokları)
    if not candidates:
        all_keys = [k for k in matrix if k[0] == prev_activity_name]
        merged = {}
        for k in all_keys:
            for act, prob in matrix[k]:
                merged[act] = merged.get(act, 0) + prob
        total = sum(merged.values())
        if total > 0:
            candidates = [(act, p/total) for act, p in merged.items()]

    if not candidates:
        return pick_activity_for_hour(hour)

    # Saat uyumluluğu kontrolü — geceleri uyku dışı aktiviteye geçiş engelle
    hour_pool = {a["name"] for a in ACTIVITIES
                 if not (hour >= 23 or hour < 6) or a["type"] == "sleep"}

    # Ağırlıklı rastgele seçim
    valid = [(act, p) for act, p in candidates if act in hour_pool]
    if not valid:
        return pick_activity_for_hour(hour)

    total_w = sum(p for _, p in valid)
    if total_w == 0:
        return pick_activity_for_hour(hour)

    r, cumul = random.uniform(0, total_w), 0
    for act_name, prob in valid:
        cumul += prob
        if r <= cumul:
            act_obj = next((a for a in ACTIVITIES if a["name"] == act_name), None)
            if act_obj:
                return act_obj

    return pick_activity_for_hour(hour)


def pick_activity_for_hour(hour, prev_type=None):
    """Saat bazlı gerçekçi aktivite seçimi."""
    if hour >= 23 or hour < 6:
        return next(a for a in ACTIVITIES if a["type"] == "sleep")
    if 6 <= hour < 8:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Having breakfast","Doing yoga","Exercising","Meditating"]]
    elif 8 <= hour < 12:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Working","Exercising","Walking outside","Cycling"]]
    elif 12 <= hour < 14:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Eating","Having breakfast","Walking outside"]]
    elif 14 <= hour < 18:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Working","Reading","On the phone","Shopping","Walking outside"]]
    elif 18 <= hour < 21:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Eating","Walking outside","Exercising","Dancing","Cooking"]]
    else:
        pool = [a for a in ACTIVITIES if a["name_en"] in ["Watching TV","Reading","Meditating","Resting","On the phone"]]
    if not pool:
        pool = [a for a in ACTIVITIES if a["type"] != "sleep"]
    if prev_type and len(pool) > 1:
        diff = [a for a in pool if a["type"] != prev_type]
        if diff and random.random() < 0.6:
            pool = diff
    weights = [1.3 if a["type"] == "active" else 1.0 for a in pool]
    r, cumul = random.uniform(0, sum(weights)), 0
    for a, w in zip(pool, weights):
        cumul += w
        if r <= cumul:
            return a
    return random.choice(pool)


# ── GEÇMİŞ VERİ ÜRETİMİ ──────────────────────────────────────────────────────

def seed_historical_data(conn, pid, days_back=14):
    """Kişi için son N günün aktivite ve sensör verilerini üret. Zaten veri varsa atlar."""
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) as n FROM activity_log WHERE person_id=?", (pid,)).fetchone()["n"] > 0:
        return
    print(f"  Kişi {pid} için {days_back} günlük geçmiş veri üretiliyor...")
    sleep_hour_base = random.uniform(22.0, 24.0)
    wake_hour_base  = random.uniform(6.0, 8.5)
    now = datetime.now()
    for day_offset in range(days_back - 1, -1, -1):
        day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        weekday   = day_start.weekday()
        sleep_start_hour = max(21, min(25, sleep_hour_base + random.gauss(0, 0.4)))
        wake_hour        = max(5.5, min(9.0, wake_hour_base + random.gauss(0, 0.3)))
        sl_start = day_start - timedelta(hours=24 - sleep_start_hour % 24)
        sl_dur   = max(240, min(600, int((wake_hour + (24 - sleep_start_hour % 24)) * 60)))
        sl_end   = sl_start + timedelta(minutes=sl_dur)
        sl_act   = next(a for a in ACTIVITIES if a["type"] == "sleep")
        sl_hr    = int(noisy(sl_act["hr_base"], sl_act["hr_noise"], 40, 75))
        c.execute("""INSERT INTO activity_log
            (person_id,activity_name,activity_name_en,activity_icon,activity_type,
             start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, sl_act["name"], sl_act["name_en"], sl_act["icon"], sl_act["type"],
             sl_start.isoformat(), sl_end.isoformat(), sl_dur,
             0, round(sl_dur * sl_act["cal_rate"], 1), sl_hr, sl_end.isoformat()))
        t_cur = sl_start
        while t_cur < sl_end:
            c.execute("""INSERT INTO sensor_log
                (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, int(noisy(sl_act["hr_base"], sl_act["hr_noise"], 40, 75)),
                 round(noisy(sl_act["spo2_base"], 0.3, 90, 100), 1),
                 round(noisy(sl_act["skin_temp"], 0.1, 35, 38), 2),
                 compute_hrv(sl_hr, 10), random.randint(5, 15), 0, 0,
                 sl_act["name"], sl_act["type"], t_cur.isoformat()))
            t_cur += timedelta(minutes=30)
        cursor_time = sl_end + timedelta(minutes=random.randint(5, 15))
        cumul_steps, cumul_cal = 0, sl_dur * sl_act["cal_rate"]
        prev_type = "sleep"
        day_end   = day_start.replace(hour=22, minute=30)
        while cursor_time < day_end:
            act = pick_activity_for_hour(cursor_time.hour, prev_type)
            dur = random.randint(act["dur_min"], act["dur_max"])
            if weekday >= 5 and act["type"] in ["rest", "sleep"]:
                dur = int(dur * 1.3)
            end_time = cursor_time + timedelta(minutes=dur)
            if end_time > day_end:
                dur = max(5, int((day_end - cursor_time).seconds / 60))
                end_time = day_end
            hr_avg = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
            steps  = int(act["step_rate"] * dur * (0.85 + random.random() * 0.3))
            cal    = round(act["cal_rate"] * dur * (0.85 + random.random() * 0.3), 1)
            cumul_steps += steps; cumul_cal += cal
            c.execute("""INSERT INTO activity_log
                (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                 start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, act["name"], act["name_en"], act["icon"], act["type"],
                 cursor_time.isoformat(), end_time.isoformat(), dur,
                 cumul_steps, round(cumul_cal, 1), hr_avg, end_time.isoformat()))
            for offset_pct in [0, 0.5, 1.0]:
                t_log  = cursor_time + timedelta(minutes=int(dur * offset_pct))
                stress = max(5, min(99, int(noisy(
                    {"active":55,"meal":25,"rest":20,"sleep":10}.get(act["type"],30) + max(0,(hr_avg-80)*0.4), 8))))
                c.execute("""INSERT INTO sensor_log
                    (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, int(noisy(act["hr_base"], act["hr_noise"], 40, 200)),
                     round(noisy(act["spo2_base"], 0.3, 90, 100), 1),
                     round(noisy(act["skin_temp"], 0.15, 35, 40), 2),
                     compute_hrv(hr_avg, stress), stress,
                     cumul_steps, round(cumul_cal, 1),
                     act["name"], act["type"], t_log.isoformat()))
            prev_type   = act["type"]
            cursor_time = end_time + timedelta(minutes=random.randint(2, 8))
    conn.commit()
    print(f"  Kişi {pid} için geçmiş veri tamamlandı.")

    # Geçmiş veri üretildikten sonra Markov matrisini oluştur
    build_markov_matrix(conn, pid)
    print(f"  Kişi {pid} için Markov matrisi oluşturuldu.")


# ── ANOMALİ & UYARI ───────────────────────────────────────────────────────────


def build_personal_stats(conn, pid):
    """
    Kişinin son 7 günlük sensör verisinden kişiye özgü
    istatistiksel profil hesapla (mean, std) — aktivite tipine göre ayrı.
    Sonuçları personal_stats tablosuna kaydet.
    """
    import statistics as _stats
    c = conn.cursor()
    now_iso = datetime.now().isoformat()

    metrics = ["heart_rate", "spo2", "skin_temp", "hrv", "stress_level"]
    act_types = ["sleep", "active", "rest", "meal"]

    for act_type in act_types:
        rows = c.execute("""
            SELECT heart_rate, spo2, skin_temp, hrv, stress_level
            FROM sensor_log
            WHERE person_id=? AND activity_type=?
              AND recorded_at >= datetime('now','-7 days')
        """, (pid, act_type)).fetchall()

        if len(rows) < 5:
            continue

        for metric in metrics:
            vals = [r[metric] for r in rows if r[metric] and r[metric] > 0]
            if len(vals) < 3:
                continue
            mean = sum(vals) / len(vals)
            std  = _stats.stdev(vals) if len(vals) > 1 else 1.0
            c.execute("""
                INSERT INTO personal_stats
                    (person_id, metric, activity_type, mean, std, n, updated_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(person_id, metric, activity_type) DO UPDATE SET
                    mean=excluded.mean, std=excluded.std,
                    n=excluded.n, updated_at=excluded.updated_at
            """, (pid, metric, act_type, round(mean,3), round(max(std,0.1),3), len(vals), now_iso))

    conn.commit()


# Kişisel istatistik cache — pid → {data, timestamp}
_personal_stats_cache = {}

def get_personal_stats(conn, pid):
    """Kişinin istatistiksel profilini önbellekten getir (10 dk cache)."""
    now_t = time.time()
    if pid in _personal_stats_cache and now_t - _personal_stats_cache[pid]["ts"] < 600:
        return _personal_stats_cache[pid]["data"]

    rows = conn.execute("""
        SELECT metric, activity_type, mean, std
        FROM personal_stats WHERE person_id=?
    """, (pid,)).fetchall()

    # {metric: {activity_type: {mean, std}}} formatında düzenle
    data = {}
    for r in rows:
        if r["metric"] not in data:
            data[r["metric"]] = {}
        data[r["metric"]][r["activity_type"]] = {
            "mean": r["mean"], "std": r["std"]
        }

    if not data:
        build_personal_stats(conn, pid)
        rows = conn.execute("""
            SELECT metric, activity_type, mean, std
            FROM personal_stats WHERE person_id=?
        """, (pid,)).fetchall()
        for r in rows:
            if r["metric"] not in data:
                data[r["metric"]] = {}
            data[r["metric"]][r["activity_type"]] = {
                "mean": r["mean"], "std": r["std"]
            }

    _personal_stats_cache[pid] = {"data": data, "ts": now_t}
    return data


def check_statistical_anomalies(pid, s, conn, socketio=None):
    """
    Kişinin kendi istatistiksel profiline göre anomali tespiti.
    Z-score bazlı: |değer - kişisel_ortalama| / kişisel_std > eşik
    
    Kural bazlı sistemin tamamlayıcısı — ikisi birlikte çalışır.
    """
    c = conn.cursor()
    activity_type = s.get("activity_type", "rest")
    personal_stats = get_personal_stats(conn, pid)

    # Z-score eşikleri
    WARN_THRESHOLD     = 2.5   # uyarı
    CRITICAL_THRESHOLD = 3.5   # kritik

    # Kontrol edilecek metrikler ve Türkçe açıklamalar
    check_metrics = {
        "heart_rate":   ("nabız", "bpm"),
        "spo2":         ("SpO₂", "%"),
        "skin_temp":    ("cilt sıcaklığı", "°C"),
        "hrv":          ("HRV", "ms"),
        "stress_level": ("stres seviyesi", "/100"),
    }

    for metric, (metric_tr, unit) in check_metrics.items():
        val = s.get(metric)
        if val is None or val <= 0:
            continue

        # Aktivite tipine göre kişisel norm
        stat = (personal_stats.get(metric, {}).get(activity_type) or
                personal_stats.get(metric, {}).get("rest"))
        if not stat:
            continue

        mean = stat["mean"]
        std  = max(stat["std"], 0.5)
        z    = abs(val - mean) / std

        if z < WARN_THRESHOLD:
            continue

        severity = "critical" if z >= CRITICAL_THRESHOLD else "warning"
        direction = "yüksek" if val > mean else "düşük"
        z_rounded = round(z, 1)

        msg_tr = f"{metric_tr.capitalize()} kişisel normdan {z_rounded} std {direction} ({val}{unit}, norm: {round(mean,1)})"
        msg_en = f"{metric_tr} {z_rounded} std {direction} from personal norm ({val}{unit}, norm: {round(mean,1)})"

        # Son 20 dakikada aynı metrik için istatistiksel anomali var mı?
        exists = c.execute("""
            SELECT id FROM anomalies WHERE person_id=? AND metric=?
              AND message_tr LIKE '%kişisel normdan%'
              AND datetime(detected_at) > datetime('now','-20 minutes')
        """, (pid, metric)).fetchone()

        if not exists:
            c.execute("""INSERT INTO anomalies
                (person_id,message_tr,message_en,metric,value,severity,detected_at)
                VALUES (?,?,?,?,?,?,?)""",
                (pid, msg_tr, msg_en, metric, round(val,1), severity, datetime.now().isoformat()))
            if socketio:
                socketio.emit("anomaly", {
                    "person_id":   pid,
                    "message_tr":  msg_tr,
                    "message_en":  msg_en,
                    "metric":      metric,
                    "value":       round(val, 1),
                    "severity":    severity,
                    "z_score":     z_rounded,
                    "personal_mean": round(mean, 1),
                    "detected_at": datetime.now().isoformat(),
                })


def check_anomalies(pid, s, conn, socketio=None):
    """Anlık değerleri anomali kurallarıyla karşılaştır."""
    c = conn.cursor()
    metrics = {
        "heart_rate":   s.get("heart_rate", 70),
        "spo2":         s.get("spo2", 98),
        "skin_temp":    s.get("skin_temp", 36.5),
        "hrv":          s.get("hrv", 45),
        "stress_level": s.get("stress_level", 30),
        "steps":        s.get("steps", 0),
        "calories":     s.get("calories", 0),
        "active_mins":  s.get("active_mins", 0),
        "screen_mins":  s.get("screen_mins", 0),
    }
    for rule in ANOMALY_RULES:
        val = metrics.get(rule["metric"], 0)
        hit = ((rule["direction"] == "above" and val > rule["threshold"]) or
               (rule["direction"] == "below" and val < rule["threshold"] and val > 0))
        if hit:
            exists = c.execute("""SELECT id FROM anomalies WHERE person_id=? AND metric=?
                AND datetime(detected_at) > datetime('now','-30 minutes')""",
                (pid, rule["metric"])).fetchone()
            if not exists:
                c.execute("""INSERT INTO anomalies
                    (person_id,message_tr,message_en,metric,value,severity,detected_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (pid, rule["message_tr"], rule["message_en"],
                     rule["metric"], round(val, 1), rule["severity"], datetime.now().isoformat()))
                if socketio:
                    socketio.emit("anomaly", {
                        "person_id": pid, "message_tr": rule["message_tr"],
                        "message_en": rule["message_en"], "metric": rule["metric"],
                        "value": round(val, 1), "severity": rule["severity"],
                        "detected_at": datetime.now().isoformat(),
                    })


def check_smart_alerts(conn, socketio=None):
    """Örüntü tabanlı akıllı uyarıları kontrol et (~1 saatte bir çağrılır)."""
    c   = conn.cursor()
    now = datetime.now()
    for p in c.execute("SELECT id FROM persons WHERE active=1").fetchall():
        pid = p["id"]
        ex_count = c.execute("""SELECT COUNT(*) as n FROM activity_log
            WHERE person_id=? AND activity_type='active'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["n"]
        if ex_count == 0:
            _insert_alert(c, pid, "no_exercise_3d",
                "3 gündür aktif aktivite yok", "No active activity for 3 days",
                "warning", now, socketio)
        sleep_starts = c.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-5 days')
            ORDER BY start_time DESC LIMIT 5""", (pid,)).fetchall()
        if len(sleep_starts) >= 3:
            hours = []
            for row in sleep_starts:
                try: hours.append(datetime.fromisoformat(row["start_time"]).hour)
                except: pass
            if hours and max(hours) - min(hours) >= 3:
                spread = max(hours) - min(hours)
                _insert_alert(c, pid, "irregular_sleep",
                    f"Uyku saatinde {spread} saatlik düzensizlik",
                    f"Sleep irregularity of {spread}h", "warning", now, socketio)
        sleep_avg = c.execute("""SELECT AVG(duration_mins) as avg_dur FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["avg_dur"]
        if sleep_avg and sleep_avg < 360:
            deficit = round((360 - sleep_avg) / 60, 1)
            _insert_alert(c, pid, "sleep_debt",
                f"Uyku ortalaması {round(sleep_avg/60,1)}s — {deficit}s borç",
                f"Sleep avg {round(sleep_avg/60,1)}h — {deficit}h debt", "warning", now, socketio)
        stress_avg = c.execute("""SELECT AVG(stress_level) as avg_s FROM sensor_log
            WHERE person_id=? AND recorded_at >= datetime('now','-2 days')""", (pid,)).fetchone()["avg_s"]
        if stress_avg and stress_avg > 65:
            _insert_alert(c, pid, "high_stress_trend",
                f"Son 2 günde ortalama stres yüksek ({round(stress_avg,0)}/100)",
                f"High stress last 2 days ({round(stress_avg,0)}/100)", "warning", now, socketio)
    conn.commit()


def _insert_alert(c, pid, alert_type, msg_tr, msg_en, severity, now, socketio=None):
    """Son 6 saatte aynı tipte uyarı yoksa ekle."""
    exists = c.execute("""SELECT id FROM smart_alerts WHERE person_id=? AND alert_type=?
        AND datetime(detected_at) > datetime('now','-6 hours')""", (pid, alert_type)).fetchone()
    if not exists:
        c.execute("""INSERT INTO smart_alerts (person_id,alert_type,message_tr,message_en,severity,detected_at)
            VALUES (?,?,?,?,?,?)""", (pid, alert_type, msg_tr, msg_en, severity, now.isoformat()))
        if socketio:
            socketio.emit("smart_alert", {
                "person_id": pid, "alert_type": alert_type,
                "message_tr": msg_tr, "severity": severity,
                "detected_at": now.isoformat(),
            })


# ── SİMÜLASYON DÖNGÜSÜ ────────────────────────────────────────────────────────

def simulation_loop(socketio):
    """
    Ana simülasyon döngüsü.
    Her iterasyonda aktif kişilerin durumunu günceller,
    WebSocket ile istemcilere iletir.
    """
    global current_weather, current_temp, weather_tick
    tick = 0; alert_tick = 0

    while True:
        try:
            conn = get_db(); c = conn.cursor()
            now  = datetime.now(); hour = now.hour

            # Hava durumu güncelleme
            weather_tick += 1
            if weather_tick >= 200:
                weather_tick    = 0
                current_weather = random.choice(WEATHER_CONDITIONS)
                current_temp    = random.uniform(*current_weather["temp_range"])
                c.execute("INSERT INTO weather_log (condition,condition_en,icon,temp) VALUES (?,?,?,?)",
                    (current_weather["condition"], current_weather["condition_en"],
                     current_weather["icon"], round(current_temp, 1)))

            # Akıllı uyarılar (~60 dk)
            alert_tick += 1
            if alert_tick >= 1200:
                alert_tick = 0
                check_smart_alerts(conn, socketio)

            for row in c.execute("SELECT id, city FROM persons WHERE active=1").fetchall():
                pid  = row["id"]
                city = row["city"] or ""
                st   = c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone()

                if st is None:
                    act = pick_activity_for_hour(hour)
                    loc = get_city_base(city, act["location"])
                    lat, lng = jitter_location(loc["lat_base"], loc["lng_base"], act["type"])
                    hr  = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
                    dur = random.randint(act["dur_min"], act["dur_max"])
                    c.execute("""INSERT INTO current_state
                        (person_id,activity_name,activity_name_en,activity_icon,activity_type,activity_color,
                         steps,active_mins,calories,screen_mins,since_mins,duration,progress,out_count,meal_count,
                         heart_rate,heart_rate_prev,spo2,skin_temp,hrv,stress_level,
                         latitude,longitude,location_name,mood,
                         chart_active,chart_rest,chart_meal,chart_sleep,updated_at)
                        VALUES (?,?,?,?,?,?,0,0,0,0,0,?,0,0,0,?,?,?,?,?,?,?,?,?,?,0,0,0,8,?)""",
                        (pid, act["name"], act["name_en"], act["icon"], act["type"], act["color"],
                         dur, hr, hr,
                         round(noisy(act["spo2_base"], 0.5, 90, 100), 1),
                         round(noisy(act["skin_temp"], 0.2, 35, 40), 1),
                         compute_hrv(hr, 30), 30, lat, lng, act["location"], act["mood"], now.isoformat()))
                    conn.commit()
                    st = c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone()
                    activity_start_times[pid] = now.isoformat()

                s   = dict(st)
                act = next((a for a in ACTIVITIES if a["name"] == s["activity_name"]), ACTIVITIES[10])
                if pid not in activity_start_times:
                    activity_start_times[pid] = now.isoformat()

                ns  = s["steps"]       + int(act["step_rate"] * (0.8 + random.random() * 0.5))
                na  = s["active_mins"] + (1 if act["type"] == "active" else 0)
                nc  = s["calories"]    + act["cal_rate"] * (0.85 + random.random() * 0.3)
                nsc = s["screen_mins"] + (1 if act["type"] in ["rest", "sleep"] else 0)
                nsi = s["since_mins"]  + 1
                np_ = min(100, int((nsi / max(s["duration"], 1)) * 100))
                prev_hr = s["heart_rate"]

                # Kullanıcının seçtiği dağılımdan biyometrik üret
                _ds = get_dist_settings_cached()

                def _sim_sample(metric, act_base, act_noise, lo, hi):
                    cfg = _ds.get(metric)
                    if not cfg:
                        return noisy(act_base, act_noise, lo, hi)
                    dist   = cfg["distribution"]
                    params = {**cfg["params"]}
                    if dist == "normal":
                        params["mean"] = act_base * 0.7 + params.get("mean", act_base) * 0.3
                        params["std"]  = params.get("std", act_noise)
                    elif dist == "uniform":
                        user_low  = params.get("low",  act_base - act_noise * 2)
                        user_high = params.get("high", act_base + act_noise * 2)
                        shift = act_base - (user_low + user_high) / 2
                        params["low"]  = user_low  + shift * 0.7
                        params["high"] = user_high + shift * 0.7
                    elif dist == "exponential":
                        params["offset"] = act_base * 0.6 + params.get("offset", 0) * 0.4
                    elif dist == "lognormal":
                        if act_base > 0:
                            params["mean"] = math.log(act_base) * 0.7 + params.get("mean", math.log(act_base)) * 0.3
                    elif dist == "triangular":
                        user_mode = params.get("mode", act_base)
                        shift     = act_base - user_mode
                        params["low"]  = params.get("low",  act_base - 20) + shift * 0.7
                        params["mode"] = act_base * 0.7 + user_mode * 0.3
                        params["high"] = params.get("high", act_base + 20) + shift * 0.7
                    elif dist == "poisson":
                        params["lam"] = max(1, act_base * 0.8)
                    return sample_distribution(dist, params, lo, hi)

                new_hr     = int(smooth(prev_hr,
                                _sim_sample("heart_rate", act["hr_base"], act["hr_noise"], 40, 200), alpha=0.15))
                new_spo2   = round(smooth(s["spo2"],
                                _sim_sample("spo2", act["spo2_base"], 0.5, 90, 100), 0.1), 1)
                new_temp   = round(smooth(s["skin_temp"],
                                _sim_sample("skin_temp", act["skin_temp"], 0.15, 35, 40), 0.08), 2)
                stress_base = {"active":55,"meal":25,"rest":20,"sleep":10}.get(act["type"], 30)
                new_stress  = int(smooth(s["stress_level"],
                                _sim_sample("stress", stress_base, 8, 5, 99), 0.2))
                new_hrv     = compute_hrv(new_hr, new_stress)

                loc = get_city_base(city, act["location"])
                new_lat, new_lng = jitter_location(loc["lat_base"], loc["lng_base"], act["type"])
                if s["location_name"] == act["location"]:
                    new_lat = smooth(s["latitude"],  new_lat, 0.05 if act["type"] == "active" else 0.01)
                    new_lng = smooth(s["longitude"], new_lng, 0.05 if act["type"] == "active" else 0.01)

                oc  = s["out_count"]; mc = s["meal_count"]
                ca  = s["chart_active"] + (1 if act["type"] == "active" else 0)
                cr  = s["chart_rest"]   + (1 if act["type"] == "rest"   else 0)
                cm  = s["chart_meal"]   + (1 if act["type"] == "meal"   else 0)
                csl = s["chart_sleep"]  + (1 if act["type"] == "sleep"  else 0)

                tick += 1
                if tick % 5 == 0:
                    c.execute("""INSERT INTO sensor_log
                        (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid, new_hr, new_spo2, new_temp, new_hrv, new_stress,
                         ns, round(nc, 1), act["name"], act["type"], now.isoformat()))

                if nsi >= s["duration"]:
                    if act["type"] == "active": oc += 1
                    if act["type"] == "meal":   mc += 1
                    start_t = activity_start_times.get(pid, now.isoformat())
                    c.execute("""INSERT INTO activity_log
                        (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                         start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid, act["name"], act["name_en"], act["icon"], act["type"],
                         start_t, now.isoformat(), max(1, nsi), ns, round(nc, 1), new_hr, now.isoformat()))
                    # Markov geçişi dene, başarısız olursa klasik seçime düş
                    na2 = pick_activity_markov(pid, act["name"], hour, conn)
                    dur = random.randint(na2["dur_min"], na2["dur_max"])
                    if act["type"] == "sleep": dur = random.randint(360, 540)
                    activity_start_times[pid] = now.isoformat()
                    c.execute("""UPDATE current_state SET
                        activity_name=?,activity_name_en=?,activity_icon=?,activity_type=?,activity_color=?,
                        steps=?,active_mins=?,calories=?,screen_mins=?,since_mins=0,duration=?,progress=0,
                        out_count=?,meal_count=?,heart_rate=?,heart_rate_prev=?,spo2=?,skin_temp=?,hrv=?,stress_level=?,
                        latitude=?,longitude=?,location_name=?,mood=?,
                        chart_active=?,chart_rest=?,chart_meal=?,chart_sleep=?,updated_at=?
                        WHERE person_id=?""",
                        (na2["name"],na2["name_en"],na2["icon"],na2["type"],na2["color"],
                         ns,na,round(nc,1),nsc,dur,oc,mc,new_hr,prev_hr,
                         new_spo2,new_temp,new_hrv,new_stress,
                         round(new_lat,6),round(new_lng,6),na2["location"],na2["mood"],
                         ca,cr,cm,csl,now.isoformat(),pid))
                else:
                    c.execute("""UPDATE current_state SET
                        steps=?,active_mins=?,calories=?,screen_mins=?,since_mins=?,progress=?,
                        heart_rate=?,heart_rate_prev=?,spo2=?,skin_temp=?,hrv=?,stress_level=?,
                        latitude=?,longitude=?,location_name=?,mood=?,
                        chart_active=?,chart_rest=?,chart_meal=?,chart_sleep=?,updated_at=?
                        WHERE person_id=?""",
                        (ns,na,round(nc,1),nsc,nsi,np_,new_hr,prev_hr,
                         new_spo2,new_temp,new_hrv,new_stress,
                         round(new_lat,6),round(new_lng,6),act["location"],act["mood"],
                         ca,cr,cm,csl,now.isoformat(),pid))

                conn.commit()
                upd = dict(c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone())
                check_anomalies(pid, upd, conn, socketio)
                check_statistical_anomalies(pid, upd, conn, socketio)
                conn.commit()
                person_row = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
                if person_row:
                    socketio.emit("state_update", {**dict(person_row), **upd})
            conn.close()
        except Exception as e:
            print(f"Simülasyon hatası: {e}")
            import traceback; traceback.print_exc()
        time.sleep(max(0.5, 3.0 / sim_speed))


# ── ÖRÜNTÜ ANALİZİ YARDIMCI FONKSİYONU ──────────────────────────────────────

def _compute_metric_params(conn, pid):
    """
    Kişinin son 14 günlük verisinden her metrik için
    tüm dağılım parametrelerini otomatik hesapla.
    routes.py'deki pattern_distributions endpoint'i tarafından kullanılır.
    """
    import statistics as _stats, math as _math
    result = {}
    now = datetime.now()

    def safe_hour(ts):
        if not ts: return None
        try:
            dt = datetime.fromisoformat(ts)
            return round(dt.hour + dt.minute / 60, 2)
        except: return None

    wake_hours=[]; sleep_hours=[]; sleep_mins_list=[]
    first_act_hours=[]; exercise_hours=[]; exercise_mins_list=[]
    outdoor_hours=[]; first_meal_hours=[]; last_meal_hours=[]
    meal_counts=[]; steps_list=[]; calories_list=[]
    active_mins_list=[]; avg_hr_list=[]; avg_spo2_list=[]
    avg_stress_list=[]; avg_hrv_list=[]

    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")

        sr = conn.execute("""SELECT start_time,end_time,duration_mins FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""", (pid, d)).fetchone()
        if sr:
            wh = safe_hour(sr["end_time"])
            sh = safe_hour(sr["start_time"])
            if wh: wake_hours.append(wh)
            if sh: sleep_hours.append(sh)
            if sr["duration_mins"]: sleep_mins_list.append(sr["duration_mins"])

        fa = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type!='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        if fa:
            h = safe_hour(fa["start_time"])
            if h: first_act_hours.append(h)

        ex = conn.execute("""SELECT start_time,SUM(duration_mins) as total FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            GROUP BY date(start_time,'localtime') ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        if ex:
            h = safe_hour(ex["start_time"])
            if h: exercise_hours.append(h)
            if ex["total"]: exercise_mins_list.append(int(ex["total"]))

        outdoor = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        if outdoor:
            h = safe_hour(outdoor["start_time"])
            if h: outdoor_hours.append(h)

        meals = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='meal' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC""", (pid, d)).fetchall()
        meal_h = [safe_hour(m["start_time"]) for m in meals if safe_hour(m["start_time"])]
        if meal_h:
            first_meal_hours.append(meal_h[0])
            last_meal_hours.append(meal_h[-1])
        meal_counts.append(len(meal_h))

        met = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
            COALESCE(MAX(calories_snap),0) as cal,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as act_mins
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""", (pid, d)).fetchone()
        if met["steps"]    > 0: steps_list.append(int(met["steps"]))
        if met["cal"]      > 0: calories_list.append(float(met["cal"]))
        if met["act_mins"] > 0: active_mins_list.append(int(met["act_mins"]))

        sen = conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,
            ROUND(AVG(spo2),1) as avg_spo2,ROUND(AVG(stress_level),1) as avg_stress,
            ROUND(AVG(hrv),1) as avg_hrv
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""", (pid, d)).fetchone()
        if sen["avg_hr"]:     avg_hr_list.append(float(sen["avg_hr"]))
        if sen["avg_spo2"]:   avg_spo2_list.append(float(sen["avg_spo2"]))
        if sen["avg_stress"]: avg_stress_list.append(float(sen["avg_stress"]))
        if sen["avg_hrv"]:    avg_hrv_list.append(float(sen["avg_hrv"]))

    def params_for(vals):
        vals = [v for v in vals if v is not None and v > 0]
        if not vals: return {}
        mean = sum(vals) / len(vals)
        std  = _stats.stdev(vals) if len(vals) > 1 else 0.1
        mn, mx = min(vals), max(vals)
        mode = sorted(vals)[len(vals) // 2]
        log_vals = [_math.log(v) for v in vals]
        log_mean = sum(log_vals) / len(log_vals)
        log_std  = _stats.stdev(log_vals) if len(log_vals) > 1 else 0.1
        return {
            "normal":      {"mean": round(mean,2),    "std":   round(max(std,0.1),2)},
            "uniform":     {"low":  round(mn,2),      "high":  round(mx,2)},
            "exponential": {"scale":round(mean,2),    "offset":round(mn*0.5,2)},
            "poisson":     {"lam":  round(mean,1)},
            "lognormal":   {"mean": round(log_mean,3),"sigma": round(max(log_std,0.1),3)},
            "triangular":  {"low":  round(mn,2),      "mode":  round(mode,2), "high": round(mx,2)},
            "beta":        {"alpha":2.0, "beta":5.0,  "scale": round(mx,2)},
        }

    data_map = {
        "wake_hour":       wake_hours,      "sleep_hour":      sleep_hours,
        "sleep_mins":      sleep_mins_list, "first_act_hour":  first_act_hours,
        "exercise_hour":   exercise_hours,  "exercise_mins":   exercise_mins_list,
        "outdoor_hour":    outdoor_hours,   "first_meal_hour": first_meal_hours,
        "last_meal_hour":  last_meal_hours, "meal_count":      meal_counts,
        "steps":           steps_list,      "calories":        calories_list,
        "active_mins":     active_mins_list,"avg_hr":          avg_hr_list,
        "avg_spo2":        avg_spo2_list,   "avg_stress":      avg_stress_list,
        "avg_hrv":         avg_hrv_list,
    }
    for metric, vals in data_map.items():
        result[metric] = params_for(vals)
    return result