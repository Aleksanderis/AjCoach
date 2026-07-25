from flask import Flask, session, redirect, request, send_from_directory, render_template, abort, Response
from markupsafe import Markup
import os, re, importlib.util, calendar
import markdown as md_lib
from pathlib import Path
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
PASSWORD = os.environ["COACH_PASSWORD"]
PERSONAS_DIR = Path(os.environ.get("PERSONAS_DIR", "/personas"))
DEFAULT_PERSONA = os.environ.get("DEFAULT_PERSONA", "")
SRC_DIR = Path(os.environ.get("SRC_DIR", str(PERSONAS_DIR.parent / "src")))


# ── helpers ────────────────────────────────────────────────────────────────────

def _personas():
    return sorted(d.name for d in PERSONAS_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))

def _require_auth():
    if not session.get("auth"):
        return redirect(f"/login?next={request.path}")

def _persona_dir(name):
    d = PERSONAS_DIR / name
    if not d.is_dir():
        abort(404)
    return d

def _render_md(text):
    return Markup(md_lib.markdown(text, extensions=["tables", "fenced_code", "nl2br"]))

def _fmt_duration(seconds):
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 60} min"

def _sidebar_data(name):
    persona_dir = PERSONAS_DIR / name
    sections = []

    if (persona_dir / "profile.md").exists():
        sections.append({"type": "link", "label": "Profile", "url": f"/{name}/doc/profile"})

    program_dir = persona_dir / "program"
    if program_dir.exists():
        items = []
        if (program_dir / "current_plan.md").exists():
            items.append({"label": "Current Plan", "url": f"/{name}/doc/program/current_plan"})
        if (program_dir / "nutrition_plan.md").exists():
            items.append({"label": "Nutrition Plan", "url": f"/{name}/doc/program/nutrition_plan"})
        for f in sorted(program_dir.glob("week_*.md"), reverse=True)[:6]:
            items.append({"label": f.stem.replace("week_", "Week "), "url": f"/{name}/doc/program/{f.stem}"})
        if items:
            sections.append({"type": "group", "label": "Program", "links": items})

    reports_dir = persona_dir / "reports"
    if reports_dir.exists():
        coaching = sorted(reports_dir.glob("*_coaching.md"), reverse=True)
        if coaching:
            items = [{"label": f.stem, "url": f"/{name}/doc/reports/{f.stem}"} for f in coaching[:10]]
            sections.append({"type": "group", "label": "Reports", "links": items})

    return sections

app.jinja_env.globals["fmt_duration"] = _fmt_duration
app.jinja_env.globals["render_md"] = _render_md


# ── auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["auth"] = True
            return redirect(request.args.get("next") or "/")
        return render_template("login.html", error="Invalid password")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ── root ───────────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    redir = _require_auth()
    if redir:
        return redir
    default = DEFAULT_PERSONA or _personas()[0]
    return redirect(f"/{default}/")

@app.route("/<name>/")
def persona_home(name):
    redir = _require_auth()
    if redir:
        return redir
    _persona_dir(name)
    return redirect(f"/{name}/doc/profile")


# ── doc viewer ─────────────────────────────────────────────────────────────────

@app.route("/<name>/doc/<path:doc_path>")
def doc(name, doc_path):
    redir = _require_auth()
    if redir:
        return redir
    persona_dir = _persona_dir(name)

    md_file = persona_dir / (doc_path + ".md")
    if not md_file.exists() or not md_file.is_file():
        abort(404)

    content = _render_md(md_file.read_text(encoding="utf-8"))
    title = md_file.stem.replace("_", " ").replace("-", " ").title()
    active_path = f"/{name}/doc/{doc_path}"

    return render_template("doc.html",
                           persona=name, personas=_personas(),
                           sidebar_sections=_sidebar_data(name),
                           active_path=active_path,
                           title=title, content=content)


# ── workout ────────────────────────────────────────────────────────────────────

@app.route("/<name>/workout/")
def workout_today(name):
    redir = _require_auth()
    if redir:
        return redir
    _persona_dir(name)
    return redirect(f"/{name}/workout/{date.today().isoformat()}/")

