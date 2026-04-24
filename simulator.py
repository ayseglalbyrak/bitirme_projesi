"""
simulator.py — Simülasyon motoru
Aktivite tanımları, biyometrik hesaplamalar, dağılım modelleri,
geçmiş veri üretimi, anomali/uyarı mantığı ve simülasyon döngüsü.
"""
import random, math, time, threading
from datetime import datetime, timedelta
import numpy as np
from db import get_db, DB_PATH
import sqlite3

# ── AKTİVİTE TANIMI ───────────────────────────────────────────────────────────

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
    {"name": "Pişiriyor",           "name_en": "Cooking",         "icon": "👨\u200d🍳", "color": "#EF9F27",
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
    {"metric": "heart_rate",  "threshold": 160, "direction": "above",
     "message_tr": "Kalp atışı kritik seviyede yüksek", "message_en": "Heart rate critically high", "severity": "critical"},
    {"metric": "heart_rate",  "threshold": 45,  "direction": "below",
     "message_tr": "Kalp atışı çok düşük",             "message_en": "Heart rate too low",         "severity": "warning"},
    {"metric": "spo2",        "threshold": 93,  "direction": "below",
     "message_tr": "Oksijen doygunluğu düşük",         "message_en": "Oxygen saturation low",      "severity": "critical"},
    {"metric": "skin_temp",   "threshold": 38.0,"direction": "above",
     "message_tr": "Vücut sıcaklığı yüksek (ateş?)",  "message_en": "Body temperature elevated",  "severity": "warning"},
    {"metric": "steps",       "threshold": 15000,"direction": "above",
     "message_tr": "Adım sayısı çok yüksek",           "message_en": "Step count too high",        "severity": "info"},
    {"metric": "active_mins", "threshold": 200,  "direction": "above",
     "message_tr": "Aktif süre çok uzun",              "message_en": "Active duration too long",   "severity": "warning"},
    {"metric": "active_mins", "threshold": 10,   "direction": "below",
     "message_tr": "Gün boyu hareketsiz",              "message_en": "Inactive all day",           "severity": "info"},
    {"metric": "stress_level","threshold": 80,   "direction": "above",
     "message_tr": "Stres seviyesi çok yüksek",        "message_en": "Stress level very high",     "severity": "warning"},
    {"metric": "hrv",         "threshold": 15,   "direction": "below",
     "message_tr": "Kalp ritmi değişkenliği düşük",    "message_en": "Low heart rate variability", "severity": "warning"},
]

LOCATIONS = {
    "ev":     {"lat_base": 41.015, "lng_base": 28.979},
    "ofis":   {"lat_base": 41.042, "lng_base": 28.986},
    "dışarı": {"lat_base": 41.025, "lng_base": 28.975},
}

AVATAR_COLORS = ["#CECBF6","#9FE1CB","#F5C4B3","#F4C0D1","#B5D4F4","#C0DD97","#FAC775","#F7C1C1"]

WEATHER_CONDITIONS = [
    {"condition": "Güneşli",         "condition_en": "Sunny",        "icon": "☀️",  "temp_range": (20, 32)},
    {"condition": "Parçalı bulutlu", "condition_en": "Partly cloudy","icon": "⛅",  "temp_range": (18, 27)},
    {"condition": "Bulutlu",         "condition_en": "Cloudy",       "icon": "☁️",  "temp_range": (15, 22)},
    {"condition": "Yağmurlu",        "condition_en": "Rainy",        "icon": "🌧️", "temp_range": (12, 18)},
    {"condition": "Rüzgarlı",        "condition_en": "Windy",        "icon": "💨",  "temp_range": (10, 20)},
]

# ── DAĞILIM MODELLERİ ─────────────────────────────────────────────────────────

