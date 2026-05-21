"""
db.py — Veritabanı katmanı
Tüm tablo tanımları, bağlantı yönetimi ve ham veri erişim fonksiyonları.
İş mantığı, simülasyon ve route kodları bu dosyada YOK.
"""
import sqlite3
import json as _json

DB_PATH = "simulasyon_v3.db"


# ── BAĞLANTI ──────────────────────────────────────────────────────────────────

def get_db():
    """Thread-safe SQLite bağlantısı döndür."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── TABLO OLUŞTURMA ───────────────────────────────────────────────────────────

def init_db():
    """Ana uygulama tablolarını oluştur, eksik sütunları migrate et."""
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

    # Simülasyon dağılım ayarları
    c.execute("""CREATE TABLE IF NOT EXISTS distribution_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT NOT NULL UNIQUE,
        distribution TEXT DEFAULT 'normal',
        params TEXT DEFAULT '{}',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for metric, dist, params in [
        ('heart_rate', 'normal',      '{"mean":75,"std":10}'),
        ('spo2',       'normal',      '{"mean":97.5,"std":0.8}'),
        ('skin_temp',  'normal',      '{"mean":36.5,"std":0.2}'),
        ('hrv',        'normal',      '{"mean":45,"std":12}'),
        ('stress',     'exponential', '{"scale":25,"offset":5}'),
        ('steps',      'lognormal',   '{"mean":8.2,"sigma":0.9}'),
        ('sleep_mins', 'triangular',  '{"low":300,"mode":450,"high":560}'),
        ('active_mins','normal',      '{"mean":60,"std":25}'),
    ]:
        try:
            c.execute("INSERT OR IGNORE INTO distribution_settings (metric,distribution,params) VALUES (?,?,?)",
                      (metric, dist, params))
        except: pass

    # Örüntü analizi dağılım ayarları
    c.execute("""CREATE TABLE IF NOT EXISTS pattern_dist_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT NOT NULL UNIQUE,
        distribution TEXT DEFAULT 'normal',
        params TEXT DEFAULT '{}',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for metric, dist, params in [
        ('wake_hour',       'normal',       '{"mean":7.5,  "std":0.5}'),
        ('sleep_hour',      'normal',       '{"mean":23.0, "std":0.5}'),
        ('sleep_mins',      'triangular',   '{"low":300,   "mode":450,"high":540}'),
        ('first_act_hour',  'normal',       '{"mean":8.0,  "std":0.5}'),
        ('exercise_hour',   'normal',       '{"mean":9.0,  "std":1.0}'),
        ('exercise_mins',   'exponential',  '{"scale":30,  "offset":0}'),
        ('outdoor_hour',    'normal',       '{"mean":10.0, "std":1.5}'),
        ('first_meal_hour', 'normal',       '{"mean":8.0,  "std":0.5}'),
        ('last_meal_hour',  'normal',       '{"mean":19.0, "std":0.5}'),
        ('meal_count',      'poisson',      '{"lam":3}'),
        ('steps',           'lognormal',    '{"mean":8.2,  "sigma":0.8}'),
        ('calories',        'normal',       '{"mean":2000, "std":400}'),
        ('active_mins',     'normal',       '{"mean":60,   "std":20}'),
        ('avg_hr',          'normal',       '{"mean":75,   "std":10}'),
        ('avg_spo2',        'normal',       '{"mean":97.5, "std":0.8}'),
        ('avg_stress',      'exponential',  '{"scale":25,  "offset":10}'),
        ('avg_hrv',         'normal',       '{"mean":45,   "std":12}'),
    ]:
        try:
            c.execute("INSERT OR IGNORE INTO pattern_dist_settings (metric,distribution,params) VALUES (?,?,?)",
                      (metric, dist, params))
        except: pass

    # Veri katkısı tabloları
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

    # Kişiye özgü istatistiksel profil tablosu
    c.execute("""CREATE TABLE IF NOT EXISTS personal_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER NOT NULL,
        metric TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        mean REAL NOT NULL,
        std REAL NOT NULL,
        n INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(person_id, metric, activity_type),
        FOREIGN KEY (person_id) REFERENCES persons(id))""")

    # Markov geçiş matrisi tablosu
    c.execute("""CREATE TABLE IF NOT EXISTS markov_transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER NOT NULL,
        from_activity TEXT NOT NULL,
        to_activity TEXT NOT NULL,
        hour_block INTEGER NOT NULL,
        count INTEGER DEFAULT 1,
        probability REAL DEFAULT 0.0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(person_id, from_activity, to_activity, hour_block),
        FOREIGN KEY (person_id) REFERENCES persons(id))""")

    # Migration: eski DB'lere eksik sütunları ekle
    for tbl, col in [
        ("activity_log",     "start_time TEXT"),
        ("activity_log",     "end_time TEXT"),
        ("activity_log",     "duration_mins INTEGER DEFAULT 0"),
        ("activity_log",     "heart_rate_avg INTEGER DEFAULT 0"),
        ("persons",          "anomaly_hr_threshold INTEGER DEFAULT 130"),
        ("persons",          "anomaly_stress_threshold INTEGER DEFAULT 75"),
        ("persons",          "health_profile TEXT DEFAULT 'balanced'"),
        ("custom_activities","distribution TEXT DEFAULT 'normal'"),
        ("custom_activities","dist_params TEXT DEFAULT '{}'"),
        ("contribution_log", "distribution_used TEXT DEFAULT 'normal'"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except: pass

    conn.commit()
    conn.close()


# ── HAM VERİ ERİŞİM FONKSİYONLARI ────────────────────────────────────────────

def db_get_persons():
    conn = get_db()
    rows = conn.execute("SELECT * FROM persons WHERE active=1 ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_current_states():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_anomalies(limit=50):
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.name as person_name FROM anomalies a
        JOIN persons p ON a.person_id=p.id
        ORDER BY a.detected_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_smart_alerts(limit=100):
    conn = get_db()
    rows = conn.execute("""SELECT sa.*,p.name as person_name FROM smart_alerts sa
        JOIN persons p ON sa.person_id=p.id
        ORDER BY sa.detected_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_sensor_history(pid, limit=60):
    conn = get_db()
    rows = conn.execute("""SELECT * FROM sensor_log WHERE person_id=?
        ORDER BY recorded_at DESC LIMIT ?""", (pid, limit)).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


def db_get_distribution_settings():
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


def db_get_pattern_dist_settings():
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