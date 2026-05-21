"""
Aktivite Simülasyonu v3 — Gerçekçi Sensör + Geçmiş Fake Data
pip install flask flask-cors
python app.py
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sqlite3, random, time, threading, math, json as _json
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
sim_speed = 1


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

    # ── Simülasyon dağılım ayarları (nabız, spo2 vb. için) ──
    c.execute("""CREATE TABLE IF NOT EXISTS distribution_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT NOT NULL UNIQUE,
        distribution TEXT DEFAULT 'normal',
        params TEXT DEFAULT '{}',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for metric, dist, params in [
        ('heart_rate','normal',     '{"mean":75,"std":10}'),
        ('spo2',      'normal',     '{"mean":97.5,"std":0.8}'),
        ('skin_temp', 'normal',     '{"mean":36.5,"std":0.2}'),
        ('hrv',       'normal',     '{"mean":45,"std":12}'),
        ('stress',    'exponential','{"scale":25,"offset":5}'),
        ('steps',     'lognormal',  '{"mean":8.2,"sigma":0.9}'),
        ('sleep_mins','triangular', '{"low":300,"mode":450,"high":560}'),
        ('active_mins','normal',    '{"mean":60,"std":25}'),
    ]:
        try:
            c.execute("INSERT OR IGNORE INTO distribution_settings (metric,distribution,params) VALUES (?,?,?)",
                      (metric, dist, params))
        except: pass

    # ── Örüntü analizi dağılım ayarları (uyanış saati, adım vb. için) ──
    c.execute("""CREATE TABLE IF NOT EXISTS pattern_dist_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT NOT NULL UNIQUE,
        distribution TEXT DEFAULT 'normal',
        params TEXT DEFAULT '{}',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for metric, dist, params in [
        ('wake_hour',       'normal',      '{"mean":7.5,  "std":0.5}'),
        ('sleep_hour',      'normal',      '{"mean":23.0, "std":0.5}'),
        ('sleep_mins',      'triangular',  '{"low":300,   "mode":450,"high":540}'),
        ('first_act_hour',  'normal',      '{"mean":8.0,  "std":0.5}'),
        ('exercise_hour',   'normal',      '{"mean":9.0,  "std":1.0}'),
        ('exercise_mins',   'exponential', '{"scale":30,  "offset":0}'),
        ('outdoor_hour',    'normal',      '{"mean":10.0, "std":1.5}'),
        ('first_meal_hour', 'normal',      '{"mean":8.0,  "std":0.5}'),
        ('last_meal_hour',  'normal',      '{"mean":19.0, "std":0.5}'),
        ('meal_count',      'poisson',     '{"lam":3}'),
        ('steps',           'lognormal',   '{"mean":8.2,  "sigma":0.8}'),
        ('calories',        'normal',      '{"mean":2000, "std":400}'),
        ('active_mins',     'normal',      '{"mean":60,   "std":20}'),
        ('avg_hr',          'normal',      '{"mean":75,   "std":10}'),
        ('avg_spo2',        'normal',      '{"mean":97.5, "std":0.8}'),
        ('avg_stress',      'exponential', '{"scale":25,  "offset":10}'),
        ('avg_hrv',         'normal',      '{"mean":45,   "std":12}'),
    ]:
        try:
            c.execute("INSERT OR IGNORE INTO pattern_dist_settings (metric,distribution,params) VALUES (?,?,?)",
                      (metric, dist, params))
        except: pass

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
    conn2 = sqlite3.connect(DB_PATH)
    init_contribution_tables(conn2)
    conn2.close()


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
    sleep_h = sleep_mins / 60
    sleep_score  = 30 if 7 <= sleep_h <= 9 else (20 if 6 <= sleep_h < 7 else (10 if sleep_h > 0 else 0))
    active_score = 25 if active_mins >= 30 else int((active_mins / 30) * 25)
    stress_score = int((1 - min(avg_stress, 100) / 100) * 20)
    hr_score     = 15 if 60 <= avg_hr <= 100 else (8 if avg_hr > 0 else 0)
    spo2_score   = 10 if spo2 >= 96 else (5 if spo2 >= 93 else 0)
    return min(100, sleep_score + active_score + stress_score + hr_score + spo2_score)


def pick_activity_for_hour(hour, prev_type=None):
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


# ── GEÇMİŞE DÖNÜK FAKE DATA ──────────────────────────────────────────────────

def seed_historical_data(conn, pid, days_back=14):
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) as n FROM activity_log WHERE person_id=?", (pid,)).fetchone()["n"] > 0:
        return
    print(f"  Kişi {pid} için {days_back} günlük geçmiş veri üretiliyor...")
    sleep_hour_base = random.uniform(22.0, 24.0)
    wake_hour_base  = random.uniform(6.0,  8.5)
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
            hr_avg = int(noisy(act["hr_base"], act["hr_noise"], 40, 200))
            steps  = int(act["step_rate"] * dur * (0.85 + random.random() * 0.3))
            cal    = round(act["cal_rate"] * dur * (0.85 + random.random() * 0.3), 1)
            cumul_steps += steps; cumul_cal += cal
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
                     cumul_steps,round(cumul_cal,1),act["name"],act["type"],t_log.isoformat()))
            prev_type   = act["type"]
            cursor_time = end_time + timedelta(minutes=random.randint(2,8))
    conn.commit()
    print(f"  Kişi {pid} için geçmiş veri tamamlandı.")


# ── AKILLI UYARILAR ───────────────────────────────────────────────────────────

def check_smart_alerts(conn):
    c = conn.cursor()
    now = datetime.now()
    for p in c.execute("SELECT id, name FROM persons WHERE active=1").fetchall():
        pid = p["id"]
        ex_count = c.execute("""SELECT COUNT(*) as n FROM activity_log
            WHERE person_id=? AND activity_type='active'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["n"]
        if ex_count == 0:
            _insert_alert(c, pid, "no_exercise_3d","3 gündür aktif aktivite yok","No active activity for 3 days","warning",now)
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
                        f"Uyku saatinde {spread} saatlik düzensizlik tespit edildi",
                        f"Sleep schedule irregularity of {spread} hours detected","warning",now)
        sleep_avg = c.execute("""SELECT AVG(duration_mins) as avg_dur FROM activity_log
            WHERE person_id=? AND activity_type='sleep'
              AND start_time >= datetime('now','-3 days')""", (pid,)).fetchone()["avg_dur"]
        if sleep_avg and sleep_avg < 360:
            deficit = round((360 - sleep_avg) / 60, 1)
            _insert_alert(c,pid,"sleep_debt",
                f"Günlük uyku ortalaması {round(sleep_avg/60,1)} saat — {deficit} saat uyku borcu var",
                f"Daily sleep avg {round(sleep_avg/60,1)}h — {deficit}h sleep debt","warning",now)
        stress_avg = c.execute("""SELECT AVG(stress_level) as avg_s FROM sensor_log
            WHERE person_id=? AND recorded_at >= datetime('now','-2 days')""", (pid,)).fetchone()["avg_s"]
        if stress_avg and stress_avg > 65:
            _insert_alert(c,pid,"high_stress_trend",
                f"Son 2 günde ortalama stres seviyesi yüksek ({round(stress_avg,0)}/100)",
                f"High avg stress over last 2 days ({round(stress_avg,0)}/100)","warning",now)
    conn.commit()


def _insert_alert(c, pid, alert_type, msg_tr, msg_en, severity, now):
    exists = c.execute("""SELECT id FROM smart_alerts WHERE person_id=? AND alert_type=?
        AND datetime(detected_at) > datetime('now','-6 hours')""", (pid, alert_type)).fetchone()
    if not exists:
        c.execute("""INSERT INTO smart_alerts (person_id,alert_type,message_tr,message_en,severity,detected_at)
            VALUES (?,?,?,?,?,?)""", (pid,alert_type,msg_tr,msg_en,severity,now.isoformat()))
        socketio.emit("smart_alert",{"person_id":pid,"alert_type":alert_type,"message_tr":msg_tr,
            "severity":severity,"detected_at":now.isoformat()})


# ── DAĞILIM FONKSİYONU ───────────────────────────────────────────────────────

def sample_distribution(dist_name, params, min_v=None, max_v=None):
    """
    Desteklenen dağılımlar:
      normal      : mean, std
      uniform     : low, high
      exponential : scale, offset
      poisson     : lam
      lognormal   : mean, sigma
      triangular  : low, mode, high
      beta        : alpha, beta, scale
    """
    import math as _math
    try:
        d = dist_name.lower()
        if d == "normal":
            v = random.gauss(params.get("mean",75), params.get("std",10))
        elif d == "uniform":
            v = random.uniform(params.get("low",60), params.get("high",90))
        elif d == "exponential":
            scale = params.get("scale",20)
            v = random.expovariate(1.0/max(scale,0.001)) + params.get("offset",0)
        elif d == "poisson":
            lam = params.get("lam",5)
            L, k, p = _math.exp(-lam), 0, 1.0
            while p > L:
                k += 1; p *= random.random()
            v = float(k - 1)
        elif d == "lognormal":
            v = random.lognormvariate(params.get("mean",4.3), params.get("sigma",0.5))
        elif d == "triangular":
            v = random.triangular(params.get("low",0), params.get("high",100), params.get("mode",50))
        elif d == "beta":
            v = random.betavariate(params.get("alpha",2), params.get("beta",5)) * params.get("scale",100)
        else:
            v = random.gauss(params.get("mean",75), params.get("std",10))
    except:
        v = params.get("mean",75) + random.gauss(0, params.get("std",10))
    if min_v is not None: v = max(min_v, v)
    if max_v is not None: v = min(max_v, v)
    return v


def get_dist_settings():
    conn = get_db()
    rows = conn.execute("SELECT metric,distribution,params FROM distribution_settings").fetchall()
    conn.close()
    result = {}
    for r in rows:
        try:
            result[r["metric"]] = {"distribution": r["distribution"], "params": _json.loads(r["params"])}
        except:
            result[r["metric"]] = {"distribution": "normal", "params": {}}
    return result

