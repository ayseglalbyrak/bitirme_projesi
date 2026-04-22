"""
Aktivite Simülasyonu v3 — Gerçekçi Sensör + Geçmiş Fake Data
pip install flask flask-cors
python app.py
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sqlite3, random, time, threading, math
from datetime import datetime, timedelta

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
DB_PATH = "simulasyon_v3.db"

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

ACTIVITIES = [
    {"name": "Uyuyor",              "name_en": "Sleeping",        "icon": "😴", "color": "#85B7EB",
     "type": "sleep",  "cal_rate": 1.0,  "step_rate": 0,
     "hr_base": 55,  "hr_noise": 5,  "spo2_base": 97, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",
     "dur_min": 360, "dur_max": 540},   # 6-9 saat
    {"name": "Kahvaltı yapıyor",    "name_en": "Having breakfast","icon": "🍳", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 8.0,  "step_rate": 0,
     "hr_base": 72,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",
     "dur_min": 20,  "dur_max": 40},
    {"name": "Egzersiz yapıyor",    "name_en": "Exercising",      "icon": "🏃", "color": "#534AB7",
     "type": "active", "cal_rate": 9.5,  "step_rate": 20,
     "hr_base": 145, "hr_noise": 15, "spo2_base": 96, "skin_temp": 37.4,
     "mood": "enerjik",     "location": "dışarı",
     "dur_min": 30,  "dur_max": 60},
    {"name": "Çalışıyor",           "name_en": "Working",         "icon": "💻", "color": "#534AB7",
     "type": "active", "cal_rate": 2.2,  "step_rate": 0,
     "hr_base": 78,  "hr_noise": 6,  "spo2_base": 98, "skin_temp": 36.4,
     "mood": "odaklanmış",  "location": "ofis",
     "dur_min": 60,  "dur_max": 180},
    {"name": "Televizyon izliyor",  "name_en": "Watching TV",     "icon": "📺", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.2,  "step_rate": 0,
     "hr_base": 65,  "hr_noise": 5,  "spo2_base": 98, "skin_temp": 36.3,
     "mood": "rahat",       "location": "ev",
     "dur_min": 30,  "dur_max": 120},
    {"name": "Yemek yiyor",         "name_en": "Eating",          "icon": "🍽️", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 7.0,  "step_rate": 0,
     "hr_base": 75,  "hr_noise": 7,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",
     "dur_min": 20,  "dur_max": 45},
    {"name": "Yürüyüşe çıkıyor",    "name_en": "Walking outside", "icon": "🚶", "color": "#534AB7",
     "type": "active", "cal_rate": 5.0,  "step_rate": 13,
     "hr_base": 95,  "hr_noise": 10, "spo2_base": 98, "skin_temp": 36.7,
     "mood": "keyifli",     "location": "dışarı",
     "dur_min": 20,  "dur_max": 60},
    {"name": "Okuyuyor",            "name_en": "Reading",         "icon": "📖", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.1,  "step_rate": 0,
     "hr_base": 63,  "hr_noise": 4,  "spo2_base": 99, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",
     "dur_min": 20,  "dur_max": 60},
    {"name": "Telefonda konuşuyor", "name_en": "On the phone",    "icon": "📱", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.3,  "step_rate": 2,
     "hr_base": 80,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.4,
     "mood": "meşgul",      "location": "ev",
     "dur_min": 10,  "dur_max": 30},
    {"name": "Alışverişe gidiyor",  "name_en": "Shopping",        "icon": "🛍️", "color": "#534AB7",
     "type": "active", "cal_rate": 4.0,  "step_rate": 9,
     "hr_base": 90,  "hr_noise": 10, "spo2_base": 98, "skin_temp": 36.6,
     "mood": "keyifli",     "location": "dışarı",
     "dur_min": 30,  "dur_max": 90},
    {"name": "Dinleniyor",          "name_en": "Resting",         "icon": "🛋️", "color": "#5DCAA5",
     "type": "rest",   "cal_rate": 1.0,  "step_rate": 0,
     "hr_base": 62,  "hr_noise": 4,  "spo2_base": 99, "skin_temp": 36.2,
     "mood": "sakin",       "location": "ev",
     "dur_min": 15,  "dur_max": 45},
    {"name": "Pişiriyor",           "name_en": "Cooking",         "icon": "👨‍🍳", "color": "#EF9F27",
     "type": "meal",   "cal_rate": 3.0,  "step_rate": 3,
     "hr_base": 82,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.5,
     "mood": "mutlu",       "location": "ev",
     "dur_min": 20,  "dur_max": 45},
    {"name": "Meditasyon yapıyor",  "name_en": "Meditating",      "icon": "🧘", "color": "#9FE1CB",
     "type": "rest",   "cal_rate": 0.9,  "step_rate": 0,
     "hr_base": 58,  "hr_noise": 3,  "spo2_base": 99, "skin_temp": 36.1,
     "mood": "huzurlu",     "location": "ev",
     "dur_min": 15,  "dur_max": 40},
    {"name": "Bisiklet sürüyor",    "name_en": "Cycling",         "icon": "🚴", "color": "#534AB7",
     "type": "active", "cal_rate": 8.5,  "step_rate": 5,
     "hr_base": 135, "hr_noise": 18, "spo2_base": 96, "skin_temp": 37.2,
     "mood": "enerjik",     "location": "dışarı",
     "dur_min": 30,  "dur_max": 75},
    {"name": "Dans ediyor",         "name_en": "Dancing",         "icon": "💃", "color": "#F4C0D1",
     "type": "active", "cal_rate": 7.0,  "step_rate": 10,
     "hr_base": 120, "hr_noise": 15, "spo2_base": 97, "skin_temp": 37.1,
     "mood": "neşeli",      "location": "ev",
     "dur_min": 20,  "dur_max": 45},
    {"name": "Yoga yapıyor",        "name_en": "Doing yoga",      "icon": "🤸", "color": "#9FE1CB",
     "type": "active", "cal_rate": 4.0,  "step_rate": 1,
     "hr_base": 80,  "hr_noise": 8,  "spo2_base": 98, "skin_temp": 36.6,
     "mood": "huzurlu",     "location": "ev",
     "dur_min": 20,  "dur_max": 50},
]

ANOMALY_RULES = [
    {"metric": "heart_rate",  "threshold": 160, "direction": "above",
     "message_tr": "Kalp atışı kritik seviyede yüksek", "message_en": "Heart rate critically high", "severity": "critical"},
    {"metric": "heart_rate",  "threshold": 45,  "direction": "below",
     "message_tr": "Kalp atışı çok düşük",             "message_en": "Heart rate too low", "severity": "warning"},
    {"metric": "spo2",        "threshold": 93,  "direction": "below",
     "message_tr": "Oksijen doygunluğu düşük",         "message_en": "Oxygen saturation low", "severity": "critical"},
    {"metric": "skin_temp",   "threshold": 38.0,"direction": "above",
     "message_tr": "Vücut sıcaklığı yüksek (ateş?)",  "message_en": "Body temperature elevated (fever?)", "severity": "warning"},
    {"metric": "steps",       "threshold": 15000,"direction": "above",
     "message_tr": "Adım sayısı çok yüksek",           "message_en": "Step count too high", "severity": "info"},
    {"metric": "calories",    "threshold": 3500, "direction": "above",
     "message_tr": "Kalori tüketimi çok yüksek",       "message_en": "Calorie intake too high", "severity": "info"},
    {"metric": "active_mins", "threshold": 200,  "direction": "above",
     "message_tr": "Aktif süre çok uzun",              "message_en": "Active duration too long", "severity": "warning"},
    {"metric": "active_mins", "threshold": 10,   "direction": "below",
     "message_tr": "Gün boyu hareketsiz",              "message_en": "Inactive all day", "severity": "info"},
    {"metric": "screen_mins", "threshold": 300,  "direction": "above",
     "message_tr": "Ekran süresi çok fazla",           "message_en": "Too much screen time", "severity": "info"},
    {"metric": "stress_level","threshold": 80,   "direction": "above",
     "message_tr": "Stres seviyesi çok yüksek",        "message_en": "Stress level very high", "severity": "warning"},
    {"metric": "hrv",         "threshold": 15,   "direction": "below",
     "message_tr": "Kalp ritmi değişkenliği düşük",    "message_en": "Low heart rate variability", "severity": "warning"},
]

AVATAR_COLORS = ["#CECBF6","#9FE1CB","#F5C4B3","#F4C0D1","#B5D4F4","#C0DD97","#FAC775","#F7C1C1"]

LOCATIONS = {
    "ev":     {"lat_base": 41.015, "lng_base": 28.979},
    "ofis":   {"lat_base": 41.042, "lng_base": 28.986},
    "dışarı": {"lat_base": 41.025, "lng_base": 28.975},
}

WEATHER_CONDITIONS = [
    {"condition": "Güneşli",         "condition_en": "Sunny",        "icon": "☀️",  "temp_range": (20, 32)},
    {"condition": "Parçalı bulutlu", "condition_en": "Partly cloudy","icon": "⛅",  "temp_range": (18, 27)},
    {"condition": "Bulutlu",         "condition_en": "Cloudy",       "icon": "☁️",  "temp_range": (15, 22)},
    {"condition": "Yağmurlu",        "condition_en": "Rainy",        "icon": "🌧️", "temp_range": (12, 18)},
    {"condition": "Rüzgarlı",        "condition_en": "Windy",        "icon": "💨",  "temp_range": (10, 20)},
]

current_weather = random.choice(WEATHER_CONDITIONS)
current_temp    = random.uniform(*current_weather["temp_range"])
weather_tick    = 0
activity_start_times = {}
sim_speed = 1  # 1x, 2x, 5x  # pid -> iso start string


# ── DB ────────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, age INTEGER, city TEXT,
        sleep_score INTEGER DEFAULT 7,
        avatar_color TEXT DEFAULT '#CECBF6',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1,
        anomaly_hr_threshold INTEGER DEFAULT 130,
        anomaly_stress_threshold INTEGER DEFAULT 75,
        health_profile TEXT DEFAULT 'balanced')""")
    c.execute("""CREATE TABLE IF NOT EXISTS current_state (
        person_id INTEGER PRIMARY KEY,
        activity_name TEXT, activity_name_en TEXT,
        activity_icon TEXT, activity_type TEXT, activity_color TEXT,
        steps INTEGER DEFAULT 0, active_mins INTEGER DEFAULT 0,
        calories REAL DEFAULT 0, screen_mins INTEGER DEFAULT 0,
        since_mins INTEGER DEFAULT 0, duration INTEGER DEFAULT 10,
        progress INTEGER DEFAULT 0, out_count INTEGER DEFAULT 0, meal_count INTEGER DEFAULT 0,
        heart_rate INTEGER DEFAULT 70, heart_rate_prev INTEGER DEFAULT 70,
        spo2 REAL DEFAULT 98.0, skin_temp REAL DEFAULT 36.5,
        hrv INTEGER DEFAULT 45, stress_level INTEGER DEFAULT 30,
        latitude REAL DEFAULT 41.015, longitude REAL DEFAULT 28.979,
        location_name TEXT DEFAULT 'ev', mood TEXT DEFAULT 'sakin',
        chart_active INTEGER DEFAULT 0, chart_rest INTEGER DEFAULT 0,
        chart_meal INTEGER DEFAULT 0, chart_sleep INTEGER DEFAULT 8,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS sensor_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        heart_rate INTEGER, spo2 REAL, skin_temp REAL, hrv INTEGER,
        stress_level INTEGER, steps INTEGER, calories REAL,
        activity_name TEXT, activity_type TEXT,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        activity_name TEXT, activity_name_en TEXT,
        activity_icon TEXT, activity_type TEXT,
        start_time TEXT, end_time TEXT, duration_mins INTEGER DEFAULT 0,
        steps_snap INTEGER DEFAULT 0, calories_snap REAL DEFAULT 0,
        heart_rate_avg INTEGER DEFAULT 0,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        message_tr TEXT, message_en TEXT,
        metric TEXT, value REAL, severity TEXT DEFAULT 'info',
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS weather_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition TEXT, condition_en TEXT, icon TEXT, temp REAL,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS smart_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER,
        alert_type TEXT, message_tr TEXT, message_en TEXT,
        severity TEXT DEFAULT 'info',
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES persons(id))""")
    # Migration: eski DB'lere sütun ekle
    for tbl, col in [
        ("activity_log", "start_time TEXT"),
        ("activity_log", "end_time TEXT"),
        ("activity_log", "duration_mins INTEGER DEFAULT 0"),
        ("activity_log", "heart_rate_avg INTEGER DEFAULT 0"),
        ("persons", "anomaly_hr_threshold INTEGER DEFAULT 130"),
        ("persons", "anomaly_stress_threshold INTEGER DEFAULT 75"),
        ("persons", "health_profile TEXT DEFAULT 'balanced'"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except:
            pass
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── HESAPLAMALAR ──────────────────────────────────────────────────────────────

def smooth(old, new, alpha=0.3):
    return old + alpha * (new - old)

def noisy(base, noise, min_v=None, max_v=None):
    v = base + random.gauss(0, noise)
    if min_v is not None: v = max(min_v, v)
    if max_v is not None: v = min(max_v, v)
    return v

def compute_hrv(hr, stress):
    base = 70 - (stress * 0.5) - (abs(hr - 65) * 0.3)
    return max(8, min(95, int(noisy(base, 6))))

def compute_stress(activity_type, hr, since_mins):
    base = {"active": 55, "meal": 25, "rest": 20, "sleep": 10}.get(activity_type, 30)
    hr_factor   = max(0, (hr - 80) * 0.4)
    time_factor = min(20, since_mins * 0.3) if activity_type == "active" else 0
    return max(5, min(99, int(noisy(base + hr_factor + time_factor, 8))))

def jitter_location(base_lat, base_lng, activity_type):
    radius = 0.005 if activity_type == "active" else (0.0005 if activity_type in ["rest","sleep","meal"] else 0.001)
    angle  = random.uniform(0, 2 * math.pi)
    dist   = random.uniform(0, radius)
    return base_lat + dist * math.cos(angle), base_lng + dist * math.sin(angle)

def compute_health_score(sleep_mins, active_mins, avg_stress, avg_hr, spo2):
    """
    Günlük sağlık skoru 0-100:
    - Uyku: 7-9 saat ideal → 30 puan
    - Aktif süre: >=30dk → 25 puan
    - Stres: düşükse → 20 puan
    - Nabız: 60-100 arası → 15 puan
    - SpO2: >=96 → 10 puan
    """
    sleep_h = sleep_mins / 60
    sleep_score = 30 if 7 <= sleep_h <= 9 else (20 if 6 <= sleep_h < 7 else (10 if sleep_h > 0 else 0))
    active_score = 25 if active_mins >= 30 else int((active_mins / 30) * 25)
    stress_score = int((1 - min(avg_stress, 100) / 100) * 20)
    hr_score = 15 if 60 <= avg_hr <= 100 else (8 if avg_hr > 0 else 0)
    spo2_score = 10 if spo2 >= 96 else (5 if spo2 >= 93 else 0)
    return min(100, sleep_score + active_score + stress_score + hr_score + spo2_score)


def pick_activity_for_hour(hour, prev_type=None):
    """Saat bazlı gerçekçi aktivite seçimi"""
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
    total, r, cumul = sum(weights), random.uniform(0, sum(weights)), 0
    for a, w in zip(pool, weights):
        cumul += w
        if r <= cumul:
            return a
    return random.choice(pool)


# ── GEÇMİŞE DÖNÜK FAKE DATA ──────────────────────────────────────────────────

def seed_historical_data(conn, pid, days_back=14):
    """
    Kişi için son N günün gerçekçi aktivite ve sensör verilerini üretir.
    Her kişiye özgü rastgele uyku/uyku ritmi ve aktivite profili atanır.
    """
    c = conn.cursor()
    # Zaten veri var mı?
    existing = c.execute(
        "SELECT COUNT(*) as n FROM activity_log WHERE person_id=?", (pid,)
    ).fetchone()["n"]
    if existing > 0:
        return

    print(f"  Kişi {pid} için {days_back} günlük geçmiş veri üretiliyor...")

    # Kişiye özgü profil
    sleep_hour_base  = random.uniform(22.0, 24.0)   # Uyku saati (saat.dakika cinsinden)
    wake_hour_base   = random.uniform(6.0,  8.5)    # Uyanma saati
    exercise_days    = random.sample(range(7), random.randint(3, 6))  # Hangi günler egzersiz
    is_morning_person = random.random() > 0.5

    now = datetime.now()

    for day_offset in range(days_back - 1, -1, -1):
        day_start = (now - timedelta(days=day_offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        weekday = day_start.weekday()  # 0=Pzt, 6=Paz

        # O günün aktivite zaman çizelgesini oluştur
        cursor_time = day_start.replace(hour=6, minute=random.randint(0, 30))

        # Uyku: bir önceki gece 22:00 - 06:30 arası
        sleep_start_hour = sleep_hour_base + random.gauss(0, 0.4)
        sleep_start_hour = max(21, min(25, sleep_start_hour))
        wake_hour = wake_hour_base + random.gauss(0, 0.3)
        wake_hour = max(5.5, min(9.0, wake_hour))
        sleep_duration_h = wake_hour + (24 - sleep_start_hour if sleep_start_hour >= 24 else 0) + (wake_hour if sleep_start_hour >= 24 else wake_hour - (sleep_start_hour if sleep_start_hour < 24 else sleep_start_hour - 24))

        # Uyku kaydı (önceki günden başlar)
        sl_start = day_start - timedelta(hours=24 - sleep_start_hour % 24)
        sl_dur   = int((wake_hour + (24 - sleep_start_hour % 24)) * 60)
        sl_dur   = max(240, min(600, sl_dur))
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

        # Sensör logu: uyku süresince her 30 dakikada bir
        t_cur = sl_start
        while t_cur < sl_end:
            c.execute("""INSERT INTO sensor_log
                (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,
                 int(noisy(sl_act["hr_base"], sl_act["hr_noise"], 40, 75)),
                 round(noisy(sl_act["spo2_base"], 0.3, 90, 100), 1),
                 round(noisy(sl_act["skin_temp"], 0.1, 35, 38), 2),
                 compute_hrv(sl_hr, 10),
                 random.randint(5, 15),
                 0, 0,
                 sl_act["name"], sl_act["type"],
                 t_cur.isoformat()))
            t_cur += timedelta(minutes=30)

        # Gündüz aktiviteleri
        cursor_time = sl_end + timedelta(minutes=random.randint(5, 15))
        cumul_steps = 0
        cumul_cal   = sl_dur * sl_act["cal_rate"]
        prev_type   = "sleep"

        day_end = day_start.replace(hour=22, minute=30)

        while cursor_time < day_end:
            act = pick_activity_for_hour(cursor_time.hour, prev_type)
            dur = random.randint(act["dur_min"], act["dur_max"])

            # Hafta sonu daha uzun uyku/dinlenme
            if weekday >= 5 and act["type"] in ["rest", "sleep"]:
                dur = int(dur * 1.3)

            end_time = cursor_time + timedelta(minutes=dur)
            if end_time > day_end:
                dur = max(5, int((day_end - cursor_time).seconds / 60))
                end_time = day_end

            hr_avg  = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
            steps   = int(act["step_rate"] * dur * (0.85 + random.random() * 0.3))
            cal     = round(act["cal_rate"] * dur * (0.85 + random.random() * 0.3), 1)
            cumul_steps += steps
            cumul_cal   += cal

            c.execute("""INSERT INTO activity_log
                (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                 start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, act["name"], act["name_en"], act["icon"], act["type"],
                 cursor_time.isoformat(), end_time.isoformat(), dur,
                 cumul_steps, round(cumul_cal, 1), hr_avg, end_time.isoformat()))

            # Sensör logu: aktivite başı, ortası, sonu
            for offset_pct in [0, 0.5, 1.0]:
                t_log = cursor_time + timedelta(minutes=int(dur * offset_pct))
                stress = compute_stress(act["type"], hr_avg, int(dur * offset_pct))
                c.execute("""INSERT INTO sensor_log
                    (person_id,heart_rate,spo2,skin_temp,hrv,stress_level,steps,calories,activity_name,activity_type,recorded_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid,
                     int(noisy(act["hr_base"], act["hr_noise"], 40, 200)),
                     round(noisy(act["spo2_base"], 0.3, 90, 100), 1),
                     round(noisy(act["skin_temp"], 0.15, 35, 40), 2),
                     compute_hrv(hr_avg, stress),
                     stress,
                     cumul_steps, round(cumul_cal, 1),
                     act["name"], act["type"],
                     t_log.isoformat()))

            prev_type   = act["type"]
            cursor_time = end_time + timedelta(minutes=random.randint(2, 8))

    conn.commit()
    print(f"  Kişi {pid} için geçmiş veri tamamlandı.")


# ── AKILLI UYARILAR ───────────────────────────────────────────────────────────

def check_smart_alerts(conn):
    """
    Tüm kişiler için önleyici akıllı uyarıları kontrol et ve kaydet.
    Her saat bir kez çalışır.
    """
    c = conn.cursor()
    persons = c.execute("SELECT id, name FROM persons WHERE active=1").fetchall()
    now = datetime.now()

    for p in persons:
        pid  = p["id"]
        name = p["name"]

        # Son 3 günde hiç egzersiz yok mu?
        ex_count = c.execute("""
            SELECT COUNT(*) as n FROM activity_log
            WHERE person_id=? AND activity_type='active'
              AND start_time >= datetime('now','-3 days')
        """, (pid,)).fetchone()["n"]

        if ex_count == 0:
            _insert_alert(c, pid, "no_exercise_3d",
                "3 gündür aktif aktivite yok",
                "No active activity for 3 days", "warning", now)

        # Uyku saati düzensizliği (son 5 günde)
        sleep_starts = c.execute("""
            SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-5 days')
            ORDER BY start_time DESC LIMIT 5
        """, (pid,)).fetchall()

        if len(sleep_starts) >= 3:
            hours = []
            for row in sleep_starts:
                try:
                    h = datetime.fromisoformat(row["start_time"]).hour
                    hours.append(h)
                except:
                    pass
            if hours:
                spread = max(hours) - min(hours)
                if spread >= 3:
                    _insert_alert(c, pid, "irregular_sleep",
                        f"Uyku saatinde {spread} saatlik düzensizlik tespit edildi",
                        f"Sleep schedule irregularity of {spread} hours detected", "warning", now)

        # Uyku borcu (son 3 gün ortalaması 6 saatten az)
        sleep_avg = c.execute("""
            SELECT AVG(duration_mins) as avg_dur FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-3 days')
        """, (pid,)).fetchone()["avg_dur"]

        if sleep_avg and sleep_avg < 360:
            deficit = round((360 - sleep_avg) / 60, 1)
            _insert_alert(c, pid, "sleep_debt",
                f"Günlük uyku ortalaması {round(sleep_avg/60,1)} saat — {deficit} saat uyku borcu var",
                f"Daily sleep avg {round(sleep_avg/60,1)}h — {deficit}h sleep debt", "warning", now)

        # Yüksek stres trendi (son 2 gün)
        stress_avg = c.execute("""
            SELECT AVG(stress_level) as avg_s FROM sensor_log
            WHERE person_id=? AND recorded_at >= datetime('now','-2 days')
        """, (pid,)).fetchone()["avg_s"]

        if stress_avg and stress_avg > 65:
            _insert_alert(c, pid, "high_stress_trend",
                f"Son 2 günde ortalama stres seviyesi yüksek ({round(stress_avg,0)}/100)",
                f"High avg stress over last 2 days ({round(stress_avg,0)}/100)", "warning", now)

    conn.commit()


def _insert_alert(c, pid, alert_type, msg_tr, msg_en, severity, now):
    """Son 6 saatte aynı tipte uyarı yoksa ekle"""
    exists = c.execute("""
        SELECT id FROM smart_alerts
        WHERE person_id=? AND alert_type=?
          AND datetime(detected_at) > datetime('now','-6 hours')
    """, (pid, alert_type)).fetchone()
    if not exists:
        c.execute("""INSERT INTO smart_alerts
            (person_id,alert_type,message_tr,message_en,severity,detected_at)
            VALUES (?,?,?,?,?,?)""",
            (pid, alert_type, msg_tr, msg_en, severity, now.isoformat()))
        socketio.emit("smart_alert", {
            "person_id":   pid,
            "alert_type":  alert_type,
            "message_tr":  msg_tr,
            "severity":    severity,
            "detected_at": now.isoformat(),
        })


# ── SİMÜLASYON DÖNGÜSÜ ───────────────────────────────────────────────────────

def check_anomalies(pid, s, conn):
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
                     rule["metric"], round(val, 1), rule["severity"],
                     datetime.now().isoformat()))
                # Anomaliyi anlık gönder
                socketio.emit("anomaly", {
                    "person_id":   pid,
                    "message_tr":  rule["message_tr"],
                    "message_en":  rule["message_en"],
                    "metric":      rule["metric"],
                    "value":       round(val, 1),
                    "severity":    rule["severity"],
                    "detected_at": datetime.now().isoformat(),
                })


def simulation_loop():
    global current_weather, current_temp, weather_tick
    tick         = 0
    alert_tick   = 0   # akıllı uyarı sayacı (her 1200 tick = ~1 saat)

    while True:
        try:
            conn = get_db()
            c    = conn.cursor()
            now  = datetime.now()
            hour = now.hour

            # Hava durumu değişimi
            weather_tick += 1
            if weather_tick >= 200:
                weather_tick    = 0
                current_weather = random.choice(WEATHER_CONDITIONS)
                current_temp    = random.uniform(*current_weather["temp_range"])
                c.execute("INSERT INTO weather_log (condition,condition_en,icon,temp) VALUES (?,?,?,?)",
                    (current_weather["condition"], current_weather["condition_en"],
                     current_weather["icon"], round(current_temp, 1)))

            # Akıllı uyarılar (her ~60 dakikada bir)
            alert_tick += 1
            if alert_tick >= 1200:
                alert_tick = 0
                check_smart_alerts(conn)

            persons = c.execute("SELECT id FROM persons WHERE active=1").fetchall()

            for row in persons:
                pid = row["id"]
                st  = c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone()

                if st is None:
                    act = pick_activity_for_hour(hour)
                    loc = LOCATIONS.get(act["location"], LOCATIONS["ev"])
                    lat, lng = jitter_location(loc["lat_base"], loc["lng_base"], act["type"])
                    hr  = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
                    hrv = compute_hrv(hr, 30)
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
                         hrv, 30, lat, lng, act["location"], act["mood"],
                         now.isoformat()))
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

                prev_hr    = s["heart_rate"]
                new_hr     = int(smooth(prev_hr, noisy(act["hr_base"], act["hr_noise"], 40, 200), alpha=0.15))
                new_spo2   = round(smooth(s["spo2"],      noisy(act["spo2_base"], 0.3, 90, 100), 0.1), 1)
                new_temp   = round(smooth(s["skin_temp"], noisy(act["skin_temp"], 0.15, 35, 40), 0.08), 2)
                new_stress = compute_stress(act["type"], new_hr, nsi)
                new_hrv    = compute_hrv(new_hr, new_stress)

                loc      = LOCATIONS.get(act["location"], LOCATIONS["ev"])
                new_lat, new_lng = jitter_location(loc["lat_base"], loc["lng_base"], act["type"])
                if s["location_name"] == act["location"]:
                    new_lat = smooth(s["latitude"],  new_lat, 0.05 if act["type"] == "active" else 0.01)
                    new_lng = smooth(s["longitude"], new_lng, 0.05 if act["type"] == "active" else 0.01)

                oc  = s["out_count"]
                mc  = s["meal_count"]
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

                    start_t  = activity_start_times.get(pid, now.isoformat())
                    end_t    = now.isoformat()
                    dur_mins = max(1, nsi)

                    c.execute("""INSERT INTO activity_log
                        (person_id,activity_name,activity_name_en,activity_icon,activity_type,
                         start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid, act["name"], act["name_en"], act["icon"], act["type"],
                         start_t, end_t, dur_mins,
                         ns, round(nc, 1), new_hr, end_t))

                    na2 = pick_activity_for_hour(hour, prev_type=act["type"])
                    dur = random.randint(na2["dur_min"], na2["dur_max"])
                    if act["type"] == "sleep":
                        dur = random.randint(360, 540)

                    activity_start_times[pid] = now.isoformat()

                    c.execute("""UPDATE current_state SET
                        activity_name=?,activity_name_en=?,activity_icon=?,activity_type=?,activity_color=?,
                        steps=?,active_mins=?,calories=?,screen_mins=?,since_mins=0,duration=?,progress=0,
                        out_count=?,meal_count=?,heart_rate=?,heart_rate_prev=?,spo2=?,skin_temp=?,hrv=?,stress_level=?,
                        latitude=?,longitude=?,location_name=?,mood=?,
                        chart_active=?,chart_rest=?,chart_meal=?,chart_sleep=?,updated_at=?
                        WHERE person_id=?""",
                        (na2["name"], na2["name_en"], na2["icon"], na2["type"], na2["color"],
                         ns, na, round(nc, 1), nsc, dur, oc, mc, new_hr, prev_hr,
                         new_spo2, new_temp, new_hrv, new_stress,
                         round(new_lat, 6), round(new_lng, 6), na2["location"], na2["mood"],
                         ca, cr, cm, csl, now.isoformat(), pid))
                else:
                    c.execute("""UPDATE current_state SET
                        steps=?,active_mins=?,calories=?,screen_mins=?,since_mins=?,progress=?,
                        heart_rate=?,heart_rate_prev=?,spo2=?,skin_temp=?,hrv=?,stress_level=?,
                        latitude=?,longitude=?,location_name=?,mood=?,
                        chart_active=?,chart_rest=?,chart_meal=?,chart_sleep=?,updated_at=?
                        WHERE person_id=?""",
                        (ns, na, round(nc, 1), nsc, nsi, np_, new_hr, prev_hr,
                         new_spo2, new_temp, new_hrv, new_stress,
                         round(new_lat, 6), round(new_lng, 6), act["location"], act["mood"],
                         ca, cr, cm, csl, now.isoformat(), pid))

                conn.commit()
                upd = dict(c.execute("SELECT * FROM current_state WHERE person_id=?", (pid,)).fetchone())
                check_anomalies(pid, upd, conn)
                conn.commit()

                # WebSocket ile anlık güncelleme gönder
                person_row = conn.execute(
                    "SELECT * FROM persons WHERE id=?", (pid,)
                ).fetchone()
                if person_row:
                    merged = {**dict(person_row), **upd}
                    socketio.emit("state_update", merged)

            conn.close()
        except Exception as e:
            print(f"Simülasyon hatası: {e}")
            import traceback; traceback.print_exc()
        time.sleep(max(0.5, 3.0 / sim_speed))


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/persons", methods=["GET"])
def get_persons():
    conn = get_db()
    r = conn.execute("SELECT * FROM persons WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(x) for x in r])

@app.route("/api/persons", methods=["POST"])
def add_person():
    d     = request.json
    name  = d.get("name", "").strip()
    if not name: return jsonify({"error": "İsim zorunlu"}), 400
    color = d.get("avatar_color", random.choice(AVATAR_COLORS))
    conn  = get_db(); c = conn.cursor()
    c.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
              (name, d.get("age", random.randint(20, 60)),
               d.get("city", "").strip(), random.randint(5, 10), color))
    conn.commit()
    pid = c.lastrowid
    # Yeni kişi için hemen geçmiş veri üret
    seed_historical_data(conn, pid, days_back=14)
    conn.close()
    return jsonify({"id": pid, "name": name, "avatar_color": color}), 201

@app.route("/api/persons/<int:pid>", methods=["PATCH"])
def update_person(pid):
    d = request.json; conn = get_db(); c = conn.cursor()
    if "avatar_color" in d:
        c.execute("UPDATE persons SET avatar_color=? WHERE id=?", (d["avatar_color"], pid))
    if "anomaly_hr_threshold" in d:
        c.execute("UPDATE persons SET anomaly_hr_threshold=? WHERE id=?", (int(d["anomaly_hr_threshold"]), pid))
    if "anomaly_stress_threshold" in d:
        c.execute("UPDATE persons SET anomaly_stress_threshold=? WHERE id=?", (int(d["anomaly_stress_threshold"]), pid))
    if "health_profile" in d:
        c.execute("UPDATE persons SET health_profile=? WHERE id=?", (d["health_profile"], pid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/persons/<int:pid>", methods=["DELETE"])
def delete_person(pid):
    conn = get_db()
    conn.execute("UPDATE persons SET active=0 WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/state", methods=["GET"])
def get_all_states():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/history/<int:pid>", methods=["GET"])
def get_history(pid):
    conn = get_db()
    rows = conn.execute("""SELECT * FROM activity_log WHERE person_id=?
        ORDER BY recorded_at DESC LIMIT 30""", (pid,)).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/sensors/<int:pid>", methods=["GET"])
def get_sensor_history(pid):
    limit = int(request.args.get("limit", 60))
    conn  = get_db()
    rows  = conn.execute("""SELECT * FROM sensor_log WHERE person_id=?
        ORDER BY recorded_at DESC LIMIT ?""", (pid, limit)).fetchall()
    conn.close()
    return jsonify(list(reversed([dict(r) for r in rows])))

@app.route("/api/anomalies", methods=["GET"])
def get_anomalies():
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.name as person_name FROM anomalies a
        JOIN persons p ON a.person_id=p.id
        ORDER BY a.detected_at DESC LIMIT 50""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/smart_alerts", methods=["GET"])
def get_smart_alerts():
    conn = get_db()
    rows = conn.execute("""SELECT sa.*,p.name as person_name FROM smart_alerts sa
        JOIN persons p ON sa.person_id=p.id
        ORDER BY sa.detected_at DESC LIMIT 100""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/compare", methods=["GET"])
def compare_persons():
    conn = get_db()
    rows = conn.execute("""SELECT p.name,p.age,p.city,p.sleep_score,p.avatar_color,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,
        cs.heart_rate,cs.spo2,cs.stress_level,cs.hrv
        FROM persons p JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY cs.steps DESC""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/summary", methods=["GET"])
def summary():
    conn  = get_db()
    total = conn.execute("SELECT COUNT(*) as n FROM persons WHERE active=1").fetchone()["n"]
    avg   = conn.execute("""SELECT ROUND(AVG(steps)) as s,ROUND(AVG(calories),1) as c,
        ROUND(AVG(active_mins)) as a,ROUND(AVG(heart_rate)) as hr,ROUND(AVG(stress_level)) as stress
        FROM current_state cs JOIN persons p ON cs.person_id=p.id WHERE p.active=1""").fetchone()
    acnt  = conn.execute("""SELECT COUNT(*) as n FROM anomalies
        WHERE datetime(detected_at)>datetime('now','-1 hour')""").fetchone()["n"]
    salrt = conn.execute("""SELECT COUNT(*) as n FROM smart_alerts
        WHERE datetime(detected_at)>datetime('now','-24 hours')""").fetchone()["n"]
    conn.close()
    return jsonify({
        "total_persons":   total,
        "avg_steps":       avg["s"]      or 0,
        "avg_calories":    avg["c"]      or 0,
        "avg_active_mins": avg["a"]      or 0,
        "avg_heart_rate":  avg["hr"]     or 0,
        "avg_stress":      avg["stress"] or 0,
        "anomaly_count":   acnt,
        "smart_alert_count": salrt,
        "weather": {
            "condition":    current_weather["condition"],
            "condition_en": current_weather["condition_en"],
            "icon":         current_weather["icon"],
            "temp":         round(current_temp, 1),
        }
    })

@app.route("/api/chart/<int:pid>", methods=["GET"])
def get_chart(pid):
    conn = get_db()
    row  = conn.execute("""SELECT p.name,p.avatar_color,cs.chart_active,cs.chart_rest,cs.chart_meal,cs.chart_sleep,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,p.sleep_score,
        cs.heart_rate,cs.spo2,cs.skin_temp,cs.hrv,cs.stress_level,cs.mood
        FROM persons p JOIN current_state cs ON p.id=cs.person_id
        WHERE p.id=? AND p.active=1""", (pid,)).fetchone()
    conn.close()
    if not row: return jsonify({"error": "Kişi bulunamadı"}), 404
    return jsonify(dict(row))

@app.route("/api/timeline/<int:pid>", methods=["GET"])
def get_timeline(pid):
    conn = get_db()
    rows = conn.execute("""SELECT activity_name,activity_name_en,activity_icon,activity_type,
        start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at
        FROM activity_log WHERE person_id=?
        AND recorded_at >= datetime('now','-7 days')
        ORDER BY recorded_at DESC LIMIT 80""", (pid,)).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/weekly/<int:pid>", methods=["GET"])
def get_weekly(pid):
    conn = get_db()
    days = []
    for i in range(6, -1, -1):
        d     = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        label = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
        row   = conn.execute("""SELECT COUNT(*) as events,
            SUM(CASE WHEN activity_type='active' THEN 1 ELSE 0 END) as active_events,
            SUM(CASE WHEN activity_type='meal'   THEN 1 ELSE 0 END) as meal_events,
            SUM(CASE WHEN activity_type='sleep'  THEN 1 ELSE 0 END) as sleep_events,
            COALESCE(MAX(steps_snap),0)    as max_steps,
            COALESCE(MAX(calories_snap),0) as max_cal,
            COALESCE(AVG(heart_rate_avg),0) as avg_hr
            FROM activity_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",
            (pid, d)).fetchone()
        days.append({"date": label, **dict(row)})
    person = conn.execute("SELECT name,sleep_score FROM persons WHERE id=?", (pid,)).fetchone()
    conn.close()
    return jsonify({"person": dict(person) if person else {}, "days": days})

@socketio.on("connect")
def on_connect():
    """Client bağlandığında tüm mevcut durumu gönder"""
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close()
    for row in rows:
        emit("state_update", dict(row))

@socketio.on("disconnect")
def on_disconnect():
    pass

@app.route("/api/avatar_colors", methods=["GET"])
def avatar_colors():
    return jsonify(AVATAR_COLORS)

@app.route("/api/export/<int:pid>", methods=["GET"])
def export_person(pid):
    from flask import Response
    import csv, io
    conn   = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404
    export_type = request.args.get("type", "activity")
    output = io.StringIO()
    if export_type == "activity":
        rows = conn.execute("""SELECT activity_name,activity_type,start_time,end_time,
            duration_mins,steps_snap,calories_snap,heart_rate_avg
            FROM activity_log WHERE person_id=? ORDER BY start_time DESC LIMIT 1000""",(pid,)).fetchall()
        writer = csv.writer(output)
        writer.writerow(["Aktivite","Tip","Baslangic","Bitis","Sure(dk)","Adim","Kalori","Ort.Nabiz"])
        for r in rows:
            writer.writerow([r["activity_name"],r["activity_type"],r["start_time"],r["end_time"],
                r["duration_mins"],r["steps_snap"],round(r["calories_snap"] or 0,1),r["heart_rate_avg"]])
        filename = person["name"]+"_aktivite.csv"
    elif export_type == "sensor":
        rows = conn.execute("""SELECT recorded_at,heart_rate,spo2,skin_temp,hrv,stress_level,
            steps,calories,activity_name,activity_type
            FROM sensor_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT 2000""",(pid,)).fetchall()
        writer = csv.writer(output)
        writer.writerow(["Zaman","Nabiz","SpO2","Sicaklik","HRV","Stres","Adim","Kalori","Aktivite","Tip"])
        for r in rows:
            writer.writerow([r["recorded_at"],r["heart_rate"],r["spo2"],r["skin_temp"],
                r["hrv"],r["stress_level"],r["steps"],round(r["calories"] or 0,1),
                r["activity_name"],r["activity_type"]])
        filename = person["name"]+"_sensor.csv"
    else:
        writer = csv.writer(output)
        writer.writerow(["Tarih","Adim","Kalori","Aktif(dk)","Uyku(dk)","Ort.Nabiz","Ort.Stres","Ort.SpO2","Etkinlik"])
        for i in range(29,-1,-1):
            d = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
            r = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
                COALESCE(MAX(calories_snap),0) as cal,
                COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as act,
                COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as slp,
                COALESCE(AVG(heart_rate_avg),0) as hr, COUNT(*) as ev
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
            s = conn.execute("""SELECT ROUND(AVG(stress_level),1) as st,ROUND(AVG(spo2),1) as sp
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
            writer.writerow([d,r["steps"],round(r["cal"] or 0,1),r["act"],r["slp"],
                round(r["hr"] or 0,1),s["st"] or 0,s["sp"] or 0,r["ev"]])
        filename = person["name"]+"_gunluk.csv"
    conn.close()
    output.seek(0)
    return Response("﻿"+output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename="+filename})

@app.route("/api/location", methods=["GET"])
def get_locations():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.avatar_color,cs.latitude,cs.longitude,
        cs.location_name,cs.activity_name,cs.activity_icon,cs.activity_type
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.active=1""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])



@app.route("/api/daily_profile/<int:pid>", methods=["GET"])
def get_daily_profile(pid):
    """
    Kişinin günlük yaşam profili karşılaştırması ve tahmini.
    Her gün için tam profil, günler arası delta, anomali tespiti, gelecek tahmini.
    """
    days_back = int(request.args.get("days", 14))
    conn      = get_db()

    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    profiles = []

    for i in range(days_back - 1, -1, -1):
        d     = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        label = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
        weekday = (datetime.now() - timedelta(days=i)).strftime("%A")
        weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                      "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

        # Uyku kaydı — uyanış ve uyku başlangıç saatleri
        sleep_rec = conn.execute("""
            SELECT start_time, end_time, duration_mins
            FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1
        """, (pid, d)).fetchone()

        wake_hour   = None
        sleep_hour  = None
        sleep_mins  = 0
        if sleep_rec:
            try:
                if sleep_rec["end_time"]:
                    end = sleep_rec["end_time"]
                    if len(end) <= 5:
                        wake_hour = int(end.split(":")[0]) + int(end.split(":")[1])/60
                    else:
                        dt = datetime.fromisoformat(end)
                        wake_hour = dt.hour + dt.minute/60
                if sleep_rec["start_time"]:
                    st2 = sleep_rec["start_time"]
                    if len(st2) <= 5:
                        sleep_hour = int(st2.split(":")[0]) + int(st2.split(":")[1])/60
                    else:
                        dt2 = datetime.fromisoformat(st2)
                        sleep_hour = dt2.hour + dt2.minute/60
                sleep_mins = sleep_rec["duration_mins"] or 0
            except:
                pass

        # İlk aktivite (uyanıştan sonraki ilk non-sleep)
        first_act = conn.execute("""
            SELECT activity_name, activity_type, start_time
            FROM activity_log
            WHERE person_id=? AND activity_type != 'sleep'
              AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1
        """, (pid, d)).fetchone()

        first_act_hour = None
        first_act_name = None
        if first_act and first_act["start_time"]:
            try:
                st3 = first_act["start_time"]
                dt3 = datetime.fromisoformat(st3) if len(st3) > 5 else None
                if dt3:
                    first_act_hour = dt3.hour + dt3.minute/60
                first_act_name = first_act["activity_name"]
            except:
                pass

        # Dışarı çıkış saati (ilk outdoor aktivite)
        outdoor = conn.execute("""
            SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='active'
              AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1
        """, (pid, d)).fetchone()

        outdoor_hour = None
        if outdoor and outdoor["start_time"]:
            try:
                ot = outdoor["start_time"]
                if len(ot) > 5:
                    dt4 = datetime.fromisoformat(ot)
                    outdoor_hour = dt4.hour + dt4.minute/60
            except:
                pass

        # Yemek saatleri
        meals = conn.execute("""
            SELECT start_time, activity_name FROM activity_log
            WHERE person_id=? AND activity_type='meal'
              AND date(start_time,'localtime')=?
            ORDER BY start_time ASC
        """, (pid, d)).fetchall()

        meal_hours = []
        for m in meals:
            try:
                mt = m["start_time"]
                if mt and len(mt) > 5:
                    dt5 = datetime.fromisoformat(mt)
                    meal_hours.append(round(dt5.hour + dt5.minute/60, 2))
            except:
                pass

        # Günlük metrikler
        metrics = conn.execute("""
            SELECT COALESCE(MAX(steps_snap),0) as steps,
                   COALESCE(MAX(calories_snap),0) as calories,
                   COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
                   COUNT(*) as event_count
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?
        """, (pid, d)).fetchone()

        sensor = conn.execute("""
            SELECT ROUND(AVG(heart_rate),1) as avg_hr,
                   ROUND(AVG(spo2),1) as avg_spo2,
                   ROUND(AVG(stress_level),1) as avg_stress,
                   ROUND(AVG(hrv),1) as avg_hrv,
                   MAX(heart_rate) as max_hr,
                   MIN(CASE WHEN heart_rate>0 THEN heart_rate END) as min_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?
        """, (pid, d)).fetchone()

        profiles.append({
            "date":          d,
            "label":         label,
            "weekday":       weekday_tr,
            # Uyku profili
            "wake_hour":     round(wake_hour, 2)  if wake_hour  is not None else None,
            "sleep_hour":    round(sleep_hour, 2) if sleep_hour is not None else None,
            "sleep_mins":    sleep_mins,
            "wake_time_str": f"{int(wake_hour):02d}:{int((wake_hour%1)*60):02d}"   if wake_hour  is not None else "—",
            "sleep_time_str":f"{int(sleep_hour):02d}:{int((sleep_hour%1)*60):02d}" if sleep_hour is not None else "—",
            # Aktivite profili
            "first_act_hour": round(first_act_hour, 2) if first_act_hour is not None else None,
            "first_act_name": first_act_name,
            "outdoor_hour":   round(outdoor_hour, 2) if outdoor_hour is not None else None,
            "meal_hours":     meal_hours,
            "meal_count":     len(meal_hours),
            # Metrikler
            "steps":       int(metrics["steps"] or 0),
            "calories":    round(float(metrics["calories"] or 0), 1),
            "active_mins": int(metrics["active_mins"] or 0),
            "event_count": int(metrics["event_count"] or 0),
            # Sensör
            "avg_hr":     float(sensor["avg_hr"] or 0),
            "avg_spo2":   float(sensor["avg_spo2"] or 0),
            "avg_stress": float(sensor["avg_stress"] or 0),
            "avg_hrv":    float(sensor["avg_hrv"] or 0),
            "max_hr":     int(sensor["max_hr"] or 0),
            "min_hr":     int(sensor["min_hr"] or 0),
        })

    # ── Delta hesabı (günler arası fark) ──────────────────────────────────────
    active_profiles = [p for p in profiles if p["event_count"] > 0]
    for i in range(1, len(active_profiles)):
        prev = active_profiles[i-1]
        curr = active_profiles[i]

        # Uyanış saati farkı (dakika)
        if curr["wake_hour"] is not None and prev["wake_hour"] is not None:
            curr["wake_delta_mins"] = round((curr["wake_hour"] - prev["wake_hour"]) * 60)
        else:
            curr["wake_delta_mins"] = None

        # Uyku saati farkı
        if curr["sleep_hour"] is not None and prev["sleep_hour"] is not None:
            curr["sleep_delta_mins"] = round((curr["sleep_hour"] - prev["sleep_hour"]) * 60)
        else:
            curr["sleep_delta_mins"] = None

        # Adım farkı
        curr["steps_delta"] = curr["steps"] - prev["steps"]

        # Aktif süre farkı
        curr["active_delta"] = curr["active_mins"] - prev["active_mins"]

        # Stres farkı
        curr["stress_delta"] = round(curr["avg_stress"] - prev["avg_stress"], 1)

    # İlk profil için delta yok
    if active_profiles:
        for key in ["wake_delta_mins","sleep_delta_mins","steps_delta","active_delta","stress_delta"]:
            if key not in active_profiles[0]:
                active_profiles[0][key] = None

    # ── Anomali tespiti ────────────────────────────────────────────────────────
    anomalies = []

    # Uyanış saati giderek gecikiyor mu? (son 4 gün)
    wake_hours_list = [p["wake_hour"] for p in active_profiles[-4:] if p["wake_hour"] is not None]
    if len(wake_hours_list) >= 3:
        diffs = [wake_hours_list[i+1] - wake_hours_list[i] for i in range(len(wake_hours_list)-1)]
        if all(d > 0.2 for d in diffs):
            total_drift = round((wake_hours_list[-1] - wake_hours_list[0]) * 60)
            anomalies.append({
                "type":    "wake_drift",
                "title":   "Uyanış Saati Giderek Gecikiyor",
                "desc":    f"Son {len(wake_hours_list)} günde uyanış saati toplam {total_drift} dakika geriledi",
                "severity":"warning",
                "icon":    "🌅"
            })

    # Adım sayısı düşüş trendi
    steps_list = [p["steps"] for p in active_profiles[-5:] if p["steps"] > 0]
    if len(steps_list) >= 4:
        first_half = sum(steps_list[:len(steps_list)//2]) / (len(steps_list)//2)
        second_half = sum(steps_list[len(steps_list)//2:]) / (len(steps_list) - len(steps_list)//2)
        if second_half < first_half * 0.8:
            drop_pct = round((1 - second_half/first_half) * 100)
            anomalies.append({
                "type":    "steps_decline",
                "title":   "Adım Sayısı Düşüyor",
                "desc":    f"Son dönem adım ortalaması %{drop_pct} azaldı ({int(first_half):,} → {int(second_half):,})",
                "severity":"info",
                "icon":    "🚶"
            })

    # Uyku düzensizliği artıyor
    sleep_list = [p["wake_hour"] for p in active_profiles if p["wake_hour"] is not None]
    if len(sleep_list) >= 5:
        spread = max(sleep_list) - min(sleep_list)
        if spread >= 2:
            anomalies.append({
                "type":    "sleep_irregularity",
                "title":   "Uyku Düzensizliği",
                "desc":    f"Uyanış saatleri {round(spread*60)} dakika aralıkta değişiyor ({min(sleep_list):.1f}h - {max(sleep_list):.1f}h)",
                "severity":"warning",
                "icon":    "😴"
            })

    # Stres artış trendi
    stress_list = [p["avg_stress"] for p in active_profiles[-4:] if p["avg_stress"] > 0]
    if len(stress_list) >= 3:
        if all(stress_list[i] < stress_list[i+1] for i in range(len(stress_list)-1)):
            anomalies.append({
                "type":    "stress_rising",
                "title":   "Stres Sürekli Artıyor",
                "desc":    f"Son {len(stress_list)} günde stres her gün arttı ({round(stress_list[0])} → {round(stress_list[-1])})",
                "severity":"warning",
                "icon":    "🧠"
            })

    # Aktif süre azalıyor
    active_list = [p["active_mins"] for p in active_profiles[-5:]]
    if len(active_list) >= 4 and max(active_list) > 0:
        recent_avg = sum(active_list[-3:]) / 3
        older_avg  = sum(active_list[:-3]) / max(1, len(active_list)-3)
        if older_avg > 20 and recent_avg < older_avg * 0.6:
            anomalies.append({
                "type":    "activity_decline",
                "title":   "Aktivite Belirgin Azaldı",
                "desc":    f"Aktif süre ortalaması {round(older_avg)} dk'dan {round(recent_avg)} dk'ya düştü",
                "severity":"warning",
                "icon":    "📉"
            })

    # ── Tahmin (gelecek 3 gün) ─────────────────────────────────────────────────
    def weighted_avg(vals, weights=None):
        vals = [v for v in vals if v is not None and v > 0]
        if not vals: return None
        if weights is None or len(weights) != len(vals):
            weights = list(range(1, len(vals)+1))
        total_w = sum(weights)
        return sum(v*w for v,w in zip(vals, weights)) / total_w

    def linear_trend(vals):
        """Basit lineer trend eğimi"""
        vals = [v for v in vals if v is not None and v > 0]
        if len(vals) < 2: return 0
        n = len(vals)
        mean_x = (n-1)/2
        mean_y = sum(vals)/n
        num   = sum((i-mean_x)*(v-mean_y) for i,v in enumerate(vals))
        denom = sum((i-mean_x)**2 for i in range(n))
        return num/denom if denom != 0 else 0

    recent = active_profiles[-7:] if len(active_profiles) >= 7 else active_profiles

    wake_vals    = [p["wake_hour"]   for p in recent if p["wake_hour"] is not None]
    sleep_vals   = [p["sleep_mins"]  for p in recent if p["sleep_mins"] > 0]
    steps_vals   = [p["steps"]       for p in recent if p["steps"] > 0]
    active_vals  = [p["active_mins"] for p in recent]
    stress_vals  = [p["avg_stress"]  for p in recent if p["avg_stress"] > 0]
    hr_vals      = [p["avg_hr"]      for p in recent if p["avg_hr"] > 0]

    wake_trend   = linear_trend(wake_vals)
    steps_trend  = linear_trend(steps_vals)
    stress_trend = linear_trend(stress_vals)

    predictions = []
    for day_ahead in range(1, 4):
        pred_date  = (datetime.now() + timedelta(days=day_ahead)).strftime("%d/%m")
        pred_wday  = (datetime.now() + timedelta(days=day_ahead)).strftime("%A")
        pred_wday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                        "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pred_wday, pred_wday)
        is_weekend = pred_wday in ["Saturday","Sunday"]

        # Ağırlıklı ortalama + trend
        base_wake   = weighted_avg(wake_vals)
        base_steps  = weighted_avg(steps_vals)
        base_stress = weighted_avg(stress_vals)
        base_sleep  = weighted_avg(sleep_vals)
        base_hr     = weighted_avg(hr_vals)

        pred_wake   = round(base_wake   + wake_trend   * day_ahead, 2) if base_wake   else None
        pred_steps  = int(  base_steps  + steps_trend  * day_ahead)    if base_steps  else None
        pred_stress = round(base_stress + stress_trend * day_ahead, 1) if base_stress else None
        pred_sleep  = round(base_sleep,  1)                             if base_sleep  else None
        pred_hr     = round(base_hr, 1)                                 if base_hr     else None

        # Hafta sonu düzeltmesi
        if is_weekend and pred_wake:
            pred_wake   = round(pred_wake + 0.5, 2)
            pred_steps  = int(pred_steps  * 0.8) if pred_steps else None

        # Tahmin güven seviyesi
        conf = "yüksek" if len(recent) >= 7 else ("orta" if len(recent) >= 4 else "düşük")

        wake_str = None
        if pred_wake is not None:
            h = max(0, min(23, int(pred_wake)))
            m = int((pred_wake % 1) * 60)
            wake_str = f"{h:02d}:{m:02d}"

        predictions.append({
            "date":        pred_date,
            "weekday":     pred_wday_tr,
            "is_weekend":  is_weekend,
            "wake_time":   wake_str,
            "steps":       max(0, pred_steps)  if pred_steps  is not None else None,
            "sleep_mins":  max(0, int(pred_sleep)) if pred_sleep is not None else None,
            "avg_stress":  max(0, min(100, pred_stress)) if pred_stress is not None else None,
            "avg_hr":      pred_hr,
            "confidence":  conf,
        })

    conn.close()
    return jsonify({
        "person":   dict(person),
        "profiles": active_profiles,
        "anomalies": anomalies,
        "predictions": predictions,
    })

@app.route("/api/analysis/<int:pid>", methods=["GET"])
def get_analysis(pid):
    days_back = int(request.args.get("days", 14))
    conn      = get_db()

    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    days_data = []
    for i in range(days_back - 1, -1, -1):
        d       = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        label   = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
        weekday = (datetime.now() - timedelta(days=i)).strftime("%A")
        weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                      "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

        summary_row = conn.execute("""
            SELECT COUNT(*) as total_events,
              SUM(CASE WHEN activity_type='active' THEN 1 ELSE 0 END) as active_count,
              SUM(CASE WHEN activity_type='meal'   THEN 1 ELSE 0 END) as meal_count,
              SUM(CASE WHEN activity_type='sleep'  THEN 1 ELSE 0 END) as sleep_count,
              SUM(CASE WHEN activity_type='rest'   THEN 1 ELSE 0 END) as rest_count,
              COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
              COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins,
              COALESCE(MAX(steps_snap),0)    as max_steps,
              COALESCE(MAX(calories_snap),0) as max_cal,
              COALESCE(AVG(heart_rate_avg),0) as avg_hr,
              COALESCE(MAX(heart_rate_avg),0) as max_hr,
              COALESCE(MIN(CASE WHEN heart_rate_avg>0 THEN heart_rate_avg END),0) as min_hr
            FROM activity_log
            WHERE person_id=? AND date(start_time,'localtime')=?
        """, (pid, d)).fetchone()

        sleep_rows = conn.execute("""
            SELECT start_time, end_time, duration_mins, heart_rate_avg
            FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND date(start_time,'localtime')=?
            ORDER BY start_time
        """, (pid, d)).fetchall()

        sleep_records = []
        for sr in sleep_rows:
            try:
                st_dt = datetime.fromisoformat(sr["start_time"]) if sr["start_time"] else None
                en_dt = datetime.fromisoformat(sr["end_time"])   if sr["end_time"]   else None
                sleep_records.append({
                    "start":         st_dt.strftime("%H:%M") if st_dt else "—",
                    "end":           en_dt.strftime("%H:%M") if en_dt else "—",
                    "duration_mins": sr["duration_mins"] or 0,
                    "hr_avg":        sr["heart_rate_avg"] or 0,
                })
            except:
                pass

        wake_time        = sleep_records[-1]["end"]   if sleep_records else None
        sleep_start_time = sleep_records[0]["start"]  if sleep_records else None

        sensor_row = conn.execute("""
            SELECT ROUND(AVG(heart_rate),1) as avg_hr,
              ROUND(AVG(spo2),1)        as avg_spo2,
              ROUND(AVG(skin_temp),2)   as avg_temp,
              ROUND(AVG(hrv),1)         as avg_hrv,
              ROUND(AVG(stress_level),1) as avg_stress,
              MIN(heart_rate)           as min_hr,
              MAX(heart_rate)           as max_hr
            FROM sensor_log
            WHERE person_id=? AND date(recorded_at,'localtime')=?
        """, (pid, d)).fetchone()

        # Isı haritası verisi: saat bazlı aktivite tipi (0-23)
        heatmap_row = []
        for h in range(24):
            row = conn.execute("""
                SELECT activity_type, COUNT(*) as cnt
                FROM sensor_log
                WHERE person_id=?
                  AND date(recorded_at,'localtime')=?
                  AND strftime('%H', recorded_at) = ?
                GROUP BY activity_type ORDER BY cnt DESC LIMIT 1
            """, (pid, d, f"{h:02d}")).fetchone()
            heatmap_row.append(row["activity_type"] if row else None)

        top_acts = conn.execute("""
            SELECT activity_name, activity_icon, activity_type, duration_mins, start_time
            FROM activity_log
            WHERE person_id=? AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 3
        """, (pid, d)).fetchall()

        sr  = dict(summary_row) if summary_row else {}
        snr = dict(sensor_row)  if sensor_row  else {}

        # Günlük sağlık skoru
        health_score = compute_health_score(
            sr.get("sleep_mins", 0),
            sr.get("active_mins", 0),
            snr.get("avg_stress", 50) or 50,
            snr.get("avg_hr", 75)     or 75,
            snr.get("avg_spo2", 97)   or 97,
        )

        days_data.append({
            "date":          d,
            "label":         label,
            "weekday":       weekday_tr,
            "total_events":  sr.get("total_events", 0),
            "active_count":  sr.get("active_count", 0),
            "meal_count":    sr.get("meal_count", 0),
            "sleep_count":   sr.get("sleep_count", 0),
            "rest_count":    sr.get("rest_count", 0),
            "active_mins":   sr.get("active_mins", 0),
            "sleep_mins":    sr.get("sleep_mins", 0),
            "steps":         sr.get("max_steps", 0),
            "calories":      round(sr.get("max_cal", 0), 1),
            "avg_hr":        snr.get("avg_hr")     or sr.get("avg_hr") or 0,
            "max_hr":        snr.get("max_hr")     or sr.get("max_hr") or 0,
            "min_hr":        snr.get("min_hr")     or sr.get("min_hr") or 0,
            "avg_spo2":      snr.get("avg_spo2", 0),
            "avg_temp":      snr.get("avg_temp", 0),
            "avg_hrv":       snr.get("avg_hrv", 0),
            "avg_stress":    snr.get("avg_stress", 0),
            "health_score":  health_score,
            "wake_time":         wake_time,
            "sleep_start_time":  sleep_start_time,
            "sleep_records":     sleep_records,
            "heatmap":           heatmap_row,
            "top_activities": [
                {
                    "name":  ta["activity_name"],
                    "icon":  ta["activity_icon"],
                    "type":  ta["activity_type"],
                    "dur":   ta["duration_mins"],
                    "start": datetime.fromisoformat(ta["start_time"]).strftime("%H:%M")
                             if ta["start_time"] else "—",
                }
                for ta in top_acts
            ],
        })

    # Kişi bazlı uyku düzensizlik skoru
    wake_hours = []
    for d in days_data:
     for r in d["sleep_records"]:
        end = r.get("end","")
        if not end or end == "—":
            continue
        try:
            # "07:37" formatı veya tam ISO string olabilir
            if len(end) <= 5:  # sadece "HH:MM"
                wake_hours.append(int(end.split(":")[0]))
            else:
                wake_hours.append(datetime.fromisoformat(end).hour)
        except:
            pass
    sleep_irregularity = round(max(wake_hours) - min(wake_hours), 1) if len(wake_hours) >= 2 else 0

    # Akıllı uyarılar
    alerts = conn.execute("""
        SELECT * FROM smart_alerts WHERE person_id=?
        ORDER BY detected_at DESC LIMIT 20
    """, (pid,)).fetchall()

    conn.close()
    return jsonify({
        "person":             dict(person),
        "days":               days_data,
        "sleep_irregularity": sleep_irregularity,
        "smart_alerts":       [dict(a) for a in alerts],
    })


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Veritabanı hazırlanıyor...")
    init_db()
    conn = get_db()

    if conn.execute("SELECT COUNT(*) as n FROM persons").fetchone()["n"] == 0:
        sample = [
            ("Ayşe Yılmaz",   34, "İstanbul"),
            ("Mehmet Kaya",   28, "Ankara"),
            ("Zeynep Arslan", 41, "İzmir"),
            ("Can Demir",     25, "İstanbul"),
            ("Elif Şahin",    36, "Bursa"),
        ]
        print("Örnek kişiler ekleniyor ve geçmiş veri üretiliyor...")
        for nm, ag, ct in sample:
            conn.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
                         (nm, ag, ct, random.randint(5, 10), random.choice(AVATAR_COLORS)))
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            seed_historical_data(conn, pid, days_back=14)
        print("Hazır.")
    else:
        # Mevcut kişiler için eksik geçmiş veriyi üret
        persons = conn.execute("SELECT id FROM persons WHERE active=1").fetchall()
        for p in persons:
            seed_historical_data(conn, p["id"], days_back=14)

    conn.close()

    # İlk akıllı uyarı kontrolü
    conn2 = get_db()
    check_smart_alerts(conn2)
    conn2.close()

    t = threading.Thread(target=simulation_loop, daemon=True)
    t.start()
    print("Simülasyon başlatıldı — http://localhost:5000")
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)