@app.route("/<name>/workout/<date_str>/")
def workout(name, date_str):
    redir = _require_auth()
    if redir:
        return redir
    persona_dir = _persona_dir(name)

    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    prev_day = (target - timedelta(days=1)).isoformat()
    next_day = (target + timedelta(days=1)).isoformat()

    week_file = _find_week_file(persona_dir, target)
    if not week_file:
        return render_template("workout.html",
                               persona=name, personas=_personas(),
                               sidebar_sections=_sidebar_data(name), active_path="workout",
                               target=target, prev_day=prev_day, next_day=next_day,
                               session_info=None, routine=None,
                               load_notes="", cooldown="", error="No week plan found for this date.")

    content = week_file.read_text(encoding="utf-8")
    session_info = _parse_today_session(content, target)

    routine = None
    if session_info and session_info["focus"] not in ("—", ""):
        routines = _enrich_routines(_load_routines(persona_dir))
        routine = _match_routine(session_info["focus"] + " " + session_info["session_type"], routines)

    return render_template("workout.html",
                           persona=name, personas=_personas(),
                           sidebar_sections=_sidebar_data(name), active_path="workout",
                           target=target, prev_day=prev_day, next_day=next_day,
                           session_info=session_info, routine=routine,
                           load_notes=_extract_section(content, "Load Notes"),
                           cooldown=_extract_section(content, "Cool-Down"),
                           error=None)


# ── week plan parsing ──────────────────────────────────────────────────────────

def _find_week_file(persona_dir, target_date):
    for f in (persona_dir / "program").glob("week_*.md"):
        try:
            monday = date.fromisoformat(f.stem.replace("week_", ""))
            if monday <= target_date <= monday + timedelta(days=6):
                return f
        except ValueError:
            pass
    return None

def _parse_today_session(content, target):
    today_name = list(calendar.day_name)[target.weekday()]
    in_table = False
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("| Day |"):
            in_table = True
            continue
        if in_table and s.startswith("|---"):
            continue
        if in_table and s.startswith("|"):
            cols = [c.strip() for c in s.strip("|").split("|")]
            if len(cols) >= 5 and today_name.lower() in cols[0].lower():
                return {"day": cols[0], "session_type": cols[1],
                        "focus": cols[2], "cardio": cols[3], "notes": cols[4]}
        elif in_table:
            break
    return None

def _load_routines(persona_dir):
    setup_file = persona_dir / "setup_hevy.py"
    if not setup_file.exists():
        return []
    spec = importlib.util.spec_from_file_location("setup_hevy", setup_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "ROUTINES", [])

def _match_routine(query, routines):
    query_words = set(re.findall(r"[a-z]+", query.lower()))
    best, best_score = None, 0
    for r in routines:
        short = re.sub(r"\s*\([^)]+\)", "", r["name"]).strip()
        r_words = set(re.findall(r"[a-z]+", short.lower()))
        score = len(query_words & r_words)
        for w in r_words:
            if any(w in qw or qw in w for qw in query_words):
                score += 0.5
        if score > best_score:
            best_score, best = score, r
    return best if best_score > 0 else None

def _load_exercise_info():
    """Parse custom_exercise_templates.md → {template_id: {muscle, demo_url}}."""
    info_file = SRC_DIR / "custom_exercise_templates.md"
    if not info_file.exists():
        return {}
    result = {}
    url_re = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    for line in info_file.read_text(encoding="utf-8").split("\n"):
        if not line.startswith("|") or "|---|" in line or "| Name |" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 5:
            continue
        tid = cols[1].strip("`")
        muscle = cols[3]
        m = url_re.search(cols[4])
        result[tid] = {"muscle": muscle, "demo_url": m.group(2) if m else None}
    return result

_URL_RE = re.compile(r'https?://\S+')

def _enrich_routines(routines):
    """Add muscle, demo_url, clean_notes to every exercise in every routine."""
    ex_info = _load_exercise_info()

    def enrich(ex):
        info = ex_info.get(ex.get("template_id", ""), {})
        ex["muscle"] = info.get("muscle", "")
        notes = ex.get("notes", "") or ""
        # Pull demo URL from exercise_info first, then from notes text
        demo = info.get("demo_url") or (_URL_RE.search(notes).group(0) if _URL_RE.search(notes) else None)
        ex["demo_url"] = demo
        # Strip all URLs and "Demo: " labels from displayed notes
        clean = _URL_RE.sub("", notes)
        clean = re.sub(r'Demo:\s*', '', clean).strip().strip("\n")
        ex["clean_notes"] = clean

    for routine in routines:
        for superset in routine.get("warmup", []):
            for ex in superset:
                enrich(ex)
        for ex in routine.get("exercises", []):
            enrich(ex)
    return routines

def _extract_section(content, heading):
    m = re.search(rf"## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3003))
    app.run(host="0.0.0.0", port=port, debug=False)