_dist_cache = {}
_dist_cache_time = 0

def get_dist_settings_cached():
    global _dist_cache, _dist_cache_time
    now_t = time.time()
    if now_t - _dist_cache_time > 60:
        _dist_cache = get_dist_settings()
        _dist_cache_time = now_t
    return _dist_cache


def get_pattern_dist_settings():
    """Örüntü analizi için metrik bazlı dağılım ayarlarını oku."""
    conn = get_db()
    rows = conn.execute("SELECT metric,distribution,params FROM pattern_dist_settings").fetchall()
    conn.close()
    result = {}
    for r in rows:
        try:
            result[r["metric"]] = {"distribution": r["distribution"], "params": _json.loads(r["params"])}
        except:
            result[r["metric"]] = {"distribution": "normal", "params": {}}
    return result

_pattern_dist_cache = {}
_pattern_dist_cache_time = 0

def get_pattern_dist_cached():
    global _pattern_dist_cache, _pattern_dist_cache_time
    now_t = time.time()
    if now_t - _pattern_dist_cache_time > 60:
        _pattern_dist_cache = get_pattern_dist_settings()
        _pattern_dist_cache_time = now_t
    return _pattern_dist_cache


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
                    (pid,rule["message_tr"],rule["message_en"],
                     rule["metric"],round(val,1),rule["severity"],datetime.now().isoformat()))
                socketio.emit("anomaly",{"person_id":pid,"message_tr":rule["message_tr"],
                    "message_en":rule["message_en"],"metric":rule["metric"],
                    "value":round(val,1),"severity":rule["severity"],"detected_at":datetime.now().isoformat()})


def simulation_loop():
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
                check_smart_alerts(conn)
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
                prev_hr = s["heart_rate"]

                # Kullanıcının seçtiği dağılımdan biyometrik değer üret
                _ds = get_dist_settings_cached()

                def _sim_sample(metric, act_base, act_noise, lo, hi):
                    cfg = _ds.get(metric)
                    if not cfg:
                        return noisy(act_base, act_noise, lo, hi)
                    dist   = cfg["distribution"]
                    params = {**cfg["params"]}
                    # Aktivite bazını dağılım parametrelerine yansıt
                    if dist == "normal":
                        user_mean      = params.get("mean", act_base)
                        params["mean"] = act_base * 0.7 + user_mean * 0.3
                        params["std"]  = params.get("std", act_noise)
                    elif dist == "uniform":
                        user_low       = params.get("low",  act_base - act_noise * 2)
                        user_high      = params.get("high", act_base + act_noise * 2)
                        shift          = act_base - (user_low + user_high) / 2
                        params["low"]  = user_low  + shift * 0.7
                        params["high"] = user_high + shift * 0.7
                    elif dist == "exponential":
                        params["offset"] = act_base * 0.6 + params.get("offset", 0) * 0.4
                    elif dist == "lognormal":
                        if act_base > 0:
                            params["mean"] = math.log(act_base) * 0.7 + params.get("mean", math.log(act_base)) * 0.3
                    elif dist == "triangular":
                        user_mode      = params.get("mode", act_base)
                        shift          = act_base - user_mode
                        params["low"]  = params.get("low",  act_base - 20) + shift * 0.7
                        params["mode"] = act_base * 0.7 + user_mode * 0.3
                        params["high"] = params.get("high", act_base + 20) + shift * 0.7
                    elif dist == "poisson":
                        params["lam"]  = max(1, act_base * 0.8)
                    return sample_distribution(dist, params, lo, hi)

                new_hr     = int(smooth(prev_hr,
                                _sim_sample("heart_rate", act["hr_base"],  act["hr_noise"], 40, 200),
                                alpha=0.15))
                new_spo2   = round(smooth(s["spo2"],
                                _sim_sample("spo2", act["spo2_base"], 0.5, 90, 100),
                                0.1), 1)
                new_temp   = round(smooth(s["skin_temp"],
                                _sim_sample("skin_temp", act["skin_temp"], 0.15, 35, 40),
                                0.08), 2)
                stress_base = {"active":55,"meal":25,"rest":20,"sleep":10}.get(act["type"], 30)
                new_stress  = int(smooth(s["stress_level"],
                                _sim_sample("stress", stress_base, 8, 5, 99),
                                0.2))
                new_hrv     = compute_hrv(new_hr, new_stress)

                loc = LOCATIONS.get(act["location"], LOCATIONS["ev"])
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
                    start_t = activity_start_times.get(pid, now.isoformat())
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
                check_anomalies(pid, upd, conn)
                conn.commit()
                person_row = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
                if person_row:
                    socketio.emit("state_update", {**dict(person_row), **upd})
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
    d = request.json; name = d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}), 400
    color = d.get("avatar_color", random.choice(AVATAR_COLORS))
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
              (name,d.get("age",random.randint(20,60)),d.get("city","").strip(),random.randint(5,10),color))
    conn.commit()
    pid = c.lastrowid
    seed_historical_data(conn, pid, days_back=14)
    conn.close()
    return jsonify({"id":pid,"name":name,"avatar_color":color}), 201

@app.route("/api/persons/<int:pid>", methods=["PATCH"])
def update_person(pid):
    d = request.json; conn = get_db(); c = conn.cursor()
    for field in ["avatar_color","anomaly_hr_threshold","anomaly_stress_threshold","health_profile"]:
        if field in d:
            c.execute(f"UPDATE persons SET {field}=? WHERE id=?", (d[field] if field=="avatar_color" or field=="health_profile" else int(d[field]), pid))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/persons/<int:pid>", methods=["DELETE"])
