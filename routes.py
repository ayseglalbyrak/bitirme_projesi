"""
routes.py — Flask API endpoint'leri
Tüm HTTP route'ları burada.
İş mantığı simulator.py'de, DB işlemleri db.py'de.
"""
import random, csv, io, json as _json
from datetime import datetime, timedelta
from collections import Counter
from flask import Blueprint, jsonify, request, send_from_directory, Response

from db import get_db
from simulator import (
    ACTIVITIES, AVATAR_COLORS, current_weather, current_temp,
    seed_historical_data, sample_distribution,
    get_dist_settings_cached, get_pattern_dist_cached,
    invalidate_dist_cache, invalidate_pattern_dist_cache,
    compute_health_score, _compute_metric_params,
    build_markov_matrix, get_markov_matrix, invalidate_markov_cache,
    build_personal_stats,
)
import simulator as _sim

bp = Blueprint("api", __name__)


# ── STATIC ────────────────────────────────────────────────────────────────────

@bp.route("/")
def home():
    return send_from_directory(".", "index.html")


# ── KİŞİLER ───────────────────────────────────────────────────────────────────

@bp.route("/api/persons", methods=["GET"])
def get_persons():
    conn = get_db()
    rows = conn.execute("SELECT * FROM persons WHERE active=1 ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/persons", methods=["POST"])
def add_person():
    d    = request.json
    name = d.get("name", "").strip()
    if not name:
        return jsonify({"error": "İsim zorunlu"}), 400
    color = d.get("avatar_color", random.choice(AVATAR_COLORS))
    conn  = get_db(); c = conn.cursor()
    c.execute(
        "INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
        (name, d.get("age", random.randint(20,60)), d.get("city","").strip(), random.randint(5,10), color)
    )
    conn.commit()
    pid = c.lastrowid
    seed_historical_data(conn, pid, days_back=14)
    conn.close()
    return jsonify({"id": pid, "name": name, "avatar_color": color}), 201