def sample_distribution(dist_name: str, params: dict, min_v=None, max_v=None) -> float:
    """
    İstenilen istatistiksel dağılımdan örnek üret.

    Desteklenen dağılımlar:
      normal     : mean, std
      uniform    : low, high
      exponential: scale (lambda'nın tersi)
      poisson    : lam (lambda)
      lognormal  : mean, sigma
      triangular : low, mode, high
      beta       : alpha, beta, scale (0-scale arası normalize)
    """
    dist_name = dist_name.lower()
    try:
        if dist_name == "normal":
            mean = params.get("mean", 75)
            std  = params.get("std",  10)
            v    = random.gauss(mean, std)
        elif dist_name == "uniform":
            low  = params.get("low",  60)
            high = params.get("high", 90)
            v    = random.uniform(low, high)
        elif dist_name == "exponential":
            scale = params.get("scale", 1.0)
            v     = random.expovariate(1.0 / max(scale, 0.001))
            v    += params.get("offset", 0)
        elif dist_name == "poisson":
            lam = params.get("lam", 5)
            # numpy olmadan Poisson: Knuth algoritması
            L, k, p = math.exp(-lam), 0, 1.0
            while p > L:
                k += 1
                p *= random.random()
            v = float(k - 1)
        elif dist_name == "lognormal":
            mean  = params.get("mean",  4.0)
            sigma = params.get("sigma", 0.5)
            v     = random.lognormvariate(mean, sigma)
        elif dist_name == "triangular":
            low  = params.get("low",  0)
            mode = params.get("mode", 50)
            high = params.get("high", 100)
            v    = random.triangular(low, high, mode)
        elif dist_name == "beta":
            alpha = params.get("alpha", 2.0)
            beta_ = params.get("beta",  5.0)
            scale = params.get("scale", 100)
            v     = random.betavariate(alpha, beta_) * scale
        else:
            # Bilinmeyen dağılım → normal
            v = random.gauss(params.get("mean", 75), params.get("std", 10))
    except Exception:
        v = params.get("mean", 75) + random.gauss(0, params.get("std", 10))

    if min_v is not None: v = max(min_v, v)
    if max_v is not None: v = min(max_v, v)
    return v


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


def compute_stress(activity_type, hr, since_mins):
    """Aktivite tipine göre stres seviyesi hesapla."""
    base       = {"active": 55, "meal": 25, "rest": 20, "sleep": 10}.get(activity_type, 30)
    hr_factor  = max(0, (hr - 80) * 0.4)
    time_factor= min(20, since_mins * 0.3) if activity_type == "active" else 0
    return max(5, min(99, int(noisy(base + hr_factor + time_factor, 8))))


def jitter_location(base_lat, base_lng, activity_type):
    """Aktivite tipine göre GPS koordinatı jitter ekle."""
    radius = 0.005 if activity_type == "active" else (0.0005 if activity_type in ["rest","sleep","meal"] else 0.001)
    angle  = random.uniform(0, 2 * math.pi)
    dist   = random.uniform(0, radius)
    return base_lat + dist * math.cos(angle), base_lng + dist * math.sin(angle)


