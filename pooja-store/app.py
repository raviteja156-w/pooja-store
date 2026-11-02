import os, json, sqlite3, datetime, requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException
from pypdf import PdfReader

app = Flask(__name__, static_folder="static")
KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
def _env(n):
    return os.environ.get(n, "").strip().strip("\"'").strip()


SB = _env("SUPABASE_URL").rstrip("/")
if SB.endswith("/rest/v1"):
    SB = SB[:-8]
SBK = _env("SUPABASE_KEY")
H = {"apikey": SBK, "Content-Type": "application/json"}
if SBK.startswith("eyJ"):  # old-style JWT keys (anon / service_role) also go in Authorization
    H["Authorization"] = f"Bearer {SBK}"
# new-style keys (sb_secret_... / sb_publishable_...) are NOT JWTs: send only the apikey header
_l = sqlite3.connect(os.environ.get("DB_PATH", "prepmate.db"), check_same_thread=False)
_l.execute("create table if not exists kv(k text primary key, v text)")


# ---- storage: Supabase (table "kv") when configured, else local SQLite ----
def _chk(r):
    if r.ok:
        return
    hint = {401: "Supabase rejected the key. Re-copy SUPABASE_KEY (service_role / secret key) from Supabase > Project Settings > API, no quotes or spaces.",
            403: "Key has no permission. Use the service_role / secret key, not the anon key.",
            404: "Table 'kv' not found. Run supabase.sql in the Supabase SQL Editor."}.get(r.status_code, "")
    raise RuntimeError(f"Supabase {r.status_code}: {hint} {r.text[:150]}")


def kget(k, d=None):
    if SB:
        r = requests.get(f"{SB}/rest/v1/kv", headers=H, params={"k": f"eq.{k}", "select": "v"}, timeout=20)
        _chk(r)
        j = r.json()
        return j[0]["v"] if j else d
    r = _l.execute("select v from kv where k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else d


def kset(k, v):
    if SB:
        _chk(requests.post(f"{SB}/rest/v1/kv", headers={**H, "Prefer": "resolution=merge-duplicates"},
                           params={"on_conflict": "k"}, json={"k": k, "v": v}, timeout=20))
        return
    _l.execute("insert or replace into kv values(?,?)", (k, json.dumps(v)))
    _l.commit()


def ai(system, user, as_json=False, msgs=None):
    if not KEY:
        raise RuntimeError("GROQ_API_KEY not set on server")
    m = [{"role": "system", "content": system}] + (msgs or [{"role": "user", "content": user}])
    body = {"model": MODEL, "temperature": 0.6, "messages": m}
    if as_json:
        body["response_format"] = {"type": "json_object"}
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=120)
    if not r.ok:
        raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
    t = r.json()["choices"][0]["message"]["content"]
    return json.loads(t) if as_json else t


TECH = ["Python Core", "Python OOP & Advanced", "SQL & Databases", "Statistics & Probability", "Machine Learning Basics",
        "Deep Learning & Transformers", "LLMs & Prompt Engineering", "RAG & Vector Databases", "AI Agents & LangChain",
        "Flask/FastAPI & REST APIs", "Pandas & NumPy", "DSA: Arrays & Strings", "DSA: Hashing, Stack & Queue",
        "System Design Basics", "HR & Behavioural"]
APT = {"beginner": ["Percentages", "Ratio & Proportion", "Averages", "Profit & Loss", "Simple & Compound Interest",
                    "Time & Work", "Time Speed Distance", "Number Series"],
       "intermediate": ["Permutation & Combination", "Probability", "Mixtures & Alligation", "Pipes & Cisterns",
                        "Boats & Streams", "Logical Reasoning", "Data Interpretation", "Syllogisms"],
       "pro": ["Advanced Probability", "Geometry & Mensuration", "Seating Arrangement",
               "Blood Relations & Coding-Decoding", "Puzzles", "Tricky Mixed Quant", "Verbal Reasoning",
               "Data Sufficiency"]}
LV = ["beginner", "intermediate", "pro"]
CO = "TCS, Infosys, Wipro, Cognizant, Accenture, Capgemini, Deloitte, Amazon, Google, startups"


def today():
    return datetime.date.today().isoformat()


def day_no():
    s = kget("start")
    if not s:
        s = today()
        kset("start", s)
    return (datetime.date.today() - datetime.date.fromisoformat(s)).days