def delete_person(pid):
    conn = get_db()
    conn.execute("UPDATE persons SET active=0 WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

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
    rows = conn.execute("SELECT * FROM activity_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT 30", (pid,)).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/sensors/<int:pid>", methods=["GET"])
def get_sensor_history(pid):
    limit = int(request.args.get("limit", 60))
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM sensor_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT ?", (pid, limit)).fetchall()
    conn.close()
    return jsonify(list(reversed([dict(r) for r in rows])))

@app.route("/api/anomalies", methods=["GET"])
def get_anomalies():
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.name as person_name FROM anomalies a
        JOIN persons p ON a.person_id=p.id ORDER BY a.detected_at DESC LIMIT 50""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/smart_alerts", methods=["GET"])
def get_smart_alerts():
    conn = get_db()
    rows = conn.execute("""SELECT sa.*,p.name as person_name FROM smart_alerts sa
        JOIN persons p ON sa.person_id=p.id ORDER BY sa.detected_at DESC LIMIT 100""").fetchall()
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
    acnt  = conn.execute("SELECT COUNT(*) as n FROM anomalies WHERE datetime(detected_at)>datetime('now','-1 hour')").fetchone()["n"]
    salrt = conn.execute("SELECT COUNT(*) as n FROM smart_alerts WHERE datetime(detected_at)>datetime('now','-24 hours')").fetchone()["n"]
    conn.close()
    return jsonify({"total_persons":total,"avg_steps":avg["s"] or 0,"avg_calories":avg["c"] or 0,
        "avg_active_mins":avg["a"] or 0,"avg_heart_rate":avg["hr"] or 0,"avg_stress":avg["stress"] or 0,
        "anomaly_count":acnt,"smart_alert_count":salrt,
        "weather":{"condition":current_weather["condition"],"condition_en":current_weather["condition_en"],
            "icon":current_weather["icon"],"temp":round(current_temp,1)}})

@app.route("/api/chart/<int:pid>", methods=["GET"])
def get_chart(pid):
    conn = get_db()
    row  = conn.execute("""SELECT p.name,p.avatar_color,cs.chart_active,cs.chart_rest,cs.chart_meal,cs.chart_sleep,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,p.sleep_score,
        cs.heart_rate,cs.spo2,cs.skin_temp,cs.hrv,cs.stress_level,cs.mood
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.id=? AND p.active=1""", (pid,)).fetchone()
    conn.close()
    if not row: return jsonify({"error":"Kişi bulunamadı"}), 404
    return jsonify(dict(row))

@app.route("/api/timeline/<int:pid>", methods=["GET"])
def get_timeline(pid):
    conn = get_db()
    rows = conn.execute("""SELECT activity_name,activity_name_en,activity_icon,activity_type,
        start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at
        FROM activity_log WHERE person_id=? AND recorded_at >= datetime('now','-7 days')
        ORDER BY recorded_at DESC LIMIT 80""", (pid,)).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/weekly/<int:pid>", methods=["GET"])
def get_weekly(pid):
    conn = get_db(); days = []
    for i in range(6,-1,-1):
        d     = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        label = (datetime.now()-timedelta(days=i)).strftime("%d/%m")
        row   = conn.execute("""SELECT COUNT(*) as events,
            SUM(CASE WHEN activity_type='active' THEN 1 ELSE 0 END) as active_events,
            SUM(CASE WHEN activity_type='meal'   THEN 1 ELSE 0 END) as meal_events,
            SUM(CASE WHEN activity_type='sleep'  THEN 1 ELSE 0 END) as sleep_events,
            COALESCE(MAX(steps_snap),0) as max_steps,COALESCE(MAX(calories_snap),0) as max_cal,
            COALESCE(AVG(heart_rate_avg),0) as avg_hr
            FROM activity_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        days.append({"date":label,**dict(row)})
    person = conn.execute("SELECT name,sleep_score FROM persons WHERE id=?", (pid,)).fetchone()
    conn.close()
    return jsonify({"person":dict(person) if person else {},"days":days})

@socketio.on("connect")
def on_connect():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close()
    for row in rows:
        emit("state_update", dict(row))

@socketio.on("disconnect")
def on_disconnect():
    pass


# ── DAĞILIM API ENDPOINT'LERİ ─────────────────────────────────────────────────

@app.route("/api/distributions", methods=["GET"])
def get_distributions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM distribution_settings ORDER BY metric").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/distributions", methods=["POST"])
def update_distributions():
    items = request.json
    if not isinstance(items, list): items = [items]
    conn = get_db(); c = conn.cursor()
    for item in items:
        metric = item.get("metric","").strip()
        dist   = item.get("distribution","normal")
        params = _json.dumps(item.get("params",{}))
        if metric:
            c.execute("""INSERT INTO distribution_settings (metric,distribution,params,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(metric) DO UPDATE SET
                distribution=excluded.distribution,params=excluded.params,updated_at=excluded.updated_at""",
                (metric,dist,params,datetime.now().isoformat()))
    conn.commit(); conn.close()
    global _dist_cache_time; _dist_cache_time = 0
    return jsonify({"ok":True})

@app.route("/api/distributions/preview", methods=["POST"])
def preview_distribution():
    d = request.json
    dist   = d.get("distribution","normal")
    params = d.get("params",{})
    min_v  = d.get("min_v",None)
    max_v  = d.get("max_v",None)
    samples = [round(sample_distribution(dist,params,min_v,max_v),2) for _ in range(100)]
    mean = sum(samples)/len(samples)
    std  = (sum((x-mean)**2 for x in samples)/len(samples))**0.5
    return jsonify({"samples":samples,"mean":round(mean,2),"std":round(std,2),"min":min(samples),"max":max(samples)})


# ── ÖRÜNTÜ ANALİZİ DAĞILIM ENDPOINT'LERİ ─────────────────────────────────────

@app.route("/api/pattern_distributions", methods=["GET"])
def get_pattern_distributions():
    """
    Örüntü analizi için metrik bazlı dağılım ayarlarını döndür.
    pid parametresi varsa o kişinin verisinden parametreleri otomatik hesapla.
    """
    pid = request.args.get("pid", type=int)
    conn = get_db()
    rows = conn.execute("SELECT * FROM pattern_dist_settings ORDER BY metric").fetchall()
    result = [dict(r) for r in rows]

    if pid:
        # Kişinin son 14 günlük verisinden parametreleri hesapla
        import statistics as _stats
        computed = _compute_metric_params(conn, pid)
        for item in result:
            metric = item["metric"]
            if metric in computed:
                # Mevcut dağılıma göre hesaplanmış parametreleri ekle
                item["computed_params"] = computed[metric]

    conn.close()
    return jsonify(result)


def _compute_metric_params(conn, pid):
    """
    Kişinin son 14 günlük verisinden her metrik için
    istatistiksel parametreleri hesapla (mean, std, min, max vb.)
    """
    import statistics as _stats, math as _math
    result = {}
    now = datetime.now()

    def safe_hour(timestr):
        if not timestr: return None
        try:
            dt = datetime.fromisoformat(timestr)
            return round(dt.hour + dt.minute / 60, 2)
        except: return None

    # Her gün için veri topla
    wake_hours=[]; sleep_hours=[]; sleep_mins_list=[]
    first_act_hours=[]; exercise_hours=[]; exercise_mins_list=[]
    outdoor_hours=[]; first_meal_hours=[]; last_meal_hours=[]
    meal_counts=[]; steps_list=[]; calories_list=[]
    active_mins_list=[]; avg_hr_list=[]; avg_spo2_list=[]
    avg_stress_list=[]; avg_hrv_list=[]

    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")

        sleep_rec = conn.execute("""SELECT start_time,end_time,duration_mins FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""", (pid, d)).fetchone()
        if sleep_rec:
            wh = safe_hour(sleep_rec["end_time"])
            sh = safe_hour(sleep_rec["start_time"])
            if wh: wake_hours.append(wh)
            if sh: sleep_hours.append(sh)
            if sleep_rec["duration_mins"]: sleep_mins_list.append(sleep_rec["duration_mins"])

        first_act = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type!='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        if first_act:
            h = safe_hour(first_act["start_time"])
            if h: first_act_hours.append(h)

        exercise = conn.execute("""SELECT start_time, SUM(duration_mins) as total FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            GROUP BY date(start_time,'localtime') ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        if exercise:
            h = safe_hour(exercise["start_time"])
            if h: exercise_hours.append(h)
            if exercise["total"]: exercise_mins_list.append(int(exercise["total"]))

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

        metrics = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
            COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""", (pid, d)).fetchone()
        if metrics["steps"] > 0: steps_list.append(int(metrics["steps"]))
        if metrics["calories"] > 0: calories_list.append(float(metrics["calories"]))
        if metrics["active_mins"] > 0: active_mins_list.append(int(metrics["active_mins"]))

        sensor = conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,
            ROUND(AVG(spo2),1) as avg_spo2, ROUND(AVG(stress_level),1) as avg_stress,
            ROUND(AVG(hrv),1) as avg_hrv
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""", (pid, d)).fetchone()
        if sensor["avg_hr"]:    avg_hr_list.append(float(sensor["avg_hr"]))
        if sensor["avg_spo2"]:  avg_spo2_list.append(float(sensor["avg_spo2"]))
        if sensor["avg_stress"]:avg_stress_list.append(float(sensor["avg_stress"]))
        if sensor["avg_hrv"]:   avg_hrv_list.append(float(sensor["avg_hrv"]))

    def params_for(vals):
        """Veriden tüm dağılım parametrelerini hesapla."""
        vals = [v for v in vals if v is not None and v > 0]
        if not vals: return {}
        mean = sum(vals) / len(vals)
        std  = _stats.stdev(vals) if len(vals) > 1 else 0.1
        mn   = min(vals); mx = max(vals)
        mode = sorted(vals)[len(vals)//2]  # medyan mod yerine

        # Log-normal parametreleri
        log_vals = [_math.log(v) for v in vals if v > 0]
        log_mean = sum(log_vals)/len(log_vals) if log_vals else 0
        log_std  = _stats.stdev(log_vals) if len(log_vals) > 1 else 0.1

        # Exponential parametresi
        exp_scale = mean  # mean = 1/lambda için scale = mean

        return {
            "normal":      {"mean": round(mean,2), "std": round(max(std,0.1),2)},
            "uniform":     {"low":  round(mn,2),   "high": round(mx,2)},
            "exponential": {"scale":round(exp_scale,2), "offset": round(mn*0.5,2)},
            "poisson":     {"lam":  round(mean,1)},
            "lognormal":   {"mean": round(log_mean,3), "sigma": round(max(log_std,0.1),3)},
            "triangular":  {"low":  round(mn,2), "mode": round(mode,2), "high": round(mx,2)},
            "beta":        {"alpha": 2.0, "beta": 5.0, "scale": round(mx,2)},
        }

    data_map = {
        "wake_hour":       wake_hours,
        "sleep_hour":      sleep_hours,
        "sleep_mins":      sleep_mins_list,
        "first_act_hour":  first_act_hours,
        "exercise_hour":   exercise_hours,
        "exercise_mins":   exercise_mins_list,
        "outdoor_hour":    outdoor_hours,
        "first_meal_hour": first_meal_hours,
        "last_meal_hour":  last_meal_hours,
        "meal_count":      meal_counts,
        "steps":           steps_list,
        "calories":        calories_list,
        "active_mins":     active_mins_list,
        "avg_hr":          avg_hr_list,
        "avg_spo2":        avg_spo2_list,
        "avg_stress":      avg_stress_list,
        "avg_hrv":         avg_hrv_list,
    }

    for metric, vals in data_map.items():
        result[metric] = params_for(vals)

    return result

@app.route("/api/pattern_distributions", methods=["POST"])
def update_pattern_distributions():
    """Örüntü analizi dağılım ayarlarını güncelle."""
    items = request.json
    if not isinstance(items, list): items = [items]
    conn = get_db(); c = conn.cursor()
    for item in items:
        metric = item.get("metric","").strip()
        dist   = item.get("distribution","normal")
        params = _json.dumps(item.get("params",{}))
        if metric:
            c.execute("""INSERT INTO pattern_dist_settings (metric,distribution,params,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(metric) DO UPDATE SET
                distribution=excluded.distribution,params=excluded.params,updated_at=excluded.updated_at""",
                (metric,dist,params,datetime.now().isoformat()))
    conn.commit(); conn.close()
    global _pattern_dist_cache_time; _pattern_dist_cache_time = 0
    return jsonify({"ok":True})


@app.route("/api/avatar_colors", methods=["GET"])
def avatar_colors():
    return jsonify(AVATAR_COLORS)

@app.route("/api/export/<int:pid>", methods=["GET"])
def export_person(pid):
    from flask import Response
    import csv, io
    conn = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    export_type = request.args.get("type","activity")
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
            r = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,COALESCE(MAX(calories_snap),0) as cal,
                COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as act,
                COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as slp,
                COALESCE(AVG(heart_rate_avg),0) as hr,COUNT(*) as ev
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
            s = conn.execute("""SELECT ROUND(AVG(stress_level),1) as st,ROUND(AVG(spo2),1) as sp
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
            writer.writerow([d,r["steps"],round(r["cal"] or 0,1),r["act"],r["slp"],
                round(r["hr"] or 0,1),s["st"] or 0,s["sp"] or 0,r["ev"]])
        filename = person["name"]+"_gunluk.csv"
    conn.close(); output.seek(0)
    return Response("\ufeff"+output.getvalue(),mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename="+filename})

@app.route("/api/location", methods=["GET"])
def get_locations():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.avatar_color,cs.latitude,cs.longitude,
        cs.location_name,cs.activity_name,cs.activity_icon,cs.activity_type
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.active=1""").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])


# ── ÖRÜNTÜ ANALİZİ ────────────────────────────────────────────────────────────

@app.route("/api/pattern_analysis/<int:pid>", methods=["GET"])
def get_pattern_analysis(pid):
    """
    Kişiye özgü günlük yaşam örüntüsü analizi.
    Kullanıcının seçtiği dağılıma göre norm hesaplar.
    """
    import statistics
    days_back = int(request.args.get("days", 14))
    conn = get_db()

    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    # Dağılım ayarlarını oku — kullanıcının seçtiği dağılım
    pattern_dists = get_pattern_dist_cached()

    daily = []
    for i in range(days_back - 1, -1, -1):
        d          = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        label      = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
        weekday    = (datetime.now() - timedelta(days=i)).strftime("%A")
        is_weekend = weekday in ["Saturday", "Sunday"]
        weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                      "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)

        def safe_hour(timestr):
            if not timestr: return None
            try:
                dt = datetime.fromisoformat(timestr)
                return round(dt.hour + dt.minute / 60, 2)
            except:
                try:
                    parts = timestr.split(":")
                    return round(int(parts[0]) + int(parts[1]) / 60, 2)
                except:
                    return None

        sleep_rec = conn.execute("""SELECT start_time, end_time, duration_mins FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""", (pid, d)).fetchone()
        wake_hour  = safe_hour(sleep_rec["end_time"])   if sleep_rec else None
        sleep_hour = safe_hour(sleep_rec["start_time"]) if sleep_rec else None
        sleep_mins = sleep_rec["duration_mins"] if sleep_rec else 0

        first_act = conn.execute("""SELECT start_time, activity_name FROM activity_log
            WHERE person_id=? AND activity_type != 'sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        first_act_hour = safe_hour(first_act["start_time"]) if first_act else None
        first_act_name = first_act["activity_name"] if first_act else None

        exercise = conn.execute("""SELECT start_time, SUM(duration_mins) as total_dur FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            GROUP BY date(start_time,'localtime') ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        exercise_hour = safe_hour(exercise["start_time"]) if exercise else None
        exercise_mins = int(exercise["total_dur"] or 0) if exercise else 0

        meals = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='meal' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC""", (pid, d)).fetchall()
        meal_hours = [safe_hour(m["start_time"]) for m in meals if safe_hour(m["start_time"])]

        outdoor = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        outdoor_hour = safe_hour(outdoor["start_time"]) if outdoor else None

        metrics = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
            COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COUNT(*) as event_count
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""", (pid, d)).fetchone()

        sensor = conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,
            ROUND(AVG(spo2),1) as avg_spo2, ROUND(AVG(stress_level),1) as avg_stress,
            ROUND(AVG(hrv),1) as avg_hrv, MAX(heart_rate) as max_hr,
            MIN(CASE WHEN heart_rate>0 THEN heart_rate END) as min_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""", (pid, d)).fetchone()

        daily.append({
            "date": d, "label": label, "weekday": weekday_tr, "is_weekend": is_weekend,
            "wake_hour": wake_hour, "sleep_hour": sleep_hour, "sleep_mins": sleep_mins,
            "first_act_hour": first_act_hour, "first_act_name": first_act_name,
            "exercise_hour": exercise_hour, "exercise_mins": exercise_mins,
            "outdoor_hour": outdoor_hour, "meal_hours": meal_hours,
            "meal_count": len(meal_hours),
            "first_meal_hour": meal_hours[0] if meal_hours else None,
            "last_meal_hour":  meal_hours[-1] if meal_hours else None,
            "steps":       int(metrics["steps"] or 0),
            "calories":    round(float(metrics["calories"] or 0), 1),
            "active_mins": int(metrics["active_mins"] or 0),
            "avg_hr":      float(sensor["avg_hr"] or 0),
            "avg_spo2":    float(sensor["avg_spo2"] or 0),
            "avg_stress":  float(sensor["avg_stress"] or 0),
            "avg_hrv":     float(sensor["avg_hrv"] or 0),
            "max_hr":      int(sensor["max_hr"] or 0),
            "event_count": int(metrics["event_count"] or 0),
        })

    active = [d for d in daily if d["steps"] > 0 or d["avg_hr"] > 0]

    # ── Seçilen dağılıma göre norm hesapla ────────────────────────────────────
    def calc_norm(vals, metric=None):
        """
        Kullanıcının seçtiği dağılıma göre norm ve band hesapla.

        Normal      → ortalama ± std
        Log-Normal  → geometrik ortalama ± geometrik std
        Exponential → %10-%90 yüzdelik dilim
        Triangular  → min/max
        Uniform     → min/max
        Diğerleri   → normal yöntemi
        """
        vals = [v for v in vals if v is not None and v > 0]
        if not vals:
            return {"mean": None, "std": 0, "low": None, "high": None, "n": 0, "distribution": "normal"}
        if len(vals) < 2:
            return {"mean": vals[0], "std": 0, "low": vals[0], "high": vals[0], "n": 1, "distribution": "normal"}

        mean = sum(vals) / len(vals)
        std  = statistics.stdev(vals)

        dist_cfg = pattern_dists.get(metric, {"distribution": "normal", "params": {}}) if metric else {"distribution": "normal", "params": {}}
        dist     = dist_cfg["distribution"]

        if dist == "normal":
            low, high = mean - std, mean + std

        elif dist == "lognormal":
            import math as _m
            log_vals = [_m.log(v) for v in vals if v > 0]
            log_mean = sum(log_vals) / len(log_vals)
            log_std  = statistics.stdev(log_vals) if len(log_vals) > 1 else 0
            low      = _m.exp(log_mean - log_std)
            high     = _m.exp(log_mean + log_std)

        elif dist == "exponential":
            # %10-%90 yüzdelik dilim
            sv   = sorted(vals)
            n    = len(sv)
            low  = sv[max(0, int(n * 0.10))]
            high = sv[min(n-1, int(n * 0.90))]

        elif dist in ("triangular", "uniform"):
            low, high = min(vals), max(vals)

        elif dist == "beta":
            low  = mean - std
            high = mean + std

        else:
            low  = mean - std
            high = mean + std

        return {
            "mean":         round(mean, 2),
            "std":          round(std, 2),
            "min":          round(min(vals), 2),
            "max":          round(max(vals), 2),
            "low":          round(low, 2),
            "high":         round(high, 2),
            "n":            len(vals),
            "distribution": dist,
        }

    weekday_data = [d for d in active if not d["is_weekend"]]
    weekend_data = [d for d in active if d["is_weekend"]]

    def norms_for(data):
        return {
            "wake_hour":       calc_norm([d["wake_hour"]       for d in data], "wake_hour"),
            "sleep_hour":      calc_norm([d["sleep_hour"]      for d in data], "sleep_hour"),
            "sleep_mins":      calc_norm([d["sleep_mins"]      for d in data], "sleep_mins"),
            "first_act_hour":  calc_norm([d["first_act_hour"]  for d in data], "first_act_hour"),
            "exercise_hour":   calc_norm([d["exercise_hour"]   for d in data], "exercise_hour"),
            "exercise_mins":   calc_norm([d["exercise_mins"]   for d in data], "exercise_mins"),
            "outdoor_hour":    calc_norm([d["outdoor_hour"]    for d in data], "outdoor_hour"),
            "first_meal_hour": calc_norm([d["first_meal_hour"] for d in data], "first_meal_hour"),
            "last_meal_hour":  calc_norm([d["last_meal_hour"]  for d in data], "last_meal_hour"),
            "meal_count":      calc_norm([d["meal_count"]      for d in data], "meal_count"),
            "steps":           calc_norm([d["steps"]           for d in data], "steps"),
            "calories":        calc_norm([d["calories"]        for d in data], "calories"),
            "active_mins":     calc_norm([d["active_mins"]     for d in data], "active_mins"),
            "avg_hr":          calc_norm([d["avg_hr"]          for d in data], "avg_hr"),
            "avg_spo2":        calc_norm([d["avg_spo2"]        for d in data], "avg_spo2"),
            "avg_stress":      calc_norm([d["avg_stress"]      for d in data], "avg_stress"),
            "avg_hrv":         calc_norm([d["avg_hrv"]         for d in data], "avg_hrv"),
        }

    norms = {
        "weekday": norms_for(weekday_data) if weekday_data else {},
        "weekend": norms_for(weekend_data) if weekend_data else {},
        "all":     norms_for(active)       if active       else {},
    }

    # ── Sapma hesapla ─────────────────────────────────────────────────────────
    def deviation_score(value, norm):
        if value is None or norm is None or norm.get("mean") is None: return None
        if norm.get("std", 0) == 0: return 0
        return round((value - norm["mean"]) / norm["std"], 2)

    METRICS = [
        ("wake_hour",       "Uyanış Saati",        "saat",  False),
        ("sleep_hour",      "Uyku Saati",           "saat",  False),
        ("sleep_mins",      "Uyku Süresi",          "dk",    True),
        ("first_act_hour",  "İlk Aktivite Saati",   "saat",  False),
        ("exercise_hour",   "Egzersiz Saati",       "saat",  False),
        ("exercise_mins",   "Egzersiz Süresi",      "dk",    True),
        ("outdoor_hour",    "Dışarı Çıkış Saati",   "saat",  False),
        ("first_meal_hour", "İlk Yemek Saati",      "saat",  False),
        ("last_meal_hour",  "Son Yemek Saati",       "saat",  False),
        ("steps",           "Adım Sayısı",          "adım",  True),
        ("calories",        "Kalori",               "kcal",  True),
        ("active_mins",     "Aktif Süre",           "dk",    True),
        ("avg_hr",          "Ort. Nabız",           "bpm",   False),
        ("avg_stress",      "Ort. Stres",           "/100",  False),
        ("avg_hrv",         "Ort. HRV",             "",      True),
        ("avg_spo2",        "Ort. SpO₂",            "%",     True),
    ]

    for day in active:
        norm_key  = "weekend" if day["is_weekend"] else "weekday"
        day_norms = norms.get(norm_key) or norms.get("all") or {}
        day["deviations"] = {}
        day["deviation_flags"] = []
        for key, label, unit, higher_better in METRICS:
            val  = day.get(key)
            norm = day_norms.get(key)
            dev  = deviation_score(val, norm)
            day["deviations"][key] = dev
            if dev is not None and abs(dev) >= 1.5:
                direction = "yüksek" if dev > 0 else "düşük"
                severity  = "kritik" if abs(dev) >= 2.5 else "uyarı"
                if not higher_better:
                    interpretation = f"normalden {round(abs(dev),1)} std {'geç' if dev > 0 else 'erken'}"
                    if key in ["avg_stress"]:
                        interpretation = f"normalden {round(abs(dev),1)} std {'yüksek' if dev > 0 else 'düşük'}"
                else:
                    interpretation = f"normalden {round(abs(dev),1)} std {'fazla' if dev > 0 else 'az'}"
                # Dağılım bilgisini sapma açıklamasına ekle
                dist_used = (day_norms.get(key) or {}).get("distribution","normal")
                day["deviation_flags"].append({
                    "metric": key, "label": label, "value": val,
                    "norm_mean": norm.get("mean") if norm else None,
                    "deviation": dev, "direction": direction, "severity": severity,
                    "interpretation": interpretation, "unit": unit,
                    "distribution": dist_used,
                })

    # ── Tahmin (gelecek 3 gün) ────────────────────────────────────────────────
    def weighted_trend(vals, weights=None):
        vals = [v for v in vals if v is not None and v > 0]
        if not vals: return None, 0
        if len(vals) < 2: return vals[-1], 0
        if weights is None: weights = list(range(1, len(vals)+1))
        weights = weights[-len(vals):]
        total_w = sum(weights)
        mean    = sum(v*w for v,w in zip(vals,weights)) / total_w
        n = len(vals); mx = (n-1)/2; my = sum(vals)/n
        num   = sum((i-mx)*(v-my) for i,v in enumerate(vals))
        denom = sum((i-mx)**2 for i in range(n))
        slope = num/denom if denom != 0 else 0
        return round(mean,2), round(slope,3)

    recent  = active[-7:] if len(active) >= 7 else active
    weights = list(range(1, len(recent)+1))
    predictions = []
    for day_ahead in range(1, 4):
        pred_date    = (datetime.now()+timedelta(days=day_ahead)).strftime("%d/%m")
        pred_weekday = (datetime.now()+timedelta(days=day_ahead)).strftime("%A")
        is_weekend   = pred_weekday in ["Saturday","Sunday"]
        pred_wday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                        "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pred_weekday, pred_weekday)
        pred = {"date":pred_date,"weekday":pred_wday_tr,"is_weekend":is_weekend}
        for key, label, unit, higher_better in METRICS:
            vals = [d.get(key) for d in recent]
            base, slope = weighted_trend(vals, weights)
            if base is not None:
                predicted = base + slope * day_ahead
                if is_weekend:
                    if key == "wake_hour":     predicted += 0.5
                    if key == "sleep_hour":    predicted += 0.3
                    if key == "exercise_mins": predicted *= 0.8
                    if key == "steps":         predicted *= 0.85
                    if key == "active_mins":   predicted *= 0.85
                if key in ["avg_spo2"]:   predicted = max(90, min(100, predicted))
                if key in ["avg_hr"]:     predicted = max(45, min(160, predicted))
                if key in ["avg_stress"]: predicted = max(5,  min(99,  predicted))
                if key in ["wake_hour","sleep_hour","first_act_hour","exercise_hour",
                           "outdoor_hour","first_meal_hour","last_meal_hour"]:
                    predicted = max(0, min(24, predicted))
                    h = int(predicted); m = int((predicted%1)*60)
                    pred[key+"_str"] = f"{h:02d}:{m:02d}"
                pred[key] = round(predicted, 2)
            else:
                pred[key] = None
        norm_key  = "weekend" if is_weekend else "weekday"
        day_norms = norms.get(norm_key) or norms.get("all") or {}
        pred["expected_deviations"] = {}
        for key, label, unit, _ in METRICS:
            norm = day_norms.get(key); val = pred.get(key)
            pred["expected_deviations"][key] = deviation_score(val, norm)
        pred["confidence"] = "yüksek" if len(recent) >= 7 else ("orta" if len(recent) >= 4 else "düşük")
        predictions.append(pred)

    all_flags = []
    for day in active:
        for flag in day.get("deviation_flags", []):
            all_flags.append({**flag, "date": day["label"], "weekday": day["weekday"]})

    from collections import Counter
    metric_counts = Counter(f["metric"] for f in all_flags)
    frequent_deviations = [
        {"metric": k, "label": next((m[1] for m in METRICS if m[0]==k), k),
         "count": v, "pct": round(v/max(len(active),1)*100)}
        for k, v in metric_counts.most_common(5)
    ]

    # Hangi metrikte hangi dağılım kullanıldı — response'a ekle
    distributions_used = {
        metric: pattern_dists.get(metric, {}).get("distribution", "normal")
        for metric, *_ in METRICS
    }

    conn.close()
    return jsonify({
        "person":              dict(person),
        "daily":               active,
        "norms":               norms,
        "predictions":         predictions,
        "all_deviation_flags": all_flags,
        "frequent_deviations": frequent_deviations,
        "metrics_meta":        [{"key":k,"label":l,"unit":u} for k,l,u,_ in METRICS],
        "distributions_used":  distributions_used,
    })


# ── VERİ KATKISI TABLOLARI ────────────────────────────────────────────────────

def init_contribution_tables(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS monitoring_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, profile_type TEXT DEFAULT 'insan',
        environment TEXT DEFAULT 'genel', description TEXT,
        location TEXT, icon TEXT DEFAULT '📍', color TEXT DEFAULT '#534AB7',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS custom_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, description TEXT, environment TEXT DEFAULT 'genel',
        hour_start INTEGER DEFAULT 8, hour_end INTEGER DEFAULT 18,
        duration_min INTEGER DEFAULT 10, duration_max INTEGER DEFAULT 60,
        frequency_per_day INTEGER DEFAULT 1, hr_base INTEGER DEFAULT 75,
        hr_noise INTEGER DEFAULT 8, spo2_base REAL DEFAULT 98.0,
        stress_base INTEGER DEFAULT 30, icon TEXT DEFAULT '🔵',
        color TEXT DEFAULT '#534AB7', distribution TEXT DEFAULT 'normal',
        dist_params TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, type TEXT DEFAULT 'genel',
        description TEXT, location TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS contribution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER, person_id INTEGER,
        custom_activity_id INTEGER, environment_id INTEGER,
        profile_name TEXT, profile_type TEXT,
        activity_name TEXT, environment_name TEXT, environment_type TEXT,
        start_time TEXT, end_time TEXT, duration_mins INTEGER,
        heart_rate INTEGER, spo2 REAL, stress_level INTEGER,
        hour_of_day INTEGER, day_of_week INTEGER, is_weekend INTEGER DEFAULT 0,
        distribution_used TEXT DEFAULT 'normal', metadata TEXT,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for tbl, col in [
        ("custom_activities","distribution TEXT DEFAULT 'normal'"),
        ("custom_activities","dist_params TEXT DEFAULT '{}'"),
        ("contribution_log", "distribution_used TEXT DEFAULT 'normal'"),
    ]:
        try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except: pass
    conn.commit()


# ── VERİ KATKISI ENDPOINT'LERİ ───────────────────────────────────────────────

@app.route("/api/monitoring_profiles", methods=["GET"])
def get_monitoring_profiles():
    conn = get_db()
    rows = conn.execute("SELECT * FROM monitoring_profiles WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/monitoring_profiles", methods=["POST"])
def add_monitoring_profile():
    d = request.json; name = d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}), 400
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO monitoring_profiles (name,profile_type,environment,description,location,icon,color) VALUES (?,?,?,?,?,?,?)",
        (name,d.get("profile_type","insan"),d.get("environment","genel"),
         d.get("description",""),d.get("location",""),d.get("icon","📍"),d.get("color","#534AB7")))
    conn.commit(); pid=c.lastrowid; conn.close()
    return jsonify({"id":pid,"name":name}), 201

@app.route("/api/monitoring_profiles/<int:pid>", methods=["DELETE"])
def delete_monitoring_profile(pid):
    conn=get_db(); conn.execute("UPDATE monitoring_profiles SET active=0 WHERE id=?",(pid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@app.route("/api/custom_activities", methods=["GET"])
def get_custom_activities():
    conn = get_db()
    rows = conn.execute("SELECT * FROM custom_activities WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/custom_activities", methods=["POST"])
def add_custom_activity():
    d = request.json; name = d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}), 400
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO custom_activities
        (name,description,environment,hour_start,hour_end,duration_min,duration_max,
         frequency_per_day,hr_base,hr_noise,spo2_base,stress_base,icon,color,distribution,dist_params)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name,d.get("description",""),d.get("environment","genel"),
         int(d.get("hour_start",8)),int(d.get("hour_end",18)),
         int(d.get("duration_min",10)),int(d.get("duration_max",60)),
         int(d.get("frequency_per_day",1)),int(d.get("hr_base",75)),
         int(d.get("hr_noise",8)),float(d.get("spo2_base",98.0)),
         int(d.get("stress_base",30)),d.get("icon","🔵"),d.get("color","#534AB7"),
         d.get("distribution","normal"),_json.dumps(d.get("dist_params",{}))))
    conn.commit(); aid=c.lastrowid; conn.close()
    return jsonify({"id":aid,"name":name}), 201

@app.route("/api/custom_activities/<int:aid>", methods=["DELETE"])
def delete_custom_activity(aid):
    conn=get_db(); conn.execute("UPDATE custom_activities SET active=0 WHERE id=?",(aid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@app.route("/api/environments", methods=["GET"])
def get_environments():
    conn=get_db(); rows=conn.execute("SELECT * FROM environments WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/environments", methods=["POST"])
def add_environment():
    d=request.json; name=d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}), 400
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO environments (name,type,description,location) VALUES (?,?,?,?)",
        (name,d.get("type","genel"),d.get("description",""),d.get("location","")))
    conn.commit(); eid=c.lastrowid; conn.close()
    return jsonify({"id":eid,"name":name}), 201

@app.route("/api/environments/<int:eid>", methods=["DELETE"])
def delete_environment(eid):
    conn=get_db(); conn.execute("UPDATE environments SET active=0 WHERE id=?",(eid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@app.route("/api/contribute/simulate", methods=["POST"])
def simulate_contribution():
    d      = request.json
    mpid   = int(d.get("profile_id",0))
    aid    = int(d.get("activity_id",0))
    date_start = d.get("date_start"); date_end = d.get("date_end")
    conn = get_db()
    profile = conn.execute("SELECT * FROM monitoring_profiles WHERE id=? AND active=1",(mpid,)).fetchone()
    if not profile: conn.close(); return jsonify({"error":"Profil bulunamadı"}), 404
    act = conn.execute("SELECT * FROM custom_activities WHERE id=? AND active=1",(aid,)).fetchone()
    if not act: conn.close(); return jsonify({"error":"Aktivite bulunamadı"}), 404
    try:
        start_date = datetime.strptime(date_start,"%Y-%m-%d") if date_start else datetime.now()-timedelta(days=7)
        end_date   = datetime.strptime(date_end,  "%Y-%m-%d") if date_end   else datetime.now()
    except:
        start_date = datetime.now()-timedelta(days=7); end_date = datetime.now()
    if (end_date-start_date).days > 90: end_date = start_date+timedelta(days=90)

    # Aktiviteye tanımlı dağılımı kullan
    dist_name = act["distribution"] or "normal"
    try:
        dist_params = _json.loads(act["dist_params"] or "{}")
    except:
        dist_params = {}
    if not dist_params:
        dist_params = {"mean": act["hr_base"], "std": act["hr_noise"]}

    now = datetime.now(); records = []; current = start_date
    while current <= end_date:
        weekday = current.weekday(); is_weekend = 1 if weekday >= 5 else 0
        freq = act["frequency_per_day"]
        hour_range = max(1, act["hour_end"]-act["hour_start"])
        interval   = max(1, hour_range//max(freq,1))
        for i in range(freq):
            base_hour  = act["hour_start"]+i*interval
            jitter_min = random.randint(-15,15)
            start_dt   = current.replace(hour=min(base_hour,23),minute=0,second=0)+timedelta(minutes=jitter_min)
            dur_mins   = random.randint(act["duration_min"],act["duration_max"])
            end_dt     = start_dt+timedelta(minutes=dur_mins)
            hr     = int(sample_distribution(dist_name, dist_params, 40, 200))
            spo2   = round(sample_distribution("normal",{"mean":act["spo2_base"],"std":0.5},88,100),1)
            stress = int(sample_distribution("normal",{"mean":act["stress_base"],"std":10},5,99))
            metadata = _json.dumps({
                "profile_name":profile["name"],"profile_type":profile["profile_type"],
                "environment":profile["environment"],"activity":act["name"],
                "distribution":dist_name,"dist_params":dist_params,
                "duration_mins":dur_mins,"day_of_week":weekday,"is_weekend":is_weekend,
            }, ensure_ascii=False)
            conn.execute("""INSERT INTO contribution_log
                (profile_id,custom_activity_id,profile_name,profile_type,
                 activity_name,environment_name,environment_type,
                 start_time,end_time,duration_mins,heart_rate,spo2,stress_level,
                 hour_of_day,day_of_week,is_weekend,distribution_used,metadata,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mpid,aid,profile["name"],profile["profile_type"],
                 act["name"],profile["environment"],profile["profile_type"],
                 start_dt.isoformat(),end_dt.isoformat(),dur_mins,
                 hr,spo2,stress,base_hour,weekday,is_weekend,
                 dist_name,metadata,now.isoformat()))
            records.append({"date":start_dt.strftime("%d/%m"),"start":start_dt.strftime("%H:%M"),
                "duration_mins":dur_mins,"heart_rate":hr,"spo2":spo2,"stress_level":stress})
        current += timedelta(days=1)
    conn.commit(); conn.close()
    return jsonify({"ok":True,"records_added":len(records),"preview":records[:5]})