def compute_health_score(sleep_mins, active_mins, avg_stress, avg_hr, spo2):
    """Günlük sağlık skoru (0-100)."""
    sleep_h      = sleep_mins / 60
    sleep_score  = 30 if 7 <= sleep_h <= 9 else (20 if 6 <= sleep_h < 7 else (10 if sleep_h > 0 else 0))
    active_score = 25 if active_mins >= 30 else int((active_mins / 30) * 25)
    stress_score = int((1 - min(avg_stress, 100) / 100) * 20)
    hr_score     = 15 if 60 <= avg_hr <= 100 else (8 if avg_hr > 0 else 0)
    spo2_score   = 10 if spo2 >= 96 else (5 if spo2 >= 93 else 0)
    return min(100, sleep_score + active_score + stress_score + hr_score + spo2_score)


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
    """
    Kişi için son N günün aktivite ve sensör verilerini üret.
    Zaten veri varsa atlar.
    """
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) as n FROM activity_log WHERE person_id=?", (pid,)).fetchone()["n"] > 0:
        return
    print(f"  Kişi {pid} için {days_back} günlük geçmiş veri üretiliyor...")
    sleep_hour_base = random.uniform(22.0, 24.0)
    wake_hour_base  = random.uniform(6.0, 8.5)
    now = datetime.now()
    for day_offset in range(days_back - 1, -1, -1):
        day_start    = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        weekday      = day_start.weekday()
        sleep_start_h= max(21, min(25, sleep_hour_base + random.gauss(0, 0.4)))
        wake_h       = max(5.5, min(9.0, wake_hour_base + random.gauss(0, 0.3)))
        sl_start     = day_start - timedelta(hours=24 - sleep_start_h % 24)
        sl_dur       = max(240, min(600, int((wake_h + (24 - sleep_start_h % 24)) * 60)))
        sl_end       = sl_start + timedelta(minutes=sl_dur)
        sl_act       = next(a for a in ACTIVITIES if a["type"] == "sleep")
        sl_hr        = int(noisy(sl_act["hr_base"], sl_act["hr_noise"], 40, 75))
        c.execute("""INSERT INTO activity_log
            (person_id,activity_name,activity_name_en,activity_icon,activity_type,
             start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid,sl_act["name"],sl_act["name_en"],sl_act["icon"],sl_act["type"],
             sl_start.isoformat(),sl_end.isoformat(),sl_dur,
             0,round(sl_dur*sl_act["cal_rate"],1),sl_hr,sl_end.isoformat()))
        t_cur = sl_start
        while t_cur < sl_end:
            c.execute("""INSERT INTO sensor_log
                (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,int(noisy(sl_act["hr_base"],sl_act["hr_noise"],40,75)),
                 round(noisy(sl_act["spo2_base"],0.3,90,100),1),
                 round(noisy(sl_act["skin_temp"],0.1,35,38),2),
                 compute_hrv(sl_hr,10),random.randint(5,15),0,0,
                 sl_act["name"],sl_act["type"],t_cur.isoformat()))
            t_cur += timedelta(minutes=30)
        cursor_time = sl_end + timedelta(minutes=random.randint(5,15))
        cumul_steps, cumul_cal = 0, sl_dur * sl_act["cal_rate"]
        prev_type = "sleep"
        day_end   = day_start.replace(hour=22, minute=30)
        while cursor_time < day_end:
            act = pick_activity_for_hour(cursor_time.hour, prev_type)
            dur = random.randint(act["dur_min"], act["dur_max"])
            if weekday >= 5 and act["type"] in ["rest","sleep"]:
                dur = int(dur * 1.3)
            end_time = cursor_time + timedelta(minutes=dur)
            if end_time > day_end:
                dur = max(5, int((day_end - cursor_time).seconds / 60))
                end_time = day_end
            hr_avg      = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
            steps       = int(act["step_rate"] * dur * (0.85 + random.random() * 0.3))
            cal         = round(act["cal_rate"] * dur * (0.85 + random.random() * 0.3), 1)
            cumul_steps += steps
            cumul_cal   += cal
            c.execute("""INSERT INTO activity_log
                (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                 start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,act["name"],act["name_en"],act["icon"],act["type"],
                 cursor_time.isoformat(),end_time.isoformat(),dur,
                 cumul_steps,round(cumul_cal,1),hr_avg,end_time.isoformat()))
            for offset_pct in [0, 0.5, 1.0]:
                t_log  = cursor_time + timedelta(minutes=int(dur * offset_pct))
                stress = compute_stress(act["type"], hr_avg, int(dur * offset_pct))
                c.execute("""INSERT INTO sensor_log
                    (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid,int(noisy(act["hr_base"],act["hr_noise"],40,200)),
                     round(noisy(act["spo2_base"],0.3,90,100),1),
                     round(noisy(act["skin_temp"],0.15,35,40),2),
                     compute_hrv(hr_avg,stress),stress,
                     cumul_steps,round(cumul_cal,1),
                     act["name"],act["type"],t_log.isoformat()))
            prev_type   = act["type"]
            cursor_time = end_time + timedelta(minutes=random.randint(2,8))
    conn.commit()
    print(f"  Kişi {pid} tamamlandı.")


# ── ANOMALİ & UYARI ───────────────────────────────────────────────────────────