def persona():
    p = kget("profile", {}) or {}
    res = kget("results", [])
    t = {}
    for r in res:
        if r["total"]:
            t.setdefault(r["topic"], []).append(r["score"] / r["total"])
    weak = sorted(t, key=lambda x: sum(t[x]) / len(t[x]))[:3]
    return (f"Learner: {p.get('name', '')}, target role: {p.get('role', '')}, level: {p.get('level', '')}, "
            f"mindset: {p.get('mindset', '')}. Python/full-stack strong; fresh Gen AI, agentic AI & data science "
            f"graduate. Weak topics: {weak or 'unknown'}. Use very simple English, short lines, be encouraging.")


@app.errorhandler(Exception)
def err(e):
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    return jsonify(error=str(e)), 500


@app.get("/")
def home():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    out = {"code_version": 3, "groq_key_set": bool(KEY), "model": MODEL,
           "storage": "supabase" if SB else "local (progress resets on redeploy)"}
    if SB:
        out["supabase_host"] = SB.replace("https://", "")
        out["key_style"] = ("jwt (eyJ...)" if SBK.startswith("eyJ") else "new (sb_...)" if SBK.startswith("sb_")
                            else "UNKNOWN - check the key" if SBK else "MISSING")
        try:
            kget("health_check")
            out["supabase_ok"] = True
        except Exception as e:
            out["supabase_ok"] = False
            out["supabase_error"] = str(e)
    return jsonify(out)


@app.get("/favicon.ico")
def fav():
    return "", 204


@app.get("/api/state")
def state():
    res = kget("results", [])
    td = today()
    days = {r["ts"][:10] for r in res}
    streak, d = 0, datetime.date.today()
    while d.isoformat() in days:
        streak += 1
        d -= datetime.timedelta(days=1)
    t = {}
    for r in res:
        if r["total"]:
            t.setdefault(r["topic"], []).append(r["score"] / r["total"])
    n = day_no()
    lv = kget("apt_level", "beginner")
    return jsonify(profile=kget("profile"), streak=streak,
                   mastery={k: round(100 * sum(v) / len(v)) for k, v in t.items()},
                   tasks=sorted(kget("tasks", []), key=lambda x: x["done"])[:15],
                   today=[r for r in res if r["ts"].startswith(td)],
                   day=n + 1, tech=TECH[n % len(TECH)], apt=APT[lv][n % 8], level=lv)


@app.post("/api/profile")
def profile():
    kset("profile", request.json)
    return jsonify(ok=1)


@app.post("/api/result")
def result():
    j = request.json
    res = kget("results", [])
    res.append({"ts": datetime.datetime.now().isoformat(), "kind": j["kind"], "topic": j.get("topic", "general"),
                "score": j["score"], "total": j["total"]})
    kset("results", res[-400:])
    # aptitude auto level: 80%+ -> level up, 20% or less -> level down
    if j["kind"] == "quiz" and str(j.get("topic", "")).startswith("Aptitude") and j["total"]:
        lv = kget("apt_level", "beginner")
        i = LV.index(lv)
        r = j["score"] / j["total"]
        if r >= .8 and i < 2:
            kset("apt_level", LV[i + 1])
        elif r <= .2 and i > 0:
            kset("apt_level", LV[i - 1])
    return jsonify(ok=1)


@app.post("/api/learn")
def learn():
    n = day_no()
    topic = TECH[n % len(TECH)]
    k = f"learn_{today()}"
    c = kget(k)
    if c:
        return jsonify(c)
    j = ai("Return JSON only. You are a top interview coach. " + persona(),
           f'Topic: "{topic}". Create 8 MOST-ASKED interview questions on it, as asked by MNCs and companies like {CO} '
           'for Gen AI / Data Science / Python roles, ordered easy to hard. Each answer must be easy to memorize: '
           'NO paragraphs. Format: {"cards":[{"q":"..","tag":"Most Asked|Basic|Tricky|Coding",'
           '"companies":["TCS","Infosys"],"short":"1-2 line answer in simple words",'
           '"points":["3 to 4 crisp bullet points"],"memory":"one mnemonic or memory trick",'
           '"example":"tiny code or real-life example, or empty"}]}', True)
    j["topic"] = topic
    j["day"] = n + 1
    kset(k, j)
    return jsonify(j)


@app.post("/api/aptitude")
def aptitude():
    n = day_no()
    lv = kget("apt_level", "beginner")
    topic = APT[lv][n % 8]
    k = f"apt_{today()}_{lv}"
    c = kget(k)
    if c:
        return jsonify(c)
    j = ai("Return JSON only. You are an aptitude trainer for campus/MNC hiring tests (TCS NQT, Infosys, Wipro, "
           "Cognizant, Accenture, CAT-style). " + persona(),
           f'Level: {lv}. Topic: "{topic}". Give key formulas then 6 most-asked questions with solutions, easy to hard '
           'for this level. Format: {"formulas":["short formula or rule",".."],"cards":[{"q":"..",'
           '"tag":"Basic|Most Asked|Tricky","companies":["TCS"],"steps":["step 1","step 2","step 3"],'
           '"answer":"final answer","trick":"shortcut to solve in 10 seconds"}]}', True)
    j["topic"] = topic
    j["level"] = lv
    kset(k, j)
    return jsonify(j)