@app.route("/api/contribute/pattern/<int:mpid>", methods=["GET"])
def contribute_pattern(mpid):
    import statistics
    conn = get_db()
    profile = conn.execute("SELECT * FROM monitoring_profiles WHERE id=?",(mpid,)).fetchone()
    if not profile: conn.close(); return jsonify({"error":"Profil bulunamadı"}), 404
    rows = conn.execute("""SELECT activity_name,start_time,end_time,duration_mins,
        heart_rate,spo2,stress_level,hour_of_day,day_of_week,is_weekend,distribution_used
        FROM contribution_log WHERE profile_id=? ORDER BY start_time ASC""",(mpid,)).fetchall()
    if not rows: conn.close(); return jsonify({"error":"Bu profil için henüz veri yok"}), 404
    from collections import defaultdict
    by_activity = defaultdict(list)
    for r in rows: by_activity[r["activity_name"]].append(dict(r))
    activity_stats = []; all_alerts = []
    for act_name, recs in by_activity.items():
        def stat(vals):
            vals=[v for v in vals if v]
            if len(vals)<2: return {"mean":vals[0] if vals else 0,"std":0,"low":vals[0] if vals else 0,"high":vals[0] if vals else 0,"n":len(vals)}
            m=sum(vals)/len(vals); s=statistics.stdev(vals)
            return {"mean":round(m,1),"std":round(s,1),"min":round(min(vals),1),"max":round(max(vals),1),"low":round(m-s,1),"high":round(m+s,1),"n":len(vals)}
        hr_stat=stat([r["heart_rate"] for r in recs]); spo2_stat=stat([r["spo2"] for r in recs])
        str_stat=stat([r["stress_level"] for r in recs]); dur_stat=stat([r["duration_mins"] for r in recs])
        daily=defaultdict(list)
        for r in recs:
            try: daily[datetime.fromisoformat(r["start_time"]).strftime("%d/%m")].append(r)
            except: pass
        daily_series=[]
        for day,drecs in sorted(daily.items()):
            avg_hr=round(sum(r["heart_rate"] for r in drecs)/len(drecs),1)
            avg_sp=round(sum(r["spo2"] for r in drecs)/len(drecs),1)
            avg_st=round(sum(r["stress_level"] for r in drecs)/len(drecs),1)
            avg_dur=round(sum(r["duration_mins"] for r in drecs)/len(drecs),1)
            devs={}
            for key,val,norm in [("heart_rate",avg_hr,hr_stat),("spo2",avg_sp,spo2_stat),("stress",avg_st,str_stat),("duration",avg_dur,dur_stat)]:
                if norm["std"]>0:
                    dev=round((val-norm["mean"])/norm["std"],2); devs[key]=dev
                    if abs(dev)>=1.5:
                        all_alerts.append({"date":day,"activity":act_name,"metric":key,"value":val,
                            "norm_mean":norm["mean"],"deviation":dev,"severity":"kritik" if abs(dev)>=2.5 else "uyarı","profile":profile["name"]})
                else: devs[key]=0
            daily_series.append({"date":day,"avg_hr":avg_hr,"avg_spo2":avg_sp,"avg_stress":avg_st,
                "avg_duration":avg_dur,"deviations":devs,"count":len(drecs)})
        activity_stats.append({"activity_name":act_name,"record_count":len(recs),"hr_stat":hr_stat,
            "spo2_stat":spo2_stat,"stress_stat":str_stat,"duration_stat":dur_stat,"daily_series":daily_series,
            "distribution":recs[0].get("distribution_used","normal") if recs else "normal"})
    conn.close()
    return jsonify({"profile":dict(profile),"activity_stats":activity_stats,
        "alerts":sorted(all_alerts,key=lambda x:abs(x["deviation"]),reverse=True)[:20],"total_records":len(rows)})