def check_anomalies(pid, s, conn, socketio=None):
    """Anlık değerleri anomali kurallarıyla karşılaştır."""
    c = conn.cursor()
    metrics = {
        "heart_rate": s.get("heart_rate",70), "spo2": s.get("spo2",98),
        "skin_temp": s.get("skin_temp",36.5), "hrv": s.get("hrv",45),
        "stress_level": s.get("stress_level",30), "steps": s.get("steps",0),
        "calories": s.get("calories",0), "active_mins": s.get("active_mins",0),
        "screen_mins": s.get("screen_mins",0),
    }
    for rule in ANOMALY_RULES:
        val = metrics.get(rule["metric"], 0)
        hit = ((rule["direction"]=="above" and val>rule["threshold"]) or
               (rule["direction"]=="below" and val<rule["threshold"] and val>0))
        if hit:
            exists = c.execute("""SELECT id FROM anomalies WHERE person_id=? AND metric=?
                AND datetime(detected_at) > datetime('now','-30 minutes')""",
                (pid, rule["metric"])).fetchone()
            if not exists:
                c.execute("""INSERT INTO anomalies
                    (person_id,message_tr,message_en,metric,value,severity,detected_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (pid,rule["message_tr"],rule["message_en"],
                     rule["metric"],round(val,1),rule["severity"],
                     datetime.now().isoformat()))
                if socketio:
                    socketio.emit("anomaly", {
                        "person_id":  pid,
                        "message_tr": rule["message_tr"],
                        "metric":     rule["metric"],
                        "value":      round(val,1),
                        "severity":   rule["severity"],
                        "detected_at":datetime.now().isoformat(),
                    })


def _insert_alert(c, pid, alert_type, msg_tr, msg_en, severity, now, socketio=None):
    """Son 6 saatte aynı tipte uyarı yoksa ekle."""
    exists = c.execute("""SELECT id FROM smart_alerts
        WHERE person_id=? AND alert_type=?
          AND datetime(detected_at) > datetime('now','-6 hours')""",
        (pid, alert_type)).fetchone()
    if not exists:
        c.execute("""INSERT INTO smart_alerts
            (person_id,alert_type,message_tr,message_en,severity,detected_at)
            VALUES (?,?,?,?,?,?)""",
            (pid,alert_type,msg_tr,msg_en,severity,now.isoformat()))
        if socketio:
            socketio.emit("smart_alert", {
                "person_id":  pid,
                "alert_type": alert_type,
                "message_tr": msg_tr,
                "severity":   severity,
                "detected_at":now.isoformat(),
            })


def check_smart_alerts(conn, socketio=None):
    """Örüntü tabanlı akıllı uyarıları kontrol et (~1 saatte bir çağrılır)."""
    c   = conn.cursor()
    now = datetime.now()
    for p in c.execute("SELECT id, name FROM persons WHERE active=1").fetchall():
        pid = p["id"]
        ex_count = c.execute("""SELECT COUNT(*) as n FROM activity_log
            WHERE person_id=? AND activity_type='active'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["n"]
        if ex_count == 0:
            _insert_alert(c,pid,"no_exercise_3d","3 gündür aktif aktivite yok",
                "No active activity for 3 days","warning",now,socketio)
        sleep_starts = c.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-5 days')
            ORDER BY start_time DESC LIMIT 5""", (pid,)).fetchall()
        if len(sleep_starts) >= 3:
            hours = []
            for row in sleep_starts:
                try: hours.append(datetime.fromisoformat(row["start_time"]).hour)
                except: pass
            if hours:
                spread = max(hours) - min(hours)
                if spread >= 3:
                    _insert_alert(c,pid,"irregular_sleep",
                        f"Uyku saatinde {spread} saatlik düzensizlik",
                        f"Sleep schedule irregularity of {spread}h","warning",now,socketio)
        sleep_avg = c.execute("""SELECT AVG(duration_mins) as avg_dur FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["avg_dur"]
        if sleep_avg and sleep_avg < 360:
            deficit = round((360 - sleep_avg) / 60, 1)
            _insert_alert(c,pid,"sleep_debt",
                f"Uyku ortalaması {round(sleep_avg/60,1)}s — {deficit}s uyku borcu",
                f"Sleep avg {round(sleep_avg/60,1)}h — {deficit}h debt","warning",now,socketio)
        stress_avg = c.execute("""SELECT AVG(stress_level) as avg_s FROM sensor_log
            WHERE person_id=? AND recorded_at >= datetime('now','-2 days')""", (pid,)).fetchone()["avg_s"]
        if stress_avg and stress_avg > 65:
            _insert_alert(c,pid,"high_stress_trend",
                f"Son 2 günde ortalama stres yüksek ({round(stress_avg,0)}/100)",
                f"High avg stress last 2 days ({round(stress_avg,0)}/100)","warning",now,socketio)
    conn.commit()


# ── SİMÜLASYON DÖNGÜSÜ ────────────────────────────────────────────────────────

# Global durum
current_weather      = random.choice(WEATHER_CONDITIONS)
current_temp         = random.uniform(*current_weather["temp_range"])
weather_tick         = 0
sim_speed            = 1
activity_start_times = {}


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
            weather_tick += 1
            if weather_tick >= 200:
                weather_tick    = 0
                current_weather = random.choice(WEATHER_CONDITIONS)
                current_temp    = random.uniform(*current_weather["temp_range"])
                c.execute("INSERT INTO weather_log (condition,condition_en,icon,temp) VALUES (?,?,?,?)",
                    (current_weather["condition"],current_weather["condition_en"],
                     current_weather["icon"],round(current_temp,1)))
            alert_tick += 1
            if alert_tick >= 1200:
                alert_tick = 0
                check_smart_alerts(conn, socketio)
            for row in c.execute("SELECT id FROM persons WHERE active=1").fetchall():
                pid = row["id"]
                st  = c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone()
                if st is None:
                    act = pick_activity_for_hour(hour)
                    loc = LOCATIONS.get(act["location"], LOCATIONS["ev"])
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
                        (pid,act["name"],act["name_en"],act["icon"],act["type"],act["color"],
                         dur,hr,hr,
                         round(noisy(act["spo2_base"],0.5,90,100),1),
                         round(noisy(act["skin_temp"],0.2,35,40),1),
                         compute_hrv(hr,30),30,lat,lng,act["location"],act["mood"],now.isoformat()))
                    conn.commit()
                    st = c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone()
                    activity_start_times[pid] = now.isoformat()
                s   = dict(st)
                act = next((a for a in ACTIVITIES if a["name"]==s["activity_name"]), ACTIVITIES[10])
                if pid not in activity_start_times:
                    activity_start_times[pid] = now.isoformat()
                ns  = s["steps"]       + int(act["step_rate"]*(0.8+random.random()*0.5))
                na  = s["active_mins"] + (1 if act["type"]=="active" else 0)
                nc  = s["calories"]    + act["cal_rate"]*(0.85+random.random()*0.3)
                nsc = s["screen_mins"] + (1 if act["type"] in ["rest","sleep"] else 0)
                nsi = s["since_mins"]  + 1
                np_ = min(100, int((nsi/max(s["duration"],1))*100))
                prev_hr    = s["heart_rate"]
                new_hr     = int(smooth(prev_hr, noisy(act["hr_base"],act["hr_noise"],40,200), alpha=0.15))
                new_spo2   = round(smooth(s["spo2"],   noisy(act["spo2_base"],0.3,90,100), 0.1), 1)
                new_temp   = round(smooth(s["skin_temp"],noisy(act["skin_temp"],0.15,35,40), 0.08), 2)
                new_stress = compute_stress(act["type"], new_hr, nsi)
                new_hrv    = compute_hrv(new_hr, new_stress)
                loc        = LOCATIONS.get(act["location"], LOCATIONS["ev"])
                new_lat, new_lng = jitter_location(loc["lat_base"], loc["lng_base"], act["type"])
                if s["location_name"] == act["location"]:
                    new_lat = smooth(s["latitude"],  new_lat, 0.05 if act["type"]=="active" else 0.01)
                    new_lng = smooth(s["longitude"], new_lng, 0.05 if act["type"]=="active" else 0.01)
                oc  = s["out_count"]; mc = s["meal_count"]
                ca  = s["chart_active"]+(1 if act["type"]=="active" else 0)
                cr  = s["chart_rest"]  +(1 if act["type"]=="rest"   else 0)
                cm  = s["chart_meal"]  +(1 if act["type"]=="meal"   else 0)
                csl = s["chart_sleep"] +(1 if act["type"]=="sleep"  else 0)
                tick += 1
                if tick % 5 == 0:
                    c.execute("""INSERT INTO sensor_log
                        (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid,new_hr,new_spo2,new_temp,new_hrv,new_stress,
                         ns,round(nc,1),act["name"],act["type"],now.isoformat()))
                if nsi >= s["duration"]:
                    if act["type"]=="active": oc+=1
                    if act["type"]=="meal":   mc+=1
                    start_t  = activity_start_times.get(pid, now.isoformat())
                    c.execute("""INSERT INTO activity_log
                        (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                         start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid,act["name"],act["name_en"],act["icon"],act["type"],
                         start_t,now.isoformat(),max(1,nsi),ns,round(nc,1),new_hr,now.isoformat()))
                    na2 = pick_activity_for_hour(hour, prev_type=act["type"])
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
                conn.commit()
                person_row = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
                if person_row:
                    socketio.emit("state_update", {**dict(person_row), **upd})
            conn.close()
        except Exception as e:
            print(f"Simülasyon hatası: {e}")
            import traceback; traceback.print_exc()
        time.sleep(max(0.5, 3.0 / sim_speed))