@app.post("/api/chat")
def chat():
    j = request.json
    sys = ("You are PrepMate, a friendly interview + aptitude coach inside a mobile app. Answer in very simple English, "
           "short bullets, max 120 words, give a memory trick or example when useful, use code blocks only if needed. "
           + persona() +
           (f"\nCurrent card the learner is viewing: {j.get('context', '')[:1500]}" if j.get("context") else ""))
    return jsonify(text=ai(sys, "", msgs=[{"role": m["role"], "content": m["content"]} for m in j["messages"]]))


@app.post("/api/quiz")
def quiz():
    topic = (request.json or {}).get("topic", "")
    return jsonify(ai("Return JSON only. " + persona(),
                      f'Make 5 MCQs on {topic or "the learner weakest topics"}, most-asked interview/aptitude style. '
                      'Format: {"questions":[{"q":"..","options":["A","B","C","D"],"answer":0,"why":"short solution"}]}',
                      True))


@app.post("/api/term")
def term():
    topic = (request.json or {}).get("topic", "")
    return jsonify(ai("Return JSON only. " + persona(),
                      f'Give 3 interview terms to define aloud{" on " + topic if topic else ""}. '
                      'Format: {"terms":["..","..",".."]}', True))


@app.post("/api/define")
def define():
    j = request.json
    return jsonify(ai("Return JSON only. You are an interview coach and English tutor. " + persona(),
                      f'Term: {j["term"]}\nSpoken answer: {j["answer"]}\nFormat: {{"score":0-10,"correct_points":"..",'
                      '"missing":"..","grammar_fixed":"corrected fluent professional version",'
                      '"grammar_notes":"short mistakes list","model_answer":"ideal 2-3 sentence answer"}', True))


@app.post("/api/coding")
def coding():
    k = "coding_" + today()
    c = kget(k)
    if c:
        return jsonify(c)
    j = ai("Return JSON only. " + persona(),
           'Make 5 most-asked Python interview coding problems (easy to medium: arrays/strings, dict/hash, '
           'pandas/numpy, OOP, one AI-flavoured). Format: {"problems":[{"title":"..","statement":"..",'
           '"example":"..","hint":".."}]}', True)
    kset(k, j)
    return jsonify(j)


@app.post("/api/review")
def review():
    j = request.json
    return jsonify(ai("Return JSON only. You are a senior Python interviewer. " + persona(),
                      f'Problem: {j["problem"]}\nCandidate code:\n{j["code"]}\nFormat: {{"correct":true,"score":0-10,'
                      '"feedback":"..","better_solution":"python code","complexity":".."}', True))


@app.post("/api/tasks")
def mktasks():
    j = ai("Return JSON only. " + persona(),
           'Assign 3 learning tasks for weak/next topics with a free resource (official docs, freeCodeCamp, YouTube, '
           'Hugging Face course). Format: {"tasks":[{"topic":"..","title":"..","url":"https://.."}]}', True)
    ts = kget("tasks", [])
    i = max([t["id"] for t in ts] or [0])
    for t in j["tasks"]:
        i += 1
        ts.append({"id": i, "topic": t["topic"], "title": t["title"], "url": t["url"], "done": 0})
    kset("tasks", ts[-30:])
    return jsonify(ok=1)


@app.post("/api/task_done")
def task_done():
    ts = kget("tasks", [])
    for t in ts:
        if t["id"] == request.json["id"]:
            t["done"] = 1
    kset("tasks", ts)
    return jsonify(ok=1)


@app.post("/api/resume")
def resume():
    f = request.files["file"]
    text = ("\n".join((p.extract_text() or "") for p in PdfReader(f).pages)
            if f.filename.lower().endswith(".pdf") else f.read().decode("utf8", "ignore"))
    return jsonify(text=ai("You are a senior tech recruiter and interview coach. " + persona(),
                           "Analyse this resume for Gen AI / Python / Data Science roles. Give: ATS score /100, "
                           "strengths, gaps, rewritten bullets, projects to add, 10 likely interview questions from "
                           "THIS resume, 7-day plan. Markdown.\n\n" + text[:9000]))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