@app.route("/api/contribute/export", methods=["GET"])
def export_contribution():
    from flask import Response
    import csv, io, unicodedata
    pid = request.args.get("profile_id", type=int)
    conn = get_db()
    q = "SELECT * FROM contribution_log WHERE 1=1"; params = []
    if pid: q += " AND profile_id=?"; params.append(pid)
    q += " ORDER BY start_time DESC LIMIT 5000"
    rows = conn.execute(q, params).fetchall(); conn.close()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["profile_name","profile_type","activity_name","environment_name",
        "start_time","end_time","duration_mins","heart_rate","spo2","stress_level",
        "hour_of_day","day_of_week","is_weekend","distribution_used","metadata"])
    for r in rows:
        writer.writerow([r["profile_name"],r["profile_type"],r["activity_name"],r["environment_name"],
            r["start_time"],r["end_time"],r["duration_mins"],r["heart_rate"],r["spo2"],r["stress_level"],
            r["hour_of_day"],r["day_of_week"],r["is_weekend"],r["distribution_used"],r["metadata"]])
    output.seek(0)
    return Response("\ufeff"+output.getvalue(),mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename=katki_verisi.csv"})

@app.route("/api/contribute/stats", methods=["GET"])
def contribution_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as n FROM contribution_log").fetchone()["n"]
    by_activity = conn.execute("""SELECT activity_name,COUNT(*) as cnt,
        ROUND(AVG(heart_rate),1) as avg_hr,ROUND(AVG(spo2),1) as avg_spo2,
        ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(duration_mins),1) as avg_dur
        FROM contribution_log GROUP BY activity_name ORDER BY cnt DESC""").fetchall()
    by_env = conn.execute("""SELECT environment_name,environment_type,COUNT(*) as cnt
        FROM contribution_log GROUP BY environment_name ORDER BY cnt DESC""").fetchall()
    conn.close()
    return jsonify({"total_records":total,"by_activity":[dict(r) for r in by_activity],
        "by_environment":[dict(r) for r in by_env]})


# ── ANALİZ ────────────────────────────────────────────────────────────────────

@app.route("/api/daily_profile/<int:pid>", methods=["GET"])
def get_daily_profile(pid):
    days_back = int(request.args.get("days", 14))
    conn      = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    profiles = []
    for i in range(days_back - 1, -1, -1):
        d        = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        label    = (datetime.now()-timedelta(days=i)).strftime("%d/%m")
        weekday  = (datetime.now()-timedelta(days=i)).strftime("%A")
        weekday_tr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar",
                      "Thursday":"Per","Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday, weekday)
        sleep_rec = conn.execute("""SELECT start_time,end_time,duration_mins FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""", (pid, d)).fetchone()
        wake_hour = sleep_hour = None; sleep_mins = 0
        if sleep_rec:
            try:
                end = sleep_rec["end_time"]
                if end:
                    dt = datetime.fromisoformat(end) if len(end)>5 else None
                    wake_hour = dt.hour+dt.minute/60 if dt else None
                st2 = sleep_rec["start_time"]
                if st2:
                    dt2 = datetime.fromisoformat(st2) if len(st2)>5 else None
                    sleep_hour = dt2.hour+dt2.minute/60 if dt2 else None
                sleep_mins = sleep_rec["duration_mins"] or 0
            except: pass
        first_act = conn.execute("""SELECT activity_name,start_time FROM activity_log
            WHERE person_id=? AND activity_type!='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        first_act_hour = None; first_act_name = None
        if first_act and first_act["start_time"]:
            try:
                dt3 = datetime.fromisoformat(first_act["start_time"]) if len(first_act["start_time"])>5 else None
                if dt3: first_act_hour = dt3.hour+dt3.minute/60
                first_act_name = first_act["activity_name"]
            except: pass
        outdoor = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""", (pid, d)).fetchone()
        outdoor_hour = None
        if outdoor and outdoor["start_time"]:
            try:
                ot = outdoor["start_time"]
                if len(ot)>5:
                    dt4 = datetime.fromisoformat(ot)
                    outdoor_hour = dt4.hour+dt4.minute/60
            except: pass
        meals = conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='meal' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC""", (pid, d)).fetchall()
        meal_hours = []
        for m in meals:
            try:
                if m["start_time"] and len(m["start_time"])>5:
                    dt5 = datetime.fromisoformat(m["start_time"])
                    meal_hours.append(round(dt5.hour+dt5.minute/60,2))
            except: pass
        metrics = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
            COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COUNT(*) as event_count FROM activity_log
            WHERE person_id=? AND date(start_time,'localtime')=?""", (pid, d)).fetchone()
        sensor = conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,ROUND(AVG(spo2),1) as avg_spo2,
            ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(hrv),1) as avg_hrv,
            MAX(heart_rate) as max_hr,MIN(CASE WHEN heart_rate>0 THEN heart_rate END) as min_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""", (pid, d)).fetchone()
        profiles.append({
            "date":d,"label":label,"weekday":weekday_tr,
            "wake_hour":round(wake_hour,2) if wake_hour is not None else None,
            "sleep_hour":round(sleep_hour,2) if sleep_hour is not None else None,
            "sleep_mins":sleep_mins,
            "wake_time_str":f"{int(wake_hour):02d}:{int((wake_hour%1)*60):02d}" if wake_hour is not None else "—",
            "sleep_time_str":f"{int(sleep_hour):02d}:{int((sleep_hour%1)*60):02d}" if sleep_hour is not None else "—",
            "first_act_hour":round(first_act_hour,2) if first_act_hour is not None else None,
            "first_act_name":first_act_name,
            "outdoor_hour":round(outdoor_hour,2) if outdoor_hour is not None else None,
            "meal_hours":meal_hours,"meal_count":len(meal_hours),
            "steps":int(metrics["steps"] or 0),"calories":round(float(metrics["calories"] or 0),1),
            "active_mins":int(metrics["active_mins"] or 0),"event_count":int(metrics["event_count"] or 0),
            "avg_hr":float(sensor["avg_hr"] or 0),"avg_spo2":float(sensor["avg_spo2"] or 0),
            "avg_stress":float(sensor["avg_stress"] or 0),"avg_hrv":float(sensor["avg_hrv"] or 0),
            "max_hr":int(sensor["max_hr"] or 0),"min_hr":int(sensor["min_hr"] or 0),
        })
    active_profiles = [p for p in profiles if p["event_count"]>0]
    for i in range(1,len(active_profiles)):
        prev=active_profiles[i-1]; curr=active_profiles[i]
        curr["wake_delta_mins"]  = round((curr["wake_hour"]-prev["wake_hour"])*60) if curr["wake_hour"] is not None and prev["wake_hour"] is not None else None
        curr["sleep_delta_mins"] = round((curr["sleep_hour"]-prev["sleep_hour"])*60) if curr["sleep_hour"] is not None and prev["sleep_hour"] is not None else None
        curr["steps_delta"]  = curr["steps"]-prev["steps"]
        curr["active_delta"] = curr["active_mins"]-prev["active_mins"]
        curr["stress_delta"] = round(curr["avg_stress"]-prev["avg_stress"],1)
    if active_profiles:
        for key in ["wake_delta_mins","sleep_delta_mins","steps_delta","active_delta","stress_delta"]:
            if key not in active_profiles[0]: active_profiles[0][key]=None
    anomalies=[]
    wake_hours_list=[p["wake_hour"] for p in active_profiles[-4:] if p["wake_hour"] is not None]
    if len(wake_hours_list)>=3:
        diffs=[wake_hours_list[i+1]-wake_hours_list[i] for i in range(len(wake_hours_list)-1)]
        if all(d>0.2 for d in diffs):
            total_drift=round((wake_hours_list[-1]-wake_hours_list[0])*60)
            anomalies.append({"type":"wake_drift","title":"Uyanış Saati Giderek Gecikiyor",
                "desc":f"Son {len(wake_hours_list)} günde uyanış saati toplam {total_drift} dakika geriledi","severity":"warning","icon":"🌅"})
    steps_list=[p["steps"] for p in active_profiles[-5:] if p["steps"]>0]
    if len(steps_list)>=4:
        first_half=sum(steps_list[:len(steps_list)//2])/(len(steps_list)//2)
        second_half=sum(steps_list[len(steps_list)//2:])/(len(steps_list)-len(steps_list)//2)
        if second_half<first_half*0.8:
            drop_pct=round((1-second_half/first_half)*100)
            anomalies.append({"type":"steps_decline","title":"Adım Sayısı Düşüyor",
                "desc":f"Son dönem adım ortalaması %{drop_pct} azaldı","severity":"info","icon":"🚶"})
    sleep_list=[p["wake_hour"] for p in active_profiles if p["wake_hour"] is not None]
    if len(sleep_list)>=5:
        spread=max(sleep_list)-min(sleep_list)
        if spread>=2:
            anomalies.append({"type":"sleep_irregularity","title":"Uyku Düzensizliği",
                "desc":f"Uyanış saatleri {round(spread*60)} dakika aralıkta değişiyor","severity":"warning","icon":"😴"})
    stress_list=[p["avg_stress"] for p in active_profiles[-4:] if p["avg_stress"]>0]
    if len(stress_list)>=3 and all(stress_list[i]<stress_list[i+1] for i in range(len(stress_list)-1)):
        anomalies.append({"type":"stress_rising","title":"Stres Sürekli Artıyor",
            "desc":f"Son {len(stress_list)} günde stres her gün arttı","severity":"warning","icon":"🧠"})
    active_list=[p["active_mins"] for p in active_profiles[-5:]]
    if len(active_list)>=4 and max(active_list)>0:
        recent_avg=sum(active_list[-3:])/3; older_avg=sum(active_list[:-3])/max(1,len(active_list)-3)
        if older_avg>20 and recent_avg<older_avg*0.6:
            anomalies.append({"type":"activity_decline","title":"Aktivite Belirgin Azaldı",
                "desc":f"Aktif süre ortalaması {round(older_avg)} dk'dan {round(recent_avg)} dk'ya düştü","severity":"warning","icon":"📉"})
    def weighted_avg(vals,weights=None):
        vals=[v for v in vals if v is not None and v>0]
        if not vals: return None
        if weights is None or len(weights)!=len(vals): weights=list(range(1,len(vals)+1))
        return sum(v*w for v,w in zip(vals,weights))/sum(weights)
    def linear_trend(vals):
        vals=[v for v in vals if v is not None and v>0]
        if len(vals)<2: return 0
        n=len(vals); mx=(n-1)/2; my=sum(vals)/n
        num=sum((i-mx)*(v-my) for i,v in enumerate(vals)); denom=sum((i-mx)**2 for i in range(n))
        return num/denom if denom!=0 else 0
    recent=active_profiles[-7:] if len(active_profiles)>=7 else active_profiles
    wake_vals=[p["wake_hour"] for p in recent if p["wake_hour"] is not None]
    sleep_vals=[p["sleep_mins"] for p in recent if p["sleep_mins"]>0]
    steps_vals=[p["steps"] for p in recent if p["steps"]>0]
    stress_vals=[p["avg_stress"] for p in recent if p["avg_stress"]>0]
    hr_vals=[p["avg_hr"] for p in recent if p["avg_hr"]>0]
    wake_trend=linear_trend(wake_vals); steps_trend=linear_trend(steps_vals); stress_trend=linear_trend(stress_vals)
    predictions=[]
    for day_ahead in range(1,4):
        pred_date=(datetime.now()+timedelta(days=day_ahead)).strftime("%d/%m")
        pred_wday=(datetime.now()+timedelta(days=day_ahead)).strftime("%A")
        pred_wday_tr={"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar","Thursday":"Per",
                      "Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pred_wday,pred_wday)
        is_weekend=pred_wday in ["Saturday","Sunday"]
        base_wake=weighted_avg(wake_vals); base_steps=weighted_avg(steps_vals)
        base_stress=weighted_avg(stress_vals); base_sleep=weighted_avg(sleep_vals); base_hr=weighted_avg(hr_vals)
        pred_wake=round(base_wake+wake_trend*day_ahead,2) if base_wake else None
        pred_steps=int(base_steps+steps_trend*day_ahead) if base_steps else None
        pred_stress=round(base_stress+stress_trend*day_ahead,1) if base_stress else None
        pred_sleep=round(base_sleep,1) if base_sleep else None
        pred_hr=round(base_hr,1) if base_hr else None
        if is_weekend and pred_wake:
            pred_wake=round(pred_wake+0.5,2)
            pred_steps=int(pred_steps*0.8) if pred_steps else None
        conf="yüksek" if len(recent)>=7 else ("orta" if len(recent)>=4 else "düşük")
        wake_str=None
        if pred_wake is not None:
            h=max(0,min(23,int(pred_wake))); m=int((pred_wake%1)*60); wake_str=f"{h:02d}:{m:02d}"
        predictions.append({"date":pred_date,"weekday":pred_wday_tr,"is_weekend":is_weekend,
            "wake_time":wake_str,"steps":max(0,pred_steps) if pred_steps is not None else None,
            "sleep_mins":max(0,int(pred_sleep)) if pred_sleep is not None else None,
            "avg_stress":max(0,min(100,pred_stress)) if pred_stress is not None else None,
            "avg_hr":pred_hr,"confidence":conf})
    conn.close()
    return jsonify({"person":dict(person),"profiles":active_profiles,"anomalies":anomalies,"predictions":predictions})


@app.route("/api/analysis/<int:pid>", methods=["GET"])
def get_analysis(pid):
    days_back = int(request.args.get("days", 14))
    conn      = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    days_data = []
    for i in range(days_back-1,-1,-1):
        d=( datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        label=(datetime.now()-timedelta(days=i)).strftime("%d/%m")
        weekday=(datetime.now()-timedelta(days=i)).strftime("%A")
        weekday_tr={"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar","Thursday":"Per",
                    "Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(weekday,weekday)
        summary_row=conn.execute("""SELECT COUNT(*) as total_events,
            SUM(CASE WHEN activity_type='active' THEN 1 ELSE 0 END) as active_count,
            SUM(CASE WHEN activity_type='meal'   THEN 1 ELSE 0 END) as meal_count,
            SUM(CASE WHEN activity_type='sleep'  THEN 1 ELSE 0 END) as sleep_count,
            SUM(CASE WHEN activity_type='rest'   THEN 1 ELSE 0 END) as rest_count,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins,
            COALESCE(MAX(steps_snap),0) as max_steps,COALESCE(MAX(calories_snap),0) as max_cal,
            COALESCE(AVG(heart_rate_avg),0) as avg_hr,COALESCE(MAX(heart_rate_avg),0) as max_hr,
            COALESCE(MIN(CASE WHEN heart_rate_avg>0 THEN heart_rate_avg END),0) as min_hr
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
        sleep_rows=conn.execute("""SELECT start_time,end_time,duration_mins,heart_rate_avg FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time""",(pid,d)).fetchall()
        sleep_records=[]
        for sr in sleep_rows:
            try:
                st_dt=datetime.fromisoformat(sr["start_time"]) if sr["start_time"] else None
                en_dt=datetime.fromisoformat(sr["end_time"])   if sr["end_time"]   else None
                sleep_records.append({"start":st_dt.strftime("%H:%M") if st_dt else "—",
                    "end":en_dt.strftime("%H:%M") if en_dt else "—",
                    "duration_mins":sr["duration_mins"] or 0,"hr_avg":sr["heart_rate_avg"] or 0})
            except: pass
        wake_time=sleep_records[-1]["end"] if sleep_records else None
        sleep_start_time=sleep_records[0]["start"] if sleep_records else None
        sensor_row=conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,ROUND(AVG(spo2),1) as avg_spo2,
            ROUND(AVG(skin_temp),2) as avg_temp,ROUND(AVG(hrv),1) as avg_hrv,
            ROUND(AVG(stress_level),1) as avg_stress,MIN(heart_rate) as min_hr,MAX(heart_rate) as max_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        heatmap_row=[]
        for h in range(24):
            row=conn.execute("""SELECT activity_type,COUNT(*) as cnt FROM sensor_log
                WHERE person_id=? AND date(recorded_at,'localtime')=? AND strftime('%H',recorded_at)=?
                GROUP BY activity_type ORDER BY cnt DESC LIMIT 1""",(pid,d,f"{h:02d}")).fetchone()
            heatmap_row.append(row["activity_type"] if row else None)
        top_acts=conn.execute("""SELECT activity_name,activity_icon,activity_type,duration_mins,start_time
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 3""",(pid,d)).fetchall()
        sr=dict(summary_row) if summary_row else {}; snr=dict(sensor_row) if sensor_row else {}
        health_score=compute_health_score(sr.get("sleep_mins",0),sr.get("active_mins",0),
            snr.get("avg_stress",50) or 50,snr.get("avg_hr",75) or 75,snr.get("avg_spo2",97) or 97)
        days_data.append({"date":d,"label":label,"weekday":weekday_tr,
            "total_events":sr.get("total_events",0),"active_count":sr.get("active_count",0),
            "meal_count":sr.get("meal_count",0),"sleep_count":sr.get("sleep_count",0),
            "rest_count":sr.get("rest_count",0),"active_mins":sr.get("active_mins",0),
            "sleep_mins":sr.get("sleep_mins",0),"steps":sr.get("max_steps",0),
            "calories":round(sr.get("max_cal",0),1),
            "avg_hr":snr.get("avg_hr") or sr.get("avg_hr") or 0,
            "max_hr":snr.get("max_hr") or sr.get("max_hr") or 0,
            "min_hr":snr.get("min_hr") or sr.get("min_hr") or 0,
            "avg_spo2":snr.get("avg_spo2",0),"avg_temp":snr.get("avg_temp",0),
            "avg_hrv":snr.get("avg_hrv",0),"avg_stress":snr.get("avg_stress",0),
            "health_score":health_score,"wake_time":wake_time,"sleep_start_time":sleep_start_time,
            "sleep_records":sleep_records,"heatmap":heatmap_row,
            "top_activities":[{"name":ta["activity_name"],"icon":ta["activity_icon"],
                "type":ta["activity_type"],"dur":ta["duration_mins"],
                "start":datetime.fromisoformat(ta["start_time"]).strftime("%H:%M") if ta["start_time"] else "—"}
                for ta in top_acts]})
    wake_hours=[]
    for _d in days_data:
        for _r in _d["sleep_records"]:
            _end=_r.get("end","")
            if not _end or _end=="—": continue
            try:
                if len(_end)<=5: wake_hours.append(int(_end.split(":")[0]))
                else: wake_hours.append(datetime.fromisoformat(_end).hour)
            except: pass
    sleep_irregularity=round(max(wake_hours)-min(wake_hours),1) if len(wake_hours)>=2 else 0
    alerts=conn.execute("SELECT * FROM smart_alerts WHERE person_id=? ORDER BY detected_at DESC LIMIT 20",(pid,)).fetchall()
    conn.close()
    return jsonify({"person":dict(person),"days":days_data,"sleep_irregularity":sleep_irregularity,
        "smart_alerts":[dict(a) for a in alerts]})