@bp.route("/api/persons/<int:pid>", methods=["PATCH"])
def update_person(pid):
    d = request.json; conn = get_db(); c = conn.cursor()
    for field in ["avatar_color", "anomaly_hr_threshold", "anomaly_stress_threshold", "health_profile"]:
        if field in d:
            val = d[field] if field in ("avatar_color", "health_profile") else int(d[field])
            c.execute(f"UPDATE persons SET {field}=? WHERE id=?", (val, pid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@bp.route("/api/persons/<int:pid>", methods=["DELETE"])
def delete_person(pid):
    conn = get_db()
    conn.execute("UPDATE persons SET active=0 WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ── DURUM & GEÇMİŞ ────────────────────────────────────────────────────────────

@bp.route("/api/state", methods=["GET"])
def get_all_states():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.age,p.city,p.sleep_score,p.avatar_color,cs.*
        FROM persons p LEFT JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY p.id""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/history/<int:pid>", methods=["GET"])
def get_history(pid):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM activity_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT 30", (pid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/sensors/<int:pid>", methods=["GET"])
def get_sensor_history(pid):
    limit = int(request.args.get("limit", 60))
    conn  = get_db()
    rows  = conn.execute(
        "SELECT * FROM sensor_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT ?", (pid, limit)
    ).fetchall()
    conn.close()
    return jsonify(list(reversed([dict(r) for r in rows])))


@bp.route("/api/anomalies", methods=["GET"])
def get_anomalies():
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.name as person_name FROM anomalies a
        JOIN persons p ON a.person_id=p.id ORDER BY a.detected_at DESC LIMIT 50""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/smart_alerts", methods=["GET"])
def get_smart_alerts():
    conn = get_db()
    rows = conn.execute("""SELECT sa.*,p.name as person_name FROM smart_alerts sa
        JOIN persons p ON sa.person_id=p.id ORDER BY sa.detected_at DESC LIMIT 100""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/compare", methods=["GET"])
def compare_persons():
    conn = get_db()
    rows = conn.execute("""SELECT p.name,p.age,p.city,p.sleep_score,p.avatar_color,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,
        cs.heart_rate,cs.spo2,cs.stress_level,cs.hrv
        FROM persons p JOIN current_state cs ON p.id=cs.person_id
        WHERE p.active=1 ORDER BY cs.steps DESC""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/summary", methods=["GET"])
def summary():
    conn  = get_db()
    total = conn.execute("SELECT COUNT(*) as n FROM persons WHERE active=1").fetchone()["n"]
    avg   = conn.execute("""SELECT ROUND(AVG(steps)) as s,ROUND(AVG(calories),1) as c,
        ROUND(AVG(active_mins)) as a,ROUND(AVG(heart_rate)) as hr,ROUND(AVG(stress_level)) as stress
        FROM current_state cs JOIN persons p ON cs.person_id=p.id WHERE p.active=1""").fetchone()
    acnt  = conn.execute(
        "SELECT COUNT(*) as n FROM anomalies WHERE datetime(detected_at)>datetime('now','-1 hour')"
    ).fetchone()["n"]
    salrt = conn.execute(
        "SELECT COUNT(*) as n FROM smart_alerts WHERE datetime(detected_at)>datetime('now','-24 hours')"
    ).fetchone()["n"]
    conn.close()
    return jsonify({
        "total_persons":total,"avg_steps":avg["s"] or 0,"avg_calories":avg["c"] or 0,
        "avg_active_mins":avg["a"] or 0,"avg_heart_rate":avg["hr"] or 0,"avg_stress":avg["stress"] or 0,
        "anomaly_count":acnt,"smart_alert_count":salrt,
        "weather":{"condition":current_weather["condition"],"condition_en":current_weather["condition_en"],
            "icon":current_weather["icon"],"temp":round(current_temp,1)}
    })


@bp.route("/api/chart/<int:pid>", methods=["GET"])
def get_chart(pid):
    conn = get_db()
    row  = conn.execute("""SELECT p.name,p.avatar_color,cs.chart_active,cs.chart_rest,cs.chart_meal,cs.chart_sleep,
        cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,p.sleep_score,
        cs.heart_rate,cs.spo2,cs.skin_temp,cs.hrv,cs.stress_level,cs.mood
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.id=? AND p.active=1""", (pid,)).fetchone()
    conn.close()
    if not row: return jsonify({"error":"Kişi bulunamadı"}), 404
    return jsonify(dict(row))


@bp.route("/api/timeline/<int:pid>", methods=["GET"])
def get_timeline(pid):
    conn = get_db()
    rows = conn.execute("""SELECT activity_name,activity_name_en,activity_icon,activity_type,
        start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at
        FROM activity_log WHERE person_id=? AND recorded_at >= datetime('now','-7 days')
        ORDER BY recorded_at DESC LIMIT 80""", (pid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/weekly/<int:pid>", methods=["GET"])
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


@bp.route("/api/location", methods=["GET"])
def get_locations():
    conn = get_db()
    rows = conn.execute("""SELECT p.id,p.name,p.avatar_color,cs.latitude,cs.longitude,
        cs.location_name,cs.activity_name,cs.activity_icon,cs.activity_type
        FROM persons p JOIN current_state cs ON p.id=cs.person_id WHERE p.active=1""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/trend/<int:pid>", methods=["GET"])
def get_trend(pid):
    conn = get_db(); trend = []
    for i in range(6,-1,-1):
        d   = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        row = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(AVG(heart_rate_avg),0) as avg_hr,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
        sen = conn.execute("""SELECT ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(heart_rate),1) as avg_hr2
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        trend.append({"date":d,"steps":row["steps"] or 0,"calories":round(row["calories"] or 0,1),
            "avg_hr":round((row["avg_hr"] or sen["avg_hr2"] or 0),1),
            "active_mins":row["active_mins"] or 0,"sleep_mins":row["sleep_mins"] or 0,
            "avg_stress":sen["avg_stress"] or 0})
    conn.close()
    return jsonify(trend)


@bp.route("/api/avatar_colors", methods=["GET"])
def avatar_colors():
    return jsonify(AVATAR_COLORS)


@bp.route("/api/sim_speed", methods=["GET","POST"])
def sim_speed_endpoint():
    if request.method == "POST":
        _sim.sim_speed = max(1, min(10, int(request.json.get("speed",1))))
    return jsonify({"speed": _sim.sim_speed})


# ── DAĞILIM ───────────────────────────────────────────────────────────────────

@bp.route("/api/distributions", methods=["GET"])
def get_distributions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM distribution_settings ORDER BY metric").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/distributions", methods=["POST"])
def update_distributions():
    items = request.json
    if not isinstance(items, list): items = [items]
    conn = get_db(); c = conn.cursor()
    for item in items:
        metric = item.get("metric","").strip()
        if not metric: continue
        c.execute("""INSERT INTO distribution_settings (metric,distribution,params,updated_at)
            VALUES (?,?,?,?) ON CONFLICT(metric) DO UPDATE SET
            distribution=excluded.distribution,params=excluded.params,updated_at=excluded.updated_at""",
            (metric, item.get("distribution","normal"),
             _json.dumps(item.get("params",{})), datetime.now().isoformat()))
    conn.commit(); conn.close()
    invalidate_dist_cache()
    return jsonify({"ok":True})


@bp.route("/api/distributions/preview", methods=["POST"])
def preview_distribution():
    d = request.json
    samples = [round(sample_distribution(d.get("distribution","normal"),
        d.get("params",{}), d.get("min_v"), d.get("max_v")),2) for _ in range(100)]
    mean = sum(samples)/len(samples)
    std  = (sum((x-mean)**2 for x in samples)/len(samples))**0.5
    return jsonify({"samples":samples,"mean":round(mean,2),"std":round(std,2),
        "min":min(samples),"max":max(samples)})


@bp.route("/api/pattern_distributions", methods=["GET"])
def get_pattern_distributions():
    pid  = request.args.get("pid", type=int)
    conn = get_db()
    rows = conn.execute("SELECT * FROM pattern_dist_settings ORDER BY metric").fetchall()
    result = [dict(r) for r in rows]
    if pid:
        computed = _compute_metric_params(conn, pid)
        for item in result:
            item["computed_params"] = computed.get(item["metric"], {})
    conn.close()
    return jsonify(result)


@bp.route("/api/pattern_distributions", methods=["POST"])
def update_pattern_distributions():
    items = request.json
    if not isinstance(items, list): items = [items]
    conn = get_db(); c = conn.cursor()
    for item in items:
        metric = item.get("metric","").strip()
        if not metric: continue
        c.execute("""INSERT INTO pattern_dist_settings (metric,distribution,params,updated_at)
            VALUES (?,?,?,?) ON CONFLICT(metric) DO UPDATE SET
            distribution=excluded.distribution,params=excluded.params,updated_at=excluded.updated_at""",
            (metric, item.get("distribution","normal"),
             _json.dumps(item.get("params",{})), datetime.now().isoformat()))
    conn.commit(); conn.close()
    invalidate_pattern_dist_cache()
    return jsonify({"ok":True})


# ── EXPORT ────────────────────────────────────────────────────────────────────

@bp.route("/api/export/<int:pid>", methods=["GET"])
def export_person(pid):
    conn = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    export_type = request.args.get("type","activity")
    output = io.StringIO()
    if export_type == "activity":
        rows = conn.execute("""SELECT activity_name,activity_type,start_time,end_time,
            duration_mins,steps_snap,calories_snap,heart_rate_avg
            FROM activity_log WHERE person_id=? ORDER BY start_time DESC LIMIT 1000""",(pid,)).fetchall()
        w = csv.writer(output)
        w.writerow(["Aktivite","Tip","Baslangic","Bitis","Sure(dk)","Adim","Kalori","Ort.Nabiz"])
        for r in rows:
            w.writerow([r["activity_name"],r["activity_type"],r["start_time"],r["end_time"],
                r["duration_mins"],r["steps_snap"],round(r["calories_snap"] or 0,1),r["heart_rate_avg"]])
        filename = person["name"]+"_aktivite.csv"
    elif export_type == "sensor":
        rows = conn.execute("""SELECT recorded_at,heart_rate,spo2,skin_temp,hrv,stress_level,
            steps,calories,activity_name,activity_type
            FROM sensor_log WHERE person_id=? ORDER BY recorded_at DESC LIMIT 2000""",(pid,)).fetchall()
        w = csv.writer(output)
        w.writerow(["Zaman","Nabiz","SpO2","Sicaklik","HRV","Stres","Adim","Kalori","Aktivite","Tip"])
        for r in rows:
            w.writerow([r["recorded_at"],r["heart_rate"],r["spo2"],r["skin_temp"],
                r["hrv"],r["stress_level"],r["steps"],round(r["calories"] or 0,1),
                r["activity_name"],r["activity_type"]])
        filename = person["name"]+"_sensor.csv"
    else:
        w = csv.writer(output)
        w.writerow(["Tarih","Adim","Kalori","Aktif(dk)","Uyku(dk)","Ort.Nabiz","Ort.Stres","Ort.SpO2","Etkinlik"])
        for i in range(29,-1,-1):
            d = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
            r = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,COALESCE(MAX(calories_snap),0) as cal,
                COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as act,
                COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as slp,
                COALESCE(AVG(heart_rate_avg),0) as hr,COUNT(*) as ev
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
            s = conn.execute("""SELECT ROUND(AVG(stress_level),1) as st,ROUND(AVG(spo2),1) as sp
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
            w.writerow([d,r["steps"],round(r["cal"] or 0,1),r["act"],r["slp"],
                round(r["hr"] or 0,1),s["st"] or 0,s["sp"] or 0,r["ev"]])
        filename = person["name"]+"_gunluk.csv"
    conn.close(); output.seek(0)
    return Response("\ufeff"+output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename="+filename})


# ── ANALİZ ────────────────────────────────────────────────────────────────────

@bp.route("/api/analysis/<int:pid>", methods=["GET"])
def get_analysis(pid):
    days_back = int(request.args.get("days", 14))
    conn      = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    days_data = []
    for i in range(days_back-1,-1,-1):
        d    = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        lbl  = (datetime.now()-timedelta(days=i)).strftime("%d/%m")
        wday = (datetime.now()-timedelta(days=i)).strftime("%A")
        wtr  = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar","Thursday":"Per",
                "Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(wday,wday)
        sr = conn.execute("""SELECT COUNT(*) as total_events,
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
        slrows = conn.execute("""SELECT start_time,end_time,duration_mins,heart_rate_avg FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time""",(pid,d)).fetchall()
        slrecs = []
        for sl in slrows:
            try:
                st=datetime.fromisoformat(sl["start_time"]) if sl["start_time"] else None
                en=datetime.fromisoformat(sl["end_time"])   if sl["end_time"]   else None
                slrecs.append({"start":st.strftime("%H:%M") if st else "—",
                    "end":en.strftime("%H:%M") if en else "—",
                    "duration_mins":sl["duration_mins"] or 0,"hr_avg":sl["heart_rate_avg"] or 0})
            except: pass
        snr = conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,ROUND(AVG(spo2),1) as avg_spo2,
            ROUND(AVG(skin_temp),2) as avg_temp,ROUND(AVG(hrv),1) as avg_hrv,
            ROUND(AVG(stress_level),1) as avg_stress,MIN(heart_rate) as min_hr,MAX(heart_rate) as max_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        heatmap=[]
        for h in range(24):
            row=conn.execute("""SELECT activity_type,COUNT(*) as cnt FROM sensor_log
                WHERE person_id=? AND date(recorded_at,'localtime')=? AND strftime('%H',recorded_at)=?
                GROUP BY activity_type ORDER BY cnt DESC LIMIT 1""",(pid,d,f"{h:02d}")).fetchone()
            heatmap.append(row["activity_type"] if row else None)
        top=conn.execute("""SELECT activity_name,activity_icon,activity_type,duration_mins,start_time
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 3""",(pid,d)).fetchall()
        s=dict(sr) if sr else {}; sn=dict(snr) if snr else {}
        hs=compute_health_score(s.get("sleep_mins",0),s.get("active_mins",0),
            sn.get("avg_stress",50) or 50,sn.get("avg_hr",75) or 75,sn.get("avg_spo2",97) or 97)
        days_data.append({"date":d,"label":lbl,"weekday":wtr,
            "total_events":s.get("total_events",0),"active_count":s.get("active_count",0),
            "meal_count":s.get("meal_count",0),"sleep_count":s.get("sleep_count",0),
            "rest_count":s.get("rest_count",0),"active_mins":s.get("active_mins",0),
            "sleep_mins":s.get("sleep_mins",0),"steps":s.get("max_steps",0),
            "calories":round(s.get("max_cal",0),1),
            "avg_hr":sn.get("avg_hr") or s.get("avg_hr") or 0,
            "max_hr":sn.get("max_hr") or s.get("max_hr") or 0,
            "min_hr":sn.get("min_hr") or s.get("min_hr") or 0,
            "avg_spo2":sn.get("avg_spo2",0),"avg_temp":sn.get("avg_temp",0),
            "avg_hrv":sn.get("avg_hrv",0),"avg_stress":sn.get("avg_stress",0),
            "health_score":hs,
            "wake_time":slrecs[-1]["end"] if slrecs else None,
            "sleep_start_time":slrecs[0]["start"] if slrecs else None,
            "sleep_records":slrecs,"heatmap":heatmap,
            "top_activities":[{"name":ta["activity_name"],"icon":ta["activity_icon"],
                "type":ta["activity_type"],"dur":ta["duration_mins"],
                "start":datetime.fromisoformat(ta["start_time"]).strftime("%H:%M")
                        if ta["start_time"] else "—"} for ta in top]})
    wh=[]
    for _d in days_data:
        for _r in _d["sleep_records"]:
            _e=_r.get("end","")
            if not _e or _e=="—": continue
            try: wh.append(int(_e.split(":")[0]) if len(_e)<=5 else datetime.fromisoformat(_e).hour)
            except: pass
    alerts=conn.execute("SELECT * FROM smart_alerts WHERE person_id=? ORDER BY detected_at DESC LIMIT 20",(pid,)).fetchall()
    conn.close()
    return jsonify({"person":dict(person),"days":days_data,
        "sleep_irregularity":round(max(wh)-min(wh),1) if len(wh)>=2 else 0,
        "smart_alerts":[dict(a) for a in alerts]})


@bp.route("/api/pattern_analysis/<int:pid>", methods=["GET"])
def get_pattern_analysis(pid):
    """Kişiye özgü örüntü analizi — kullanıcının seçtiği dağılıma göre norm hesaplar."""
    import statistics
    days_back     = int(request.args.get("days", 14))
    conn          = get_db()
    person        = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person: conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
    pattern_dists = get_pattern_dist_cached()

    METRICS = [
        ("wake_hour","Uyanış Saati","saat",False),("sleep_hour","Uyku Saati","saat",False),
        ("sleep_mins","Uyku Süresi","dk",True),("first_act_hour","İlk Aktivite Saati","saat",False),
        ("exercise_hour","Egzersiz Saati","saat",False),("exercise_mins","Egzersiz Süresi","dk",True),
        ("outdoor_hour","Dışarı Çıkış Saati","saat",False),("first_meal_hour","İlk Yemek Saati","saat",False),
        ("last_meal_hour","Son Yemek Saati","saat",False),("steps","Adım Sayısı","adım",True),
        ("calories","Kalori","kcal",True),("active_mins","Aktif Süre","dk",True),
        ("avg_hr","Ort. Nabız","bpm",False),("avg_stress","Ort. Stres","/100",False),
        ("avg_hrv","Ort. HRV","",True),("avg_spo2","Ort. SpO₂","%",True),
    ]

    def safe_h(ts):
        if not ts: return None
        try:
            dt=datetime.fromisoformat(ts); return round(dt.hour+dt.minute/60,2)
        except:
            try: return round(int(ts.split(":")[0])+int(ts.split(":")[1])/60,2)
            except: return None

    daily=[]
    for i in range(days_back-1,-1,-1):
        d   =(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        lbl =(datetime.now()-timedelta(days=i)).strftime("%d/%m")
        wday=(datetime.now()-timedelta(days=i)).strftime("%A")
        iw  = wday in ["Saturday","Sunday"]
        wtr = {"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar","Thursday":"Per",
               "Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(wday,wday)
        slp=conn.execute("""SELECT start_time,end_time,duration_mins FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""",(pid,d)).fetchone()
        fa =conn.execute("""SELECT start_time,activity_name FROM activity_log
            WHERE person_id=? AND activity_type!='sleep' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""",(pid,d)).fetchone()
        ex =conn.execute("""SELECT start_time,SUM(duration_mins) as total FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            GROUP BY date(start_time,'localtime') ORDER BY start_time ASC LIMIT 1""",(pid,d)).fetchone()
        meals=conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='meal' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC""",(pid,d)).fetchall()
        out=conn.execute("""SELECT start_time FROM activity_log
            WHERE person_id=? AND activity_type='active' AND date(start_time,'localtime')=?
            ORDER BY start_time ASC LIMIT 1""",(pid,d)).fetchone()
        met=conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
            COALESCE(MAX(calories_snap),0) as calories,
            COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
            COUNT(*) as event_count
            FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
        sen=conn.execute("""SELECT ROUND(AVG(heart_rate),1) as avg_hr,ROUND(AVG(spo2),1) as avg_spo2,
            ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(hrv),1) as avg_hrv,MAX(heart_rate) as max_hr
            FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
        mh=[safe_h(m["start_time"]) for m in meals if safe_h(m["start_time"])]
        daily.append({"date":d,"label":lbl,"weekday":wtr,"is_weekend":iw,
            "wake_hour":safe_h(slp["end_time"]) if slp else None,
            "sleep_hour":safe_h(slp["start_time"]) if slp else None,
            "sleep_mins":slp["duration_mins"] if slp else 0,
            "first_act_hour":safe_h(fa["start_time"]) if fa else None,
            "first_act_name":fa["activity_name"] if fa else None,
            "exercise_hour":safe_h(ex["start_time"]) if ex else None,
            "exercise_mins":int(ex["total"] or 0) if ex else 0,
            "outdoor_hour":safe_h(out["start_time"]) if out else None,
            "meal_hours":mh,"meal_count":len(mh),
            "first_meal_hour":mh[0] if mh else None,"last_meal_hour":mh[-1] if mh else None,
            "steps":int(met["steps"] or 0),"calories":round(float(met["calories"] or 0),1),
            "active_mins":int(met["active_mins"] or 0),
            "avg_hr":float(sen["avg_hr"] or 0),"avg_spo2":float(sen["avg_spo2"] or 0),
            "avg_stress":float(sen["avg_stress"] or 0),"avg_hrv":float(sen["avg_hrv"] or 0),
            "max_hr":int(sen["max_hr"] or 0),"event_count":int(met["event_count"] or 0)})

    active=[d for d in daily if d["steps"]>0 or d["avg_hr"]>0]

    def calc_norm(vals, metric=None):
        vals=[v for v in vals if v is not None and v>0]
        if not vals: return {"mean":None,"std":0,"low":None,"high":None,"n":0,"distribution":"normal"}
        if len(vals)<2: return {"mean":vals[0],"std":0,"low":vals[0],"high":vals[0],"n":1,"distribution":"normal"}
        mean=sum(vals)/len(vals); std=statistics.stdev(vals)
        dist=(pattern_dists.get(metric,{}) if metric else {}).get("distribution","normal")
        if dist=="normal": low,high=mean-std,mean+std
        elif dist=="lognormal":
            import math as _m
            lv=[_m.log(v) for v in vals]; lm=sum(lv)/len(lv)
            ls=statistics.stdev(lv) if len(lv)>1 else 0
            low,high=_m.exp(lm-ls),_m.exp(lm+ls)
        elif dist=="exponential":
            sv=sorted(vals); n=len(sv)
            low=sv[max(0,int(n*.1))]; high=sv[min(n-1,int(n*.9))]
        elif dist in ("triangular","uniform"): low,high=min(vals),max(vals)
        else: low,high=mean-std,mean+std
        return {"mean":round(mean,2),"std":round(std,2),"min":round(min(vals),2),
                "max":round(max(vals),2),"low":round(low,2),"high":round(high,2),
                "n":len(vals),"distribution":dist}

    def norms_for(data):
        return {k:calc_norm([d[k] for d in data],k) for k,*_ in METRICS}

    norms={
        "weekday":norms_for([d for d in active if not d["is_weekend"]]) if any(not d["is_weekend"] for d in active) else {},
        "weekend":norms_for([d for d in active if d["is_weekend"]])     if any(d["is_weekend"] for d in active)     else {},
        "all":    norms_for(active) if active else {},
    }

    def dev_s(val,norm):
        if val is None or norm is None or norm.get("mean") is None: return None
        if norm.get("std",0)==0: return 0
        return round((val-norm["mean"])/norm["std"],2)

    for day in active:
        dn=norms.get("weekend" if day["is_weekend"] else "weekday") or norms.get("all") or {}
        day["deviations"]={}; day["deviation_flags"]=[]
        for key,label,unit,higher in METRICS:
            val=day.get(key); norm=dn.get(key); dev=dev_s(val,norm)
            day["deviations"][key]=dev
            if dev is not None and abs(dev)>=1.5:
                direction="yüksek" if dev>0 else "düşük"
                severity ="kritik" if abs(dev)>=2.5 else "uyarı"
                interp=(f"normalden {round(abs(dev),1)} std {'geç' if dev>0 else 'erken'}"
                        if not higher else f"normalden {round(abs(dev),1)} std {'fazla' if dev>0 else 'az'}")
                if key=="avg_stress": interp=f"normalden {round(abs(dev),1)} std {'yüksek' if dev>0 else 'düşük'}"
                day["deviation_flags"].append({"metric":key,"label":label,"value":val,
                    "norm_mean":norm.get("mean") if norm else None,"deviation":dev,
                    "direction":direction,"severity":severity,"interpretation":interp,"unit":unit,
                    "distribution":(dn.get(key) or {}).get("distribution","normal")})

    def wtrd(vals,weights=None):
        vals=[v for v in vals if v is not None and v>0]
        if not vals: return None,0
        if len(vals)<2: return vals[-1],0
        if weights is None: weights=list(range(1,len(vals)+1))
        weights=weights[-len(vals):]
        mean=sum(v*w for v,w in zip(vals,weights))/sum(weights)
        n=len(vals); mx=(n-1)/2; my=sum(vals)/n
        num=sum((i-mx)*(v-my) for i,v in enumerate(vals))
        denom=sum((i-mx)**2 for i in range(n))
        return round(mean,2),round(num/denom if denom else 0,3)

    recent=active[-7:] if len(active)>=7 else active
    ws=list(range(1,len(recent)+1))
    predictions=[]
    for ahead in range(1,4):
        pd=(datetime.now()+timedelta(days=ahead)).strftime("%d/%m")
        pw=(datetime.now()+timedelta(days=ahead)).strftime("%A")
        iw=pw in ["Saturday","Sunday"]
        pwr={"Monday":"Pzt","Tuesday":"Sal","Wednesday":"Çar","Thursday":"Per",
             "Friday":"Cum","Saturday":"Cmt","Sunday":"Paz"}.get(pw,pw)
        pred={"date":pd,"weekday":pwr,"is_weekend":iw}
        for key,label,unit,higher in METRICS:
            base,slope=wtrd([d.get(key) for d in recent],ws)
            if base is not None:
                p=base+slope*ahead
                if iw:
                    if key=="wake_hour":     p+=0.5
                    if key=="sleep_hour":    p+=0.3
                    if key=="exercise_mins": p*=0.8
                    if key in ("steps","active_mins"): p*=0.85
                if key=="avg_spo2":   p=max(90,min(100,p))
                if key=="avg_hr":     p=max(45,min(160,p))
                if key=="avg_stress": p=max(5, min(99, p))
                if key in ("wake_hour","sleep_hour","first_act_hour","exercise_hour",
                           "outdoor_hour","first_meal_hour","last_meal_hour"):
                    p=max(0,min(24,p)); h=int(p); m=int((p%1)*60)
                    pred[key+"_str"]=f"{h:02d}:{m:02d}"
                pred[key]=round(p,2)
            else: pred[key]=None
        dn=norms.get("weekend" if iw else "weekday") or norms.get("all") or {}
        pred["expected_deviations"]={key:dev_s(pred.get(key),dn.get(key)) for key,*_ in METRICS}
        pred["confidence"]="yüksek" if len(recent)>=7 else ("orta" if len(recent)>=4 else "düşük")
        predictions.append(pred)

    all_flags=[{**f,"date":day["label"],"weekday":day["weekday"]}
               for day in active for f in day.get("deviation_flags",[])]
    mc=Counter(f["metric"] for f in all_flags)
    frequent=[{"metric":k,"label":next((m[1] for m in METRICS if m[0]==k),k),
               "count":v,"pct":round(v/max(len(active),1)*100)} for k,v in mc.most_common(5)]
    conn.close()
    return jsonify({"person":dict(person),"daily":active,"norms":norms,"predictions":predictions,
        "all_deviation_flags":all_flags,"frequent_deviations":frequent,
        "metrics_meta":[{"key":k,"label":l,"unit":u} for k,l,u,_ in METRICS],
        "distributions_used":{m:pattern_dists.get(m,{}).get("distribution","normal") for m,*_ in METRICS}})



# ── VERİ KALİTE ÖLÇÜMÜ ────────────────────────────────────────────────────────

@bp.route("/api/quality/<int:pid>", methods=["GET"])
def get_data_quality(pid):
    """
    Üretilen verinin istatistiksel kalitesini ölç.
    
    Metrikler:
    - Temel istatistikler (mean, std, min, max, skewness, kurtosis)
    - KL-Divergence (üretilen vs teorik dağılım)
    - Chi-kare uyum testi
    - Aktivite dağılımı gerçekçilik skoru
    - Günlük düzenlilik skoru (Markov etkisi)
    """
    import statistics, math
    conn   = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    days_back = int(request.args.get("days", 14))
    now       = datetime.now()

    # ── 1. Ham sensör verisi çek ─────────────────────────────────────────────
    sensor_rows = conn.execute("""
        SELECT heart_rate, spo2, skin_temp, hrv, stress_level,
               activity_type, recorded_at
        FROM sensor_log WHERE person_id=?
        AND recorded_at >= datetime('now', ? || ' days')
        ORDER BY recorded_at ASC
    """, (pid, f"-{days_back}")).fetchall()

    if len(sensor_rows) < 20:
        conn.close()
        return jsonify({"error": "Yeterli sensör verisi yok"}), 400

    hr_vals     = [r["heart_rate"]   for r in sensor_rows if r["heart_rate"]   and r["heart_rate"]   > 0]
    spo2_vals   = [r["spo2"]         for r in sensor_rows if r["spo2"]         and r["spo2"]         > 0]
    temp_vals   = [r["skin_temp"]    for r in sensor_rows if r["skin_temp"]    and r["skin_temp"]    > 0]
    hrv_vals    = [r["hrv"]          for r in sensor_rows if r["hrv"]          and r["hrv"]          > 0]
    stress_vals = [r["stress_level"] for r in sensor_rows if r["stress_level"] and r["stress_level"] > 0]

    # ── 2. İstatistik hesaplama ───────────────────────────────────────────────
    def calc_stats(vals, name, unit, expected_mean, expected_std, expected_min, expected_max):
        """Bir metrik için kapsamlı istatistik hesapla."""
        if len(vals) < 3:
            return None
        n    = len(vals)
        mean = sum(vals) / n
        std  = statistics.stdev(vals) if n > 1 else 0
        mn   = min(vals)
        mx   = max(vals)
        
        # Skewness (çarpıklık)
        if std > 0:
            skew = sum(((v - mean) / std) ** 3 for v in vals) / n
        else:
            skew = 0
        
        # Kurtosis (basıklık)
        if std > 0:
            kurt = sum(((v - mean) / std) ** 4 for v in vals) / n - 3
        else:
            kurt = 0

        # KL-Divergence (normal dağılıma göre)
        def kl_divergence_normal(vals, mu, sigma):
            """Verinin normal dağılıma yakınlığını ölç (düşük = iyi)."""
            if sigma <= 0: return 0
            n   = len(vals)
            eps = 1e-10
            # Histogram oluştur (10 bin)
            bins = 10
            hist_min = mu - 3*sigma
            hist_max = mu + 3*sigma
            bin_w    = (hist_max - hist_min) / bins
            if bin_w <= 0: return 0
            
            observed = [0]*bins
            for v in vals:
                idx = int((v - hist_min) / bin_w)
                idx = max(0, min(bins-1, idx))
                observed[idx] += 1
            
            # Teorik normal dağılım beklentisi
            import math as _m
            expected = []
            for i in range(bins):
                x_mid = hist_min + (i+0.5)*bin_w
                p_theory = (1/(sigma*_m.sqrt(2*_m.pi))) * _m.exp(-0.5*((x_mid-mu)/sigma)**2) * bin_w
                expected.append(max(p_theory, eps))
            
            total_obs = sum(observed)
            if total_obs == 0: return 0
            
            kl = 0
            for o, e in zip(observed, expected):
                p = o/total_obs + eps
                kl += p * _m.log(p / e)
            return round(abs(kl), 4)

        # Standart KL-divergence — her metrik için hesapla
        kl_div = kl_divergence_normal(vals, expected_mean, expected_std)
        # Nabız/stres/HRV multimodal — kendi ortalamasına göre KL hesapla (daha adil)
        if name in ("Nabız", "Stres", "HRV"):
            kl_div = kl_divergence_normal(vals, mean, max(std, 0.1))
        
        # Chi-kare uyum testi (basitleştirilmiş)
        def chi_square_test(vals, mu, sigma, bins=8):
            """Chi-kare istatistiği hesapla (düşük = normal dağılıma uygun)."""
            if sigma <= 0 or len(vals) < bins: return 0, 1.0
            import math as _m
            n        = len(vals)
            hist_min = mu - 3*sigma
            hist_max = mu + 3*sigma
            bin_w    = (hist_max - hist_min) / bins
            if bin_w <= 0: return 0, 1.0
            observed = [0]*bins
            for v in vals:
                idx = int((v - hist_min) / bin_w)
                idx = max(0, min(bins-1, idx))
                observed[idx] += 1
            expected_counts = []
            for i in range(bins):
                x_lo = hist_min + i*bin_w
                x_hi = x_lo + bin_w
                def phi(x): return 0.5*(1 + math.erf(x/_m.sqrt(2)))
                p = phi((x_hi-mu)/sigma) - phi((x_lo-mu)/sigma)
                expected_counts.append(max(p*n, 0.1))
            chi2  = sum((o-e)**2/e for o,e in zip(observed,expected_counts))
            p_val = math.exp(-chi2/2) if chi2 < 50 else 0
            return round(chi2, 3), round(p_val, 4)

        chi2, p_val = chi_square_test(vals, expected_mean, expected_std)

        # Gerçekçilik skoru (0-100)
        mean_score = max(0, 100 - abs(mean - expected_mean) / max(expected_std, 1) * 20)
        std_score  = max(0, 100 - abs(std - expected_std) / max(expected_std, 0.1) * 30)
        range_ok   = (expected_min <= mn) and (mx <= expected_max)
        range_score = 100 if range_ok else max(0, 70 - (
            max(0, expected_min - mn) + max(0, mx - expected_max)) / max(expected_std, 1) * 10)
        # Normallik skoru: aktivite bazlı KL kullan (daha adil)
        normal_score = max(0, 100 - kl_div * 150)

        realism_score = round((mean_score * 0.3 + std_score * 0.25 +
                               range_score * 0.2 + normal_score * 0.25))

        # Histogram verisi (görselleştirme için)
        import math as _mh
        hist_bins   = 12
        bin_w_h     = (mx - mn) / hist_bins if mx > mn else 1
        hist_counts = [0] * hist_bins
        for v in vals:
            idx = int((v - mn) / bin_w_h)
            idx = max(0, min(hist_bins - 1, idx))
            hist_counts[idx] += 1
        hist_max_count = max(hist_counts) if hist_counts else 1
        normal_curve = []
        for i in range(hist_bins):
            x_mid = mn + (i + 0.5) * bin_w_h
            if std > 0:
                p = (1 / (std * _mh.sqrt(2 * _mh.pi))) * _mh.exp(-0.5 * ((x_mid - mean) / std) ** 2)
                normal_curve.append(round(p * len(vals) * bin_w_h, 2))
            else:
                normal_curve.append(0)
        hist_labels = [round(mn + i * bin_w_h, 1) for i in range(hist_bins)]

        return {
            "name":           name,
            "unit":           unit,
            "n":              n,
            "mean":           round(mean, 2),
            "std":            round(std, 2),
            "min":            round(mn, 2),
            "max":            round(mx, 2),
            "skewness":       round(skew, 3),
            "kurtosis":       round(kurt, 3),
            "kl_divergence":  kl_div,
            "chi2":           chi2,
            "chi2_p":         p_val,
            "expected_mean":  expected_mean,
            "expected_std":   expected_std,
            "realism_score":  realism_score,
            "mean_score":     round(mean_score),
            "std_score":      round(std_score),
            "range_score":    round(range_score),
            "normal_score":   round(normal_score),
            "histogram": {
                "counts":       hist_counts,
                "labels":       hist_labels,
                "normal_curve": normal_curve,
                "max_count":    hist_max_count,
                "bin_width":    round(bin_w_h, 2),
            },
        }

    # Beklenen değerler (tıbbi literatürden)
    metrics_quality = [
        calc_stats(hr_vals,     "Nabız",         "bpm", 72,   12,  40,  180),
        calc_stats(spo2_vals,   "SpO₂",          "%",   97.5, 1.2, 92,  100),
        calc_stats(temp_vals,   "Cilt Sıcaklığı","°C",  36.5, 0.4, 35,  39),
        calc_stats(hrv_vals,    "HRV",           "ms",  45,   15,  10,  90),
        calc_stats(stress_vals, "Stres",         "/100",35,   20,  5,   95),
    ]
    metrics_quality = [m for m in metrics_quality if m]

    # ── 3. Aktivite dağılımı gerçekçilik analizi ──────────────────────────────
    # SÜRE bazında hesapla.
    # Uyku kaydı gece başlar, sabah biter — çift sayımı önlemek için
    # her günün 00:00-23:59 aralığına düşen GERÇEK süreyi hesapla.
    # Basit yaklaşım: period_start içinde başlayan kayıtları al,
    # ama uyku için duration'ı 24*days_back saate bölerek normalize et.
    act_durations = conn.execute("""
        SELECT activity_type,
               SUM(
                 CASE
                   -- Uyku: gece başlar sabah biter, gerçek süreyi kap
                   WHEN activity_type = 'sleep' THEN
                     MIN(duration_mins,
                         CAST((julianday(end_time) - julianday(start_time)) * 1440 AS INTEGER))
                   ELSE duration_mins
                 END
               ) as total_mins
        FROM activity_log
        WHERE person_id=?
          AND recorded_at >= datetime('now', ? || ' days')
          AND duration_mins > 0
        GROUP BY activity_type
    """, (pid, f"-{days_back}")).fetchall()

    total_mins = sum(r["total_mins"] for r in act_durations if r["total_mins"])
    act_dist   = {r["activity_type"]: round(r["total_mins"]/total_mins, 3)
                  for r in act_durations if total_mins > 0}

    # Beklenen dağılım — süre bazında (24 saatin kaçı, gerçekçi insan)
    expected_act_dist = {
        "sleep":  0.33,  # ~8 saat / 24 saat
        "active": 0.28,  # çalışma + egzersiz + yürüyüş
        "rest":   0.22,  # dinlenme + TV + okuma
        "meal":   0.17,  # yemek saatleri
    }
    
    # Aktivite dağılımı KL-Divergence
    act_kl = 0
    for act_type, expected_p in expected_act_dist.items():
        observed_p = act_dist.get(act_type, 0.001)
        act_kl += expected_p * math.log(expected_p / max(observed_p, 0.001))
    act_kl = round(abs(act_kl), 4)
    
    act_realism = max(0, round(100 - act_kl * 100))

    # ── 4. Günlük düzenlilik skoru (Markov etkisi) ───────────────────────────
    # Her gün için uyanış saati sapması — düşükse düzenli
    wake_times = []
    for i in range(days_back):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        slp = conn.execute("""SELECT end_time FROM activity_log
            WHERE person_id=? AND activity_type='sleep' AND date(start_time,'localtime')=?
            ORDER BY duration_mins DESC LIMIT 1""", (pid, d)).fetchone()
        if slp and slp["end_time"]:
            try:
                dt = datetime.fromisoformat(slp["end_time"])
                wake_times.append(dt.hour + dt.minute/60)
            except: pass

    if len(wake_times) >= 3:
        wake_std  = statistics.stdev(wake_times)
        # Std < 0.5 saat = çok düzenli (100), > 3 saat = düzensiz (0)
        regularity_score = max(0, round(100 - wake_std * 33))
    else:
        wake_std         = None
        regularity_score = None

    # Markov geçiş sayısı
    markov_count = conn.execute(
        "SELECT COUNT(*) as n FROM markov_transitions WHERE person_id=?", (pid,)
    ).fetchone()["n"]

    # ── 5. Genel kalite skoru ─────────────────────────────────────────────────
    if metrics_quality:
        avg_realism    = round(sum(m["realism_score"] for m in metrics_quality) / len(metrics_quality))
        overall_score  = round(avg_realism * 0.5 + act_realism * 0.3 + 
                              (regularity_score or 70) * 0.2)
    else:
        avg_realism   = 0
        overall_score = 0

    conn.close()
    return jsonify({
        "person":             dict(person),
        "period_days":        days_back,
        "total_sensor_records": len(sensor_rows),
        "metrics":            metrics_quality,
        "activity_distribution": {
            "observed":    {k: round(v,3) for k,v in act_dist.items()},
            "expected":    expected_act_dist,
            "kl_divergence": act_kl,
            "realism_score": act_realism,
        },
        "regularity": {
            "wake_times_n":    len(wake_times),
            "wake_std_hours":  round(wake_std, 3) if wake_std else None,
            "regularity_score": regularity_score,
        },
        "markov": {
            "transitions_learned": markov_count,
            "active": markov_count > 0,
        },
        "scores": {
            "sensor_realism":   avg_realism,
            "activity_realism": act_realism,
            "regularity":       regularity_score,
            "overall":          overall_score,
        }
    })


# ── KİŞİSEL İSTATİSTİKSEL PROFİL ─────────────────────────────────────────────

@bp.route("/api/personal_stats/<int:pid>", methods=["GET"])
def get_personal_stats_endpoint(pid):
    """Kişinin aktivite bazlı istatistiksel profilini döndür."""
    conn   = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    rows = conn.execute("""
        SELECT metric, activity_type, mean, std, n, updated_at
        FROM personal_stats WHERE person_id=?
        ORDER BY metric, activity_type
    """, (pid,)).fetchall()

    if not rows:
        build_personal_stats(conn, pid)
        rows = conn.execute("""
            SELECT metric, activity_type, mean, std, n, updated_at
            FROM personal_stats WHERE person_id=?
            ORDER BY metric, activity_type
        """, (pid,)).fetchall()

    conn.close()
    return jsonify({
        "person": dict(person),
        "stats":  [dict(r) for r in rows],
    })


@bp.route("/api/personal_stats/<int:pid>/rebuild", methods=["POST"])
def rebuild_personal_stats(pid):
    """Kişisel istatistiksel profili yeniden oluştur."""
    conn = get_db()
    build_personal_stats(conn, pid)
    conn.close()
    return jsonify({"ok": True, "message": "Profil güncellendi"})

# ── MARKOV GEÇİŞ MATRİSİ ─────────────────────────────────────────────────────

@bp.route("/api/markov/<int:pid>", methods=["GET"])
def get_markov(pid):
    """
    Kişinin Markov geçiş matrisini döndür.
    Arayüzde aktivite geçiş grafiği çizmek için kullanılır.
    """
    conn   = get_db()
    person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"error": "Kişi bulunamadı"}), 404

    # Matris yoksa oluştur
    count = conn.execute(
        "SELECT COUNT(*) as n FROM markov_transitions WHERE person_id=?", (pid,)
    ).fetchone()["n"]
    if count == 0:
        built = build_markov_matrix(conn, pid)
        if not built:
            conn.close()
            return jsonify({"error": "Yeterli veri yok (min 10 kayıt gerekli)"}), 400

    rows = conn.execute("""
        SELECT from_activity, to_activity, hour_block, count, probability
        FROM markov_transitions WHERE person_id=?
        ORDER BY from_activity, hour_block, probability DESC
    """, (pid,)).fetchall()

    # En sık geçişleri bul (görselleştirme için)
    top_transitions = conn.execute("""
        SELECT from_activity, to_activity,
               SUM(count) as total_count,
               AVG(probability) as avg_prob
        FROM markov_transitions WHERE person_id=?
        GROUP BY from_activity, to_activity
        ORDER BY total_count DESC LIMIT 20
    """, (pid,)).fetchall()

    # Aktivite başına en olası sonraki aktivite
    most_likely = conn.execute("""
        SELECT from_activity,
               to_activity,
               MAX(probability) as max_prob
        FROM markov_transitions WHERE person_id=?
        GROUP BY from_activity
        ORDER BY from_activity
    """, (pid,)).fetchall()

    # Saat bloğu isimleri
    hour_block_labels = {
        0: "Gece (00-06)",
        1: "Sabah (06-08)",
        2: "Öğleden önce (08-12)",
        3: "Öğle (12-14)",
        4: "Öğleden sonra (14-18)",
        5: "Akşam (18-21)",
        6: "Gece (21-23)",
    }

    conn.close()
    return jsonify({
        "person":              dict(person),
        "total_transitions":   len(rows),
        "matrix":              [dict(r) for r in rows],
        "top_transitions":     [dict(r) for r in top_transitions],
        "most_likely_next":    [dict(r) for r in most_likely],
        "hour_block_labels":   hour_block_labels,
    })


@bp.route("/api/markov/<int:pid>/rebuild", methods=["POST"])
def rebuild_markov(pid):
    """Markov matrisini son verilerden yeniden oluştur."""
    conn = get_db()
    built = build_markov_matrix(conn, pid)
    conn.close()
    invalidate_markov_cache(pid)
    if built:
        return jsonify({"ok": True, "message": "Markov matrisi güncellendi"})
    return jsonify({"ok": False, "message": "Yeterli veri yok"}), 400


# ── VERİ KATKISI ──────────────────────────────────────────────────────────────

@bp.route("/api/monitoring_profiles", methods=["GET"])
def get_monitoring_profiles():
    conn=get_db(); rows=conn.execute("SELECT * FROM monitoring_profiles WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@bp.route("/api/monitoring_profiles", methods=["POST"])
def add_monitoring_profile():
    d=request.json; name=d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}),400
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO monitoring_profiles (name,profile_type,environment,description,location,icon,color) VALUES (?,?,?,?,?,?,?)",
        (name,d.get("profile_type","insan"),d.get("environment","genel"),
         d.get("description",""),d.get("location",""),d.get("icon","📍"),d.get("color","#534AB7")))
    conn.commit(); nid=c.lastrowid; conn.close(); return jsonify({"id":nid,"name":name}),201

@bp.route("/api/monitoring_profiles/<int:nid>", methods=["DELETE"])
def delete_monitoring_profile(nid):
    conn=get_db(); conn.execute("UPDATE monitoring_profiles SET active=0 WHERE id=?",(nid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@bp.route("/api/custom_activities", methods=["GET"])
def get_custom_activities():
    conn=get_db(); rows=conn.execute("SELECT * FROM custom_activities WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@bp.route("/api/custom_activities", methods=["POST"])
def add_custom_activity():
    d=request.json; name=d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}),400
    conn=get_db(); c=conn.cursor()
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
    conn.commit(); aid=c.lastrowid; conn.close(); return jsonify({"id":aid,"name":name}),201

@bp.route("/api/custom_activities/<int:aid>", methods=["DELETE"])
def delete_custom_activity(aid):
    conn=get_db(); conn.execute("UPDATE custom_activities SET active=0 WHERE id=?",(aid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@bp.route("/api/environments", methods=["GET"])
def get_environments():
    conn=get_db(); rows=conn.execute("SELECT * FROM environments WHERE active=1 ORDER BY id").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@bp.route("/api/environments", methods=["POST"])
def add_environment():
    d=request.json; name=d.get("name","").strip()
    if not name: return jsonify({"error":"İsim zorunlu"}),400
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO environments (name,type,description,location) VALUES (?,?,?,?)",
        (name,d.get("type","genel"),d.get("description",""),d.get("location","")))
    conn.commit(); eid=c.lastrowid; conn.close(); return jsonify({"id":eid,"name":name}),201

@bp.route("/api/environments/<int:eid>", methods=["DELETE"])
def delete_environment(eid):
    conn=get_db(); conn.execute("UPDATE environments SET active=0 WHERE id=?",(eid,))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@bp.route("/api/contribute/simulate", methods=["POST"])
def simulate_contribution():
    d=request.json; mpid=int(d.get("profile_id",0)); aid=int(d.get("activity_id",0))
    conn=get_db()
    profile=conn.execute("SELECT * FROM monitoring_profiles WHERE id=? AND active=1",(mpid,)).fetchone()
    if not profile: conn.close(); return jsonify({"error":"Profil bulunamadı"}),404
    act=conn.execute("SELECT * FROM custom_activities WHERE id=? AND active=1",(aid,)).fetchone()
    if not act: conn.close(); return jsonify({"error":"Aktivite bulunamadı"}),404
    try:
        sd=datetime.strptime(d.get("date_start"),"%Y-%m-%d") if d.get("date_start") else datetime.now()-timedelta(days=7)
        ed=datetime.strptime(d.get("date_end"),  "%Y-%m-%d") if d.get("date_end")   else datetime.now()
    except: sd=datetime.now()-timedelta(days=7); ed=datetime.now()
    if (ed-sd).days>90: ed=sd+timedelta(days=90)
    dn=act["distribution"] or "normal"
    try: dp=_json.loads(act["dist_params"] or "{}")
    except: dp={}
    if not dp: dp={"mean":act["hr_base"],"std":act["hr_noise"]}
    now=datetime.now(); recs=[]; cur=sd
    while cur<=ed:
        wday=cur.weekday(); iw=1 if wday>=5 else 0
        freq=act["frequency_per_day"]
        iv=max(1,max(1,act["hour_end"]-act["hour_start"])//max(freq,1))
        for i in range(freq):
            bh=act["hour_start"]+i*iv
            sdt=cur.replace(hour=min(bh,23),minute=0,second=0)+timedelta(minutes=random.randint(-15,15))
            dur=random.randint(act["duration_min"],act["duration_max"])
            hr=int(sample_distribution(dn,dp,40,200))
            spo2=round(sample_distribution("normal",{"mean":act["spo2_base"],"std":0.5},88,100),1)
            stress=int(sample_distribution("normal",{"mean":act["stress_base"],"std":10},5,99))
            meta=_json.dumps({"profile_name":profile["name"],"profile_type":profile["profile_type"],
                "environment":profile["environment"],"activity":act["name"],
                "distribution":dn,"dist_params":dp,"duration_mins":dur,
                "day_of_week":wday,"is_weekend":iw},ensure_ascii=False)
            conn.execute("""INSERT INTO contribution_log
                (profile_id,custom_activity_id,profile_name,profile_type,
                 activity_name,environment_name,environment_type,
                 start_time,end_time,duration_mins,heart_rate,spo2,stress_level,
                 hour_of_day,day_of_week,is_weekend,distribution_used,metadata,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mpid,aid,profile["name"],profile["profile_type"],act["name"],
                 profile["environment"],profile["profile_type"],
                 sdt.isoformat(),(sdt+timedelta(minutes=dur)).isoformat(),dur,
                 hr,spo2,stress,bh,wday,iw,dn,meta,now.isoformat()))
            recs.append({"date":sdt.strftime("%d/%m"),"start":sdt.strftime("%H:%M"),
                "duration_mins":dur,"heart_rate":hr,"spo2":spo2,"stress_level":stress})
        cur+=timedelta(days=1)
    conn.commit(); conn.close()
    return jsonify({"ok":True,"records_added":len(recs),"preview":recs[:5]})

@bp.route("/api/contribute/stats", methods=["GET"])
def contribution_stats():
    conn=get_db()
    total=conn.execute("SELECT COUNT(*) as n FROM contribution_log").fetchone()["n"]
    ba=conn.execute("""SELECT activity_name,COUNT(*) as cnt,ROUND(AVG(heart_rate),1) as avg_hr,
        ROUND(AVG(spo2),1) as avg_spo2,ROUND(AVG(stress_level),1) as avg_stress,ROUND(AVG(duration_mins),1) as avg_dur
        FROM contribution_log GROUP BY activity_name ORDER BY cnt DESC""").fetchall()
    be=conn.execute("""SELECT environment_name,environment_type,COUNT(*) as cnt
        FROM contribution_log GROUP BY environment_name ORDER BY cnt DESC""").fetchall()
    conn.close()
    return jsonify({"total_records":total,"by_activity":[dict(r) for r in ba],"by_environment":[dict(r) for r in be]})

@bp.route("/api/contribute/export", methods=["GET"])
def export_contribution():
    pid=request.args.get("profile_id",type=int); conn=get_db()
    q="SELECT * FROM contribution_log WHERE 1=1"; params=[]
    if pid: q+=" AND profile_id=?"; params.append(pid)
    rows=conn.execute(q+" ORDER BY start_time DESC LIMIT 5000",params).fetchall(); conn.close()
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(["profile_name","profile_type","activity_name","environment_name",
        "start_time","end_time","duration_mins","heart_rate","spo2","stress_level",
        "hour_of_day","day_of_week","is_weekend","distribution_used","metadata"])
    for r in rows:
        w.writerow([r["profile_name"],r["profile_type"],r["activity_name"],r["environment_name"],
            r["start_time"],r["end_time"],r["duration_mins"],r["heart_rate"],r["spo2"],r["stress_level"],
            r["hour_of_day"],r["day_of_week"],r["is_weekend"],r["distribution_used"],r["metadata"]])
    out.seek(0)
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename=katki_verisi.csv"})