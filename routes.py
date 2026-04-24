"""
routes.py — Flask API endpoint'ları
Tüm HTTP ve WebSocket route tanımları.
Her fonksiyon yalnızca isteği alır, iş mantığını simulator.py veya db.py'ye devreder.
"""
from flask import jsonify, request, send_from_directory, Response
from datetime import datetime, timedelta
import random, csv, io, unicodedata, json as _json, statistics
from collections import defaultdict

from db import (get_db, db_get_persons, db_get_current_states, db_get_anomalies,
                db_get_smart_alerts, db_get_sensor_history, db_get_activity_history,
                db_get_locations, db_get_compare)
from simulator import (ACTIVITIES, ANOMALY_RULES, AVATAR_COLORS, WEATHER_CONDITIONS,
                       LOCATIONS, current_weather, current_temp, sim_speed,
                       compute_health_score, seed_historical_data, check_smart_alerts,
                       sample_distribution)
import simulator


def register_routes(app, socketio):
    """Tüm route'ları Flask uygulamasına kaydet."""

    @app.route("/")
    def home():
        return send_from_directory(".", "index.html")

    @socketio.on("connect")
    def on_connect():
        from flask_socketio import emit
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

    # ── PERSONS ───────────────────────────────────────────────────────────────

    @app.route("/api/persons", methods=["GET"])
    def get_persons():
        return jsonify(db_get_persons())

    @app.route("/api/persons", methods=["POST"])
    def add_person():
        d     = request.json
        name  = d.get("name","").strip()
        if not name: return jsonify({"error":"İsim zorunlu"}), 400
        color = d.get("avatar_color", random.choice(AVATAR_COLORS))
        conn  = get_db(); c = conn.cursor()
        c.execute("INSERT INTO persons (name,age,city,sleep_score,avatar_color) VALUES (?,?,?,?,?)",
                  (name, d.get("age",random.randint(20,60)), d.get("city","").strip(),
                   random.randint(5,10), color))
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
                c.execute(f"UPDATE persons SET {field}=? WHERE id=?", (d[field], pid))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

    @app.route("/api/persons/<int:pid>", methods=["DELETE"])
    def delete_person(pid):
        conn = get_db()
        conn.execute("UPDATE persons SET active=0 WHERE id=?", (pid,))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

    # ── STATE & SENSORS ───────────────────────────────────────────────────────

    @app.route("/api/state", methods=["GET"])
    def get_all_states():
        return jsonify(db_get_current_states())

    @app.route("/api/history/<int:pid>", methods=["GET"])
    def get_history(pid):
        return jsonify(db_get_activity_history(pid))

    @app.route("/api/sensors/<int:pid>", methods=["GET"])
    def get_sensor_history(pid):
        limit = int(request.args.get("limit", 60))
        return jsonify(db_get_sensor_history(pid, limit))

    @app.route("/api/anomalies", methods=["GET"])
    def get_anomalies():
        return jsonify(db_get_anomalies())

    @app.route("/api/smart_alerts", methods=["GET"])
    def get_smart_alerts():
        return jsonify(db_get_smart_alerts())

    @app.route("/api/compare", methods=["GET"])
    def compare_persons():
        return jsonify(db_get_compare())

    @app.route("/api/location", methods=["GET"])
    def get_locations():
        return jsonify(db_get_locations())

    @app.route("/api/avatar_colors", methods=["GET"])
    def avatar_colors():
        return jsonify(AVATAR_COLORS)

    # ── SİMÜLASYON HIZI ──────────────────────────────────────────────────────

    @app.route("/api/sim_speed", methods=["GET","POST"])
    def sim_speed_endpoint():
        if request.method == "POST":
            speed = int(request.json.get("speed", 1))
            simulator.sim_speed = max(1, min(10, speed))
            return jsonify({"speed": simulator.sim_speed})
        return jsonify({"speed": simulator.sim_speed})

    # ── ÖZET ─────────────────────────────────────────────────────────────────

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
            "total_persons": total, "avg_steps": avg["s"] or 0,
            "avg_calories": avg["c"] or 0, "avg_active_mins": avg["a"] or 0,
            "avg_heart_rate": avg["hr"] or 0, "avg_stress": avg["stress"] or 0,
            "anomaly_count": acnt, "smart_alert_count": salrt,
            "weather": {
                "condition":    simulator.current_weather["condition"],
                "condition_en": simulator.current_weather["condition_en"],
                "icon":         simulator.current_weather["icon"],
                "temp":         round(simulator.current_temp, 1),
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
        if not row: return jsonify({"error":"Kişi bulunamadı"}), 404
        return jsonify(dict(row))

    @app.route("/api/timeline/<int:pid>", methods=["GET"])
    def get_timeline(pid):
        conn = get_db()
        rows = conn.execute("""SELECT activity_name,activity_name_en,activity_icon,activity_type,
            start_time,end_time,duration_mins,steps_snap,calories_snap,heart_rate_avg,recorded_at
            FROM activity_log WHERE person_id=?
            AND recorded_at>=datetime('now','-7 days') ORDER BY recorded_at DESC LIMIT 80""", (pid,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

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

    @app.route("/api/trend/<int:pid>", methods=["GET"])
    def get_trend(pid):
        conn  = get_db(); trend = []
        for i in range(6,-1,-1):
            d   = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
            row = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
                COALESCE(MAX(calories_snap),0) as calories,COALESCE(AVG(heart_rate_avg),0) as avg_hr,
                COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as active_mins,
                COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as sleep_mins
                FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
            sensor = conn.execute("""SELECT ROUND(AVG(stress_level),1) as avg_stress,
                ROUND(AVG(heart_rate),1) as avg_hr2
                FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
            trend.append({"date":d,"steps":row["steps"] or 0,"calories":round(row["calories"] or 0,1),
                "avg_hr":round((row["avg_hr"] or 0) if row["avg_hr"] else (sensor["avg_hr2"] or 0),1),
                "active_mins":row["active_mins"] or 0,"sleep_mins":row["sleep_mins"] or 0,
                "avg_stress":sensor["avg_stress"] or 0})
        conn.close()
        return jsonify(trend)

    # ── CSV EXPORT ────────────────────────────────────────────────────────────

    @app.route("/api/export/<int:pid>", methods=["GET"])
    def export_person(pid):
        conn   = get_db()
        person = conn.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
        if not person:
            conn.close(); return jsonify({"error":"Kişi bulunamadı"}), 404
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
                r = conn.execute("""SELECT COALESCE(MAX(steps_snap),0) as steps,
                    COALESCE(MAX(calories_snap),0) as cal,
                    COALESCE(SUM(CASE WHEN activity_type='active' THEN duration_mins ELSE 0 END),0) as act,
                    COALESCE(SUM(CASE WHEN activity_type='sleep'  THEN duration_mins ELSE 0 END),0) as slp,
                    COALESCE(AVG(heart_rate_avg),0) as hr,COUNT(*) as ev
                    FROM activity_log WHERE person_id=? AND date(start_time,'localtime')=?""",(pid,d)).fetchone()
                s = conn.execute("""SELECT ROUND(AVG(stress_level),1) as st,ROUND(AVG(spo2),1) as sp
                    FROM sensor_log WHERE person_id=? AND date(recorded_at,'localtime')=?""",(pid,d)).fetchone()
                writer.writerow([d,r["steps"],round(r["cal"] or 0,1),r["act"],r["slp"],
                    round(r["hr"] or 0,1),s["st"] or 0,s["sp"] or 0,r["ev"]])
            filename = person["name"]+"_gunluk.csv"
        conn.close()
        output.seek(0)
        safe_fn = unicodedata.normalize("NFKD",filename).encode("ascii","ignore").decode()
        return Response("\ufeff"+output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition":"attachment; filename="+safe_fn})

    # ── AI ANALİZ ─────────────────────────────────────────────────────────────

    @app.route("/api/ai_analyze/<int:pid>", methods=["GET"])
    def ai_analyze(pid):
        import urllib.request
        conn = get_db()
        row  = conn.execute("""SELECT p.name,p.avatar_color,cs.chart_active,cs.chart_rest,cs.chart_meal,cs.chart_sleep,
            cs.steps,cs.active_mins,cs.calories,cs.screen_mins,cs.out_count,cs.meal_count,p.sleep_score,
            cs.heart_rate,cs.spo2,cs.skin_temp,cs.hrv,cs.stress_level,cs.mood
            FROM persons p JOIN current_state cs ON p.id=cs.person_id
            WHERE p.id=? AND p.active=1""",(pid,)).fetchone()
        conn.close()
        if not row: return jsonify({"error":"Kişi bulunamadı"}),404
        d   = dict(row)
        tot = (d["chart_active"] or 0)+(d["chart_rest"] or 0)+(d["chart_meal"] or 0)+(d["chart_sleep"] or 8)
        pct = lambda v: round((v/tot)*100) if tot>0 else 0
        prompt = (f"Kişi: {d['name']}. Uyku skoru: {d['sleep_score']}/10. "
                  f"Adım: {d['steps']}, Aktif: {d['active_mins']} dk. "
                  f"Nabız: {d['heart_rate']} bpm, SpO₂: {d['spo2']}%, Stres: {d['stress_level']}/100. "
                  f"Ruh hali: {d['mood']}. "
                  f"Bu verilere göre 3-4 cümlelik Türkçe yorum yaz.")
        payload = _json.dumps({"model":"claude-sonnet-4-20250514","max_tokens":1000,
            "messages":[{"role":"user","content":prompt}]}).encode()
        from config import ANTHROPIC_API_KEY
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",data=payload,
            headers={"Content-Type":"application/json","anthropic-version":"2023-06-01",
                     "x-api-key":ANTHROPIC_API_KEY},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=30) as resp:
                result = _json.loads(resp.read())
                text   = "".join(b.get("text","") for b in result.get("content",[]))
                return jsonify({"text":text})
        except urllib.error.HTTPError as e:
            return jsonify({"error":f"HTTP {e.code}: {e.read().decode()}"}),500
        except Exception as e:
            return jsonify({"error":str(e)}),500

    # ── İZLEME PROFİLİ ───────────────────────────────────────────────────────

    @app.route("/api/monitoring_profiles", methods=["GET"])
    def get_monitoring_profiles():
        conn = get_db()
        rows = conn.execute("SELECT * FROM monitoring_profiles WHERE active=1 ORDER BY id").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/monitoring_profiles", methods=["POST"])
    def add_monitoring_profile():
        d    = request.json; name = d.get("name","").strip()
        if not name: return jsonify({"error":"İsim zorunlu"}),400
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO monitoring_profiles (name,profile_type,environment,description,location,icon,color) VALUES (?,?,?,?,?,?,?)",
            (name,d.get("profile_type","insan"),d.get("environment","genel"),
             d.get("description",""),d.get("location",""),d.get("icon","📍"),d.get("color","#534AB7")))
        conn.commit(); eid=c.lastrowid; conn.close()
        return jsonify({"id":eid,"name":name}),201

    @app.route("/api/monitoring_profiles/<int:pid>", methods=["DELETE"])
    def delete_monitoring_profile(pid):
        conn=get_db(); conn.execute("UPDATE monitoring_profiles SET active=0 WHERE id=?",(pid,))
        conn.commit(); conn.close(); return jsonify({"ok":True})

    # ── ÖZEL AKTİVİTE ────────────────────────────────────────────────────────

    @app.route("/api/custom_activities", methods=["GET"])
    def get_custom_activities():
        conn = get_db()
        rows = conn.execute("SELECT * FROM custom_activities WHERE active=1 ORDER BY id").fetchall()
        conn.close(); return jsonify([dict(r) for r in rows])

    @app.route("/api/custom_activities", methods=["POST"])
    def add_custom_activity():
        d = request.json; name = d.get("name","").strip()
        if not name: return jsonify({"error":"İsim zorunlu"}),400
        conn=get_db(); c=conn.cursor()
        c.execute("""INSERT INTO custom_activities
            (name,description,environment,hour_start,hour_end,duration_min,duration_max,
             frequency_per_day,hr_base,hr_noise,spo2_base,stress_base,icon,color,distribution,dist_params)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name,d.get("description",""),d.get("environment","genel"),
             int(d.get("hour_start",8)),int(d.get("hour_end",18)),
             int(d.get("duration_min",10)),int(d.get("duration_max",60)),
             int(d.get("frequency_per_day",1)),
             int(d.get("hr_base",75)),int(d.get("hr_noise",8)),
             float(d.get("spo2_base",98.0)),int(d.get("stress_base",30)),
             d.get("icon","🔵"),d.get("color","#534AB7"),
             d.get("distribution","normal"),
             _json.dumps(d.get("dist_params",{}))))
        conn.commit(); aid=c.lastrowid; conn.close()
        return jsonify({"id":aid,"name":name}),201

    @app.route("/api/custom_activities/<int:aid>", methods=["DELETE"])
    def delete_custom_activity(aid):
        conn=get_db(); conn.execute("UPDATE custom_activities SET active=0 WHERE id=?",(aid,))
        conn.commit(); conn.close(); return jsonify({"ok":True})

    # ── ORTAM ─────────────────────────────────────────────────────────────────

    @app.route("/api/environments", methods=["GET"])
    def get_environments():
        conn=get_db(); rows=conn.execute("SELECT * FROM environments WHERE active=1 ORDER BY id").fetchall()
        conn.close(); return jsonify([dict(r) for r in rows])

    @app.route("/api/environments", methods=["POST"])
    def add_environment():
        d=request.json; name=d.get("name","").strip()
        if not name: return jsonify({"error":"İsim zorunlu"}),400
        conn=get_db(); c=conn.cursor()
        c.execute("INSERT INTO environments (name,type,description,location) VALUES (?,?,?,?)",
            (name,d.get("type","genel"),d.get("description",""),d.get("location","")))
        conn.commit(); eid=c.lastrowid; conn.close()
        return jsonify({"id":eid,"name":name}),201

    @app.route("/api/environments/<int:eid>", methods=["DELETE"])
    def delete_environment(eid):
        conn=get_db(); conn.execute("UPDATE environments SET active=0 WHERE id=?",(eid,))
        conn.commit(); conn.close(); return jsonify({"ok":True})

    # ── DAĞILIM BİLGİSİ ──────────────────────────────────────────────────────

    @app.route("/api/distributions", methods=["GET"])
    def get_distributions():
        """Desteklenen dağılımlar ve parametreleri."""
        return jsonify([
            {"name":"normal",     "label":"Normal (Gaussian)",
             "params":[{"key":"mean","label":"Ortalama (μ)","default":75},
                       {"key":"std", "label":"Standart Sapma (σ)","default":10}]},
            {"name":"uniform",    "label":"Düzgün (Uniform)",
             "params":[{"key":"low", "label":"Alt Sınır","default":60},
                       {"key":"high","label":"Üst Sınır","default":90}]},
            {"name":"exponential","label":"Üstel (Exponential)",
             "params":[{"key":"scale", "label":"Ölçek (1/λ)","default":20},
                       {"key":"offset","label":"Başlangıç Değeri","default":40}]},
            {"name":"poisson",    "label":"Poisson",
             "params":[{"key":"lam","label":"Lambda (λ)","default":5}]},
            {"name":"lognormal",  "label":"Log-Normal",
             "params":[{"key":"mean", "label":"μ (log)","default":4.3},
                       {"key":"sigma","label":"σ (log)","default":0.3}]},
            {"name":"triangular", "label":"Üçgen (Triangular)",
             "params":[{"key":"low", "label":"Alt Sınır","default":50},
                       {"key":"mode","label":"Tepe Nokta","default":75},
                       {"key":"high","label":"Üst Sınır","default":100}]},
            {"name":"beta",       "label":"Beta",
             "params":[{"key":"alpha","label":"Alpha (α)","default":2},
                       {"key":"beta", "label":"Beta (β)","default":5},
                       {"key":"scale","label":"Ölçek","default":100}]},
        ])

    # ── VERİ KATKISI: SİMÜLASYON ─────────────────────────────────────────────

    @app.route("/api/contribute/simulate", methods=["POST"])
    def simulate_contribution():
        d    = request.json
        mpid = int(d.get("profile_id",0))
        aid  = int(d.get("activity_id",0))
        date_start = d.get("date_start")
        date_end   = d.get("date_end")
        conn = get_db()
        profile = conn.execute("SELECT * FROM monitoring_profiles WHERE id=? AND active=1",(mpid,)).fetchone()
        if not profile: conn.close(); return jsonify({"error":"Profil bulunamadı"}),404
        act = conn.execute("SELECT * FROM custom_activities WHERE id=? AND active=1",(aid,)).fetchone()
        if not act: conn.close(); return jsonify({"error":"Aktivite bulunamadı"}),404
        try:
            start_date = datetime.strptime(date_start,"%Y-%m-%d") if date_start else datetime.now()-timedelta(days=7)
            end_date   = datetime.strptime(date_end,  "%Y-%m-%d") if date_end   else datetime.now()
        except:
            start_date = datetime.now()-timedelta(days=7); end_date = datetime.now()
        if (end_date-start_date).days > 90:
            end_date = start_date + timedelta(days=90)

        # Dağılım parametrelerini çöz
        dist_name = act["distribution"] or "normal"
        try:
            dist_params = _json.loads(act["dist_params"] or "{}")
        except:
            dist_params = {}
        # Varsayılan parametreler
        if not dist_params:
            dist_params = {"mean": act["hr_base"], "std": act["hr_noise"]}

        now = datetime.now(); records = []; current = start_date
        while current <= end_date:
            weekday    = current.weekday(); is_weekend = 1 if weekday>=5 else 0
            freq       = act["frequency_per_day"]
            hour_range = max(1, act["hour_end"]-act["hour_start"])
            interval   = max(1, hour_range//max(freq,1))
            for i in range(freq):
                base_hour  = act["hour_start"]+i*interval
                jitter_min = random.randint(-15,15)
                start_dt   = current.replace(hour=min(base_hour,23),minute=0,second=0)+timedelta(minutes=jitter_min)
                dur_mins   = random.randint(act["duration_min"],act["duration_max"])
                end_dt     = start_dt+timedelta(minutes=dur_mins)

                # Dağılıma göre biyometrik üret
                hr_params = {**dist_params}
                if dist_name == "normal" and "mean" not in hr_params:
                    hr_params["mean"] = act["hr_base"]; hr_params["std"] = act["hr_noise"]
                hr     = int(sample_distribution(dist_name, hr_params, 40, 200))
                spo2   = round(sample_distribution("normal",{"mean":act["spo2_base"],"std":0.5},88,100),1)
                stress = int(sample_distribution("normal",{"mean":act["stress_base"],"std":10},5,99))

                metadata = _json.dumps({
                    "profile_name":   profile["name"],
                    "profile_type":   profile["profile_type"],
                    "environment":    profile["environment"],
                    "activity":       act["name"],
                    "distribution":   dist_name,
                    "dist_params":    dist_params,
                    "duration_mins":  dur_mins,
                    "day_of_week":    weekday,
                    "is_weekend":     is_weekend,
                }, ensure_ascii=False)

                conn.execute("""INSERT INTO contribution_log
                    (profile_id,custom_activity_id,profile_name,profile_type,
                     activity_name,environment_name,environment_type,
                     start_time,end_time,duration_mins,
                     heart_rate,spo2,stress_level,
                     hour_of_day,day_of_week,is_weekend,
                     distribution_used,metadata,recorded_at)
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

    # ── VERİ KATKISI: SAPMA ANALİZİ ──────────────────────────────────────────

    @app.route("/api/contribute/pattern/<int:mpid>", methods=["GET"])
    def contribute_pattern(mpid):
        conn = get_db()
        profile = conn.execute("SELECT * FROM monitoring_profiles WHERE id=?",(mpid,)).fetchone()
        if not profile: conn.close(); return jsonify({"error":"Profil bulunamadı"}),404
        rows = conn.execute("""SELECT activity_name,start_time,end_time,duration_mins,
            heart_rate,spo2,stress_level,hour_of_day,day_of_week,is_weekend,distribution_used
            FROM contribution_log WHERE profile_id=? ORDER BY start_time ASC""",(mpid,)).fetchall()
        if not rows: conn.close(); return jsonify({"error":"Bu profil için henüz veri yok"}),404
        by_activity = defaultdict(list)
        for r in rows:
            by_activity[r["activity_name"]].append(dict(r))
        activity_stats = []; all_alerts = []
        for act_name, recs in by_activity.items():
            def stat(vals):
                vals = [v for v in vals if v is not None and v>0]
                if len(vals)<2: return {"mean":vals[0] if vals else 0,"std":0,"low":vals[0] if vals else 0,"high":vals[0] if vals else 0,"n":len(vals)}
                m=sum(vals)/len(vals); s=statistics.stdev(vals)
                return {"mean":round(m,1),"std":round(s,1),"min":round(min(vals),1),"max":round(max(vals),1),"low":round(m-s,1),"high":round(m+s,1),"n":len(vals)}
            hr_stat  = stat([r["heart_rate"]    for r in recs])
            spo2_stat= stat([r["spo2"]          for r in recs])
            str_stat = stat([r["stress_level"]  for r in recs])
            dur_stat = stat([r["duration_mins"] for r in recs])
            daily = defaultdict(list)
            for r in recs:
                try: daily[datetime.fromisoformat(r["start_time"]).strftime("%d/%m")].append(r)
                except: pass
            daily_series = []
            for day, drecs in sorted(daily.items()):
                avg_hr  = round(sum(r["heart_rate"]   for r in drecs)/len(drecs),1)
                avg_sp  = round(sum(r["spo2"]         for r in drecs)/len(drecs),1)
                avg_st  = round(sum(r["stress_level"] for r in drecs)/len(drecs),1)
                avg_dur = round(sum(r["duration_mins"]for r in drecs)/len(drecs),1)
                devs = {}
                for key,val,norm in [("heart_rate",avg_hr,hr_stat),("spo2",avg_sp,spo2_stat),
                                     ("stress",avg_st,str_stat),("duration",avg_dur,dur_stat)]:
                    if norm["std"]>0:
                        dev = round((val-norm["mean"])/norm["std"],2); devs[key]=dev
                        if abs(dev)>=1.5:
                            severity="kritik" if abs(dev)>=2.5 else "uyarı"
                            all_alerts.append({"date":day,"activity":act_name,"metric":key,
                                "value":val,"norm_mean":norm["mean"],"deviation":dev,"severity":severity,"profile":profile["name"]})
                    else: devs[key]=0
                daily_series.append({"date":day,"avg_hr":avg_hr,"avg_spo2":avg_sp,
                    "avg_stress":avg_st,"avg_duration":avg_dur,"deviations":devs,"count":len(drecs)})
            activity_stats.append({"activity_name":act_name,"record_count":len(recs),
                "hr_stat":hr_stat,"spo2_stat":spo2_stat,"stress_stat":str_stat,"duration_stat":dur_stat,
                "daily_series":daily_series,
                "distribution": recs[0].get("distribution_used","normal") if recs else "normal"})
        conn.close()
        return jsonify({"profile":dict(profile),"activity_stats":activity_stats,
            "alerts":sorted(all_alerts,key=lambda x:abs(x["deviation"]),reverse=True)[:20],
            "total_records":len(rows)})

    # ── VERİ KATKISI: EXPORT & STATS ─────────────────────────────────────────

    @app.route("/api/contribute/export", methods=["GET"])
    def export_contribution():
        pid = request.args.get("profile_id",type=int)
        conn = get_db()
        q = "SELECT * FROM contribution_log WHERE 1=1"
        params = []
        if pid: q += " AND profile_id=?"; params.append(pid)
        q += " ORDER BY start_time DESC LIMIT 5000"
        rows = conn.execute(q,params).fetchall(); conn.close()
        output = io.StringIO()
        writer = csv.writer(output)
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

    # ── ANALİZ (büyük endpoint'ler) ─────────────────────────────────────────
    # Bu endpoint'ler uzun olduğu için app_analysis.py'den import edilir
    from analysis_routes import register_analysis_routes
    register_analysis_routes(app)