# ── SİM HIZI ─────────────────────────────────────────────────────────────────

@app.route("/api/sim_speed", methods=["GET","POST"])
def sim_speed_endpoint():
    global sim_speed
    if request.method=="POST":
        sim_speed=max(1,min(10,int(request.json.get("speed",1))))
    return jsonify({"speed":sim_speed})

@app.route("/api/trend/<int:pid>", methods=["GET"])
def get_trend(pid):
    conn = get_db(); trend = []
    for i in range(6,-1,-1):
        d=(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        row=conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(AVG(heart_rate_avg),0) as avg_hr,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
        sensor=conn.execute("""SELECT ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(heart_rate),1) as avg_hr2
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        trend.append({"date":d,"steps":row["steps"] or 0,"calories":round(row["calories"] or 0,1),
            "avg_hr":round((row["avg_hr"] or 0) if row["avg_hr"] else (sensor["avg_hr2"] or 0),1),
            "active_mins":row["active_mins"] or 0,"sleep_mins":row["sleep_mins"] or 0,
            "avg_stress":sensor["avg_stress"] or 0})
    conn.close(); return jsonify(trend)


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Veritabanı hazırlanıyor...")
    init_db()
    conn = get_db()
    if conn.execute("SELECT COUNT(*) as n FROM persons").fetchone()["n"] == 0:
        sample = [("Ayşe Yılmaz",34,"İstanbul"),("Mehmet Kaya",28,"Ankara"),
                  ("Zeynep Arslan",41,"İzmir"),("Can Demir",25,"İstanbul"),("Elif Şahin",36,"Bursa")]
        print("Örnek kişiler ekleniyor ve geçmiş veri üretiliyor...")
        for nm, ag, ct in sample:
            conn.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
                         (nm,ag,ct,random.randint(5,10),random.choice(AVATAR_COLORS)))
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            seed_historical_data(conn, pid, days_back=14)
        print("Hazır.")
    else:
        for p in conn.execute("SELECT id FROM persons WHERE active=1").fetchall():
            seed_historical_data(conn, p["id"], days_back=14)
    conn.close()
    conn2 = get_db(); check_smart_alerts(conn2); conn2.close()
    t = threading.Thread(target=simulation_loop, daemon=True)
    t.start()
    print("Simülasyon başlatıldı — http://localhost:5000")
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)