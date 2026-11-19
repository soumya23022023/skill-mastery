"""Skill Mastery - CRM and Attendance.   Run:  streamlit run app.py
Data is stored in a local SQLite file (smaos.db). Existing leads are kept."""
import os
import re
import sqlite3
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

DB = "smaos.db"
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.jpeg")
STAGES = ["New Lead", "Contacted", "Interested", "Meeting Scheduled", "Demo Completed",
          "Proposal Sent", "Negotiation", "Confirmed", "Lost"]
SOURCES = ["Website", "Referral", "Social Media", "Cold Call", "School Visit", "Event", "Others"]
BOARDS = ["State Board (Telangana)", "CBSE", "ICSE", "IB", "Cambridge", "Other"]
CATEGORIES = ["Private", "Government", "Aided", "Residential", "International"]
DISTRICTS = ["Hyderabad", "Ranga Reddy", "Medchal-Malkajgiri", "Sangareddy", "Warangal", "Karimnagar",
             "Nizamabad", "Khammam", "Nalgonda", "Mahbubnagar", "Other"]
STATUS = ["Present", "Absent", "Late", "Half Day", "Leave"]
CODE = {"Present": "P", "Absent": "A", "Late": "L", "Half Day": "H", "Leave": "V"}

st.set_page_config(page_title="Skill Mastery", page_icon=LOGO if os.path.exists(LOGO) else "🤝", layout="wide")


# ------------------------------------------------------------------ database
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS leads(
            id INTEGER PRIMARY KEY AUTOINCREMENT, school TEXT NOT NULL, principal TEXT, phone TEXT, email TEXT,
            address TEXT, district TEXT, category TEXT, board TEXT, students INTEGER DEFAULT 0,
            teachers INTEGER DEFAULT 0, source TEXT, bde TEXT, stage TEXT DEFAULT 'New Lead',
            deal_value REAL DEFAULT 0, followup_date TEXT, meeting_date TEXT, notes TEXT,
            created_at TEXT, closed_date TEXT, is_sample INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, emp_code TEXT, department TEXT,
            phone TEXT, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id INTEGER NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL,
            check_in TEXT, check_out TEXT, note TEXT, UNIQUE(emp_id, day));
        """)


def q(sql, params=()):
    with conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def ex(sql, params=()):
    with conn() as c:
        c.execute(sql, params)


def inr(v):
    v = float(v or 0)
    if v >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    if v >= 1e5:
        return f"₹{v/1e5:.1f} L"
    return f"₹{v:,.0f}"


def clean(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def ok_time(s):
    return s == "" or re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s) is not None


def head(title, sub):
    st.markdown(f'<div class="ph"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


CSS = """<style>
.stApp{background:#f3f6fb}
.block-container{padding-top:1.4rem;max-width:1400px}
html,body,.stApp,p,label,li,[data-testid=stMetricValue],[data-testid=stMetricLabel]{color:#0f172a}
.ph{border-left:6px solid #1d4ed8;padding:.2rem 0 .2rem 1rem;margin-bottom:1.2rem}
.ph h1{margin:0;font-size:2rem;font-weight:800;color:#0b1f4d}
.ph p{margin:.2rem 0 0;font-size:1.05rem;color:#475569}
[data-testid=stSidebar]{border-right:1px solid #dbe3f0}
[data-testid=stSidebar] .stRadio label{padding:.6rem .9rem;border-radius:10px;width:100%;font-size:1.05rem;font-weight:600;color:#1e293b}
[data-testid=stSidebar] .stRadio label:hover{background:#e8effc}
[data-testid=stSidebar] .stRadio label:has(input:checked){background:#1d4ed8}
[data-testid=stSidebar] .stRadio label:has(input:checked) *{color:#fff !important}
[data-testid=stSidebar] .stRadio [data-baseweb=radio] > div:first-child{display:none}
[data-testid=stMetricValue]{font-size:2rem;font-weight:800}
[data-testid=stMetricLabel] p{font-size:1rem;font-weight:600;color:#334155}
button[data-baseweb=tab]{font-size:1.05rem;font-weight:600}
div.stButton>button,div.stDownloadButton>button,div[data-testid=stFormSubmitButton]>button{border-radius:10px;font-weight:600}
.foot{font-size:.9rem;color:#475569;line-height:1.5}
</style>"""


# -------------------------------------------------------------------- login
def gate():
    try:
        pw = st.secrets.get("APP_PASSWORD")
    except Exception:
        pw = None
    if not pw or st.session_state.get("auth"):
        return
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.image(LOGO)
        p = st.text_input("Password", type="password")
        if st.button("Sign in", type="primary"):
            if p == pw:
                st.session_state.auth = True
                st.rerun()
            st.error("Incorrect password.")
    st.stop()


# ----------------------------------------------------------------- dashboard
def page_dashboard():
    head("Dashboard", "Sales and attendance at a glance")
    L, today = q("SELECT * FROM leads"), date.today().isoformat()
    n_emp = int(q("SELECT COUNT(*) n FROM employees WHERE active=1").n[0])
    T = q("SELECT status FROM attendance WHERE day=?", (today,))
    act, won = L[~L.stage.isin(["Confirmed", "Lost"])], L[L.stage == "Confirmed"]
    due = int((act.followup_date.fillna("9999") <= today).sum())
    row1 = [("Total leads", f"{len(L):,}"), ("Schools confirmed", f"{len(won):,}"),
            ("Conversion rate", f"{len(won)/len(L)*100:.1f}%" if len(L) else "0%"), ("Confirmed revenue", inr(won.deal_value.sum()))]
    row2 = [("Open pipeline value", inr(act.deal_value.sum())), ("Follow-ups due", due),
            ("Present today", int(T.status.isin(["Present", "Late", "Half Day"]).sum())),
            ("Not marked today", max(n_emp - len(T), 0))]
    for row in (row1, row2):
        for col, (t, v) in zip(st.columns(4), row):
            with col.container(border=True):
                st.metric(t, v)
    c1, c2 = st.columns([1.5, 1])
    with c1.container(border=True):
        st.subheader("Pipeline by stage")
        if len(L):
            s = L.stage.value_counts().reindex(STAGES).fillna(0).reset_index()
            s.columns = ["Stage", "Leads"]
            st.altair_chart(alt.Chart(s).mark_bar(color="#1d4ed8").encode(
                y=alt.Y("Stage:N", sort=STAGES, title=None), x=alt.X("Leads:Q", title=None)).properties(height=280), width="stretch")
        else:
            st.info("No leads yet. Add your first lead on the Leads page.")
    with c2.container(border=True):
        st.subheader("Lead sources")
        if len(L):
            s = L.source.fillna("Others").value_counts().reset_index()
            s.columns = ["Source", "Leads"]
            st.altair_chart(alt.Chart(s).mark_arc(innerRadius=55).encode(
                theta="Leads:Q", color="Source:N", tooltip=["Source", "Leads"]).properties(height=280), width="stretch")
        else:
            st.info("No leads yet.")
    with st.container(border=True):
        st.subheader("Recent leads")
        st.dataframe(L.head(8)[["school", "principal", "phone", "source", "bde", "stage"]], width="stretch", hide_index=True)


# --------------------------------------------------------------------- leads
def lead_form(row, key):
    r = row or {}

    def g(k, d=""):
        v = clean(r.get(k))
        return v if v != "" else d

    ix = lambda opts, k: opts.index(g(k)) if g(k) in opts else 0
    with st.form(key, clear_on_submit=row is None):
        a, b, c = st.columns(3)
        school = a.text_input("School name *", g("school"))
        principal = b.text_input("Principal name", g("principal"))
        phone = c.text_input("Phone (10 digits)", g("phone"))
        email = a.text_input("Email", g("email"))
        district = b.selectbox("District", DISTRICTS, ix(DISTRICTS, "district"))
        category = c.selectbox("Category", CATEGORIES, ix(CATEGORIES, "category"))
        board = a.selectbox("Board", BOARDS, ix(BOARDS, "board"))
        students = b.number_input("Student strength", 0, 100000, int(float(g("students", 0))))
        teachers = c.number_input("Teacher strength", 0, 10000, int(float(g("teachers", 0))))
        source = a.selectbox("Lead source", SOURCES, ix(SOURCES, "source"))
        bde = b.text_input("Assigned BDE", g("bde"))
        stage = c.selectbox("Stage", STAGES, ix(STAGES, "stage"))
        deal = a.number_input("Deal value (₹)", 0.0, 1e9, float(g("deal_value", 0)), step=10000.0)
        fu = b.date_input("Follow-up date", date.fromisoformat(g("followup_date")) if g("followup_date") else date.today() + timedelta(days=3))
        notes = c.text_area("Notes", g("notes"), height=80)
        ok = st.form_submit_button("Save lead", type="primary")
    if not ok:
        return
    errs = []
    if not school.strip():
        errs.append("School name is required.")
    if phone and not (phone.isdigit() and len(phone) == 10):
        errs.append("Phone must be 10 digits.")
    if email and "@" not in email:
        errs.append("Email looks invalid.")
    dup = q("SELECT id,school FROM leads WHERE (lower(school)=lower(?) AND district=?) OR (phone!='' AND phone=?)",
            (school.strip(), district, phone))
    dup = dup[dup.id != r.get("id", -1)]
    if len(dup):
        errs.append("Possible duplicate of: " + ", ".join(dup.school))
    if errs:
        for e in errs:
            st.error(e)
        return
    v = (school.strip(), principal, phone, email, district, category, board, students, teachers, source, bde, stage,
         deal, fu.isoformat(), notes)
    today = date.today().isoformat()
    if row is None:
        ex("""INSERT INTO leads(school,principal,phone,email,district,category,board,students,teachers,source,bde,stage,
            deal_value,followup_date,notes,created_at,closed_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           v + (today, today if stage == "Confirmed" else None))
    else:
        ex("""UPDATE leads SET school=?,principal=?,phone=?,email=?,district=?,category=?,board=?,students=?,teachers=?,
            source=?,bde=?,stage=?,deal_value=?,followup_date=?,notes=?,
            closed_date=CASE WHEN ?='Confirmed' AND closed_date IS NULL THEN ? ELSE closed_date END WHERE id=?""",
           v + (stage, today, int(r["id"])))
    st.toast("Lead saved")
    st.rerun()


def page_leads():
    head("Leads", "Schools you are talking to")
    L = q("SELECT * FROM leads ORDER BY id DESC")
    with st.expander("➕ Add a new lead"):
        lead_form(None, "add")
    f1, f2, f3 = st.columns([2, 1, 1])
    s = f1.text_input("Search", placeholder="School, principal or phone")
    fs = f2.multiselect("Stage", STAGES)
    fb = f3.multiselect("BDE", sorted(L.bde.dropna().unique()))
    V = L
    if s:
        V = V[V.school.str.contains(s, case=False, na=False) | V.principal.str.contains(s, case=False, na=False)
              | V.phone.str.contains(s, na=False)]
    if fs:
        V = V[V.stage.isin(fs)]
    if fb:
        V = V[V.bde.isin(fb)]
    st.caption(f"Showing {len(V)} of {len(L)} leads")
    st.dataframe(V[["id", "school", "principal", "phone", "district", "students", "source", "bde", "stage", "deal_value",
                    "followup_date"]], width="stretch", hide_index=True)
    st.download_button("⬇ Export to CSV", V.to_csv(index=False).encode(), "leads.csv", "text/csv")
    if len(L):
        with st.expander("✏️ Edit or delete a lead"):
            pick = st.selectbox("Choose lead", L.id, format_func=lambda i: f"#{i}  {L[L.id == i].school.iloc[0]}")
            lead_form(L[L.id == pick].iloc[0].to_dict(), "edit")
            sure = st.checkbox("I want to delete this lead permanently")
            if st.button("🗑 Delete lead", disabled=not sure):
                ex("DELETE FROM leads WHERE id=?", (int(pick),))
                st.rerun()


def page_deals():
    head("Deals", "Move schools through your sales pipeline")
    L = q("SELECT * FROM leads")
    if L.empty:
        st.info("No leads yet.")
        return
    g = L.groupby("stage").agg(Leads=("id", "count"), Value=("deal_value", "sum")).reindex(STAGES).fillna(0).reset_index()
    g["Value"] = g.Value.map(inr)
    st.dataframe(g.rename(columns={"stage": "Stage"}), width="stretch", hide_index=True)
    with st.container(border=True):
        st.subheader("Move a deal")
        pick = st.selectbox("Deal", L.id, format_func=lambda i: f"#{i}  {L[L.id == i].school.iloc[0]}  ({L[L.id == i].stage.iloc[0]})")
        new = st.selectbox("New stage", STAGES, index=STAGES.index(L[L.id == pick].stage.iloc[0]))
        if st.button("Update stage", type="primary"):
            ex("UPDATE leads SET stage=?, closed_date=CASE WHEN ?='Confirmed' THEN ? ELSE closed_date END WHERE id=?",
               (new, new, date.today().isoformat(), int(pick)))
            st.rerun()


# ---------------------------------------------------------------- attendance
def page_attendance():
    head("Attendance", "Mark daily attendance, view monthly registers and manage employees")
    t1, t2, t3 = st.tabs(["✅ Mark attendance", "📅 Monthly report", "👤 Employees"])
    E = q("SELECT * FROM employees WHERE active=1 ORDER BY name")
    with t1:
        if E.empty:
            st.info("No employees yet. Open the Employees tab and add your team first.")
        else:
            d = st.date_input("Date", date.today(), max_value=date.today()).isoformat()
            cur = q("SELECT emp_id,status,check_in,check_out,note FROM attendance WHERE day=?", (d,))
            m = E[["id", "name", "department"]].merge(cur, how="left", left_on="id", right_on="emp_id")
            saved = int(m.status.notna().sum())
            df = pd.DataFrame({"id": m.id, "Employee": m.name, "Department": m.department.fillna(""),
                               "Status": m.status.fillna("Present"), "Check-in": m.check_in.fillna(""),
                               "Check-out": m.check_out.fillna(""), "Note": m.note.fillna("")})
            st.caption(f"{saved} of {len(df)} employees already saved for this date. Rows not saved yet start as Present.")
            ed = st.data_editor(df, key=f"ed_{d}", hide_index=True, width="stretch", disabled=["id", "Employee", "Department"],
                                column_config={"id": None,
                                               "Status": st.column_config.SelectboxColumn(options=STATUS, required=True),
                                               "Check-in": st.column_config.TextColumn(help="24-hour time, like 09:30"),
                                               "Check-out": st.column_config.TextColumn(help="24-hour time, like 18:00")})
            cnt = ed.Status.value_counts()
            st.markdown("**Totals:** " + "  |  ".join(f"{s}: {int(cnt.get(s, 0))}" for s in STATUS))
            if st.button("Save attendance", type="primary"):
                bad = [r["Employee"] for _, r in ed.iterrows() if not (ok_time(clean(r["Check-in"])) and ok_time(clean(r["Check-out"])))]
                if bad:
                    st.error("Enter times as HH:MM, for example 09:30. Check: " + ", ".join(bad))
                else:
                    with conn() as c:
                        for _, r in ed.iterrows():
                            c.execute("""INSERT INTO attendance(emp_id,day,status,check_in,check_out,note) VALUES(?,?,?,?,?,?)
                                ON CONFLICT(emp_id,day) DO UPDATE SET status=excluded.status,check_in=excluded.check_in,
                                check_out=excluded.check_out,note=excluded.note""",
                                      (int(r["id"]), d, r["Status"], clean(r["Check-in"]), clean(r["Check-out"]), clean(r["Note"])))
                    st.success(f"Attendance saved for {d}.")
    with t2:
        t = date.today().replace(day=1)
        months = []
        for i in range(12):
            y, mo = t.year, t.month - i
            if mo <= 0:
                mo, y = mo + 12, y - 1
            months.append(f"{y}-{mo:02d}")
        mon = st.selectbox("Month", months)
        R = q("""SELECT e.name, COALESCE(e.department,'') department, a.day, a.status FROM attendance a
                 JOIN employees e ON e.id=a.emp_id WHERE substr(a.day,1,7)=? ORDER BY e.name""", (mon,))
        if R.empty:
            st.info("No attendance saved for this month.")
        else:
            S = R.pivot_table(index=["name", "department"], columns="status", values="day", aggfunc="count", fill_value=0)
            S = S.reindex(columns=STATUS, fill_value=0)
            S.columns.name = None
            S["Days marked"] = S.sum(axis=1)
            S["Attendance %"] = ((S.Present + S.Late + 0.5 * S["Half Day"]) / S["Days marked"] * 100).round(1)
            S = S.reset_index().rename(columns={"name": "Employee", "department": "Department"})
            st.subheader("Summary")
            st.dataframe(S, width="stretch", hide_index=True)
            R["d"], R["c"] = R.day.str[8:].astype(int), R.status.map(CODE)
            G = R.pivot_table(index="name", columns="d", values="c", aggfunc="first").fillna("")
            G.index.name, G.columns.name = "Employee", None
            st.subheader("Daily register")
            st.caption("P = Present, A = Absent, L = Late, H = Half day, V = Leave")
            st.dataframe(G, width="stretch")
            st.download_button("⬇ Download summary (CSV)", S.to_csv(index=False).encode(), f"attendance_{mon}.csv", "text/csv")
    with t3:
        with st.form("emp", clear_on_submit=True):
            a, b, c, dd = st.columns(4)
            name, code = a.text_input("Full name *"), b.text_input("Employee ID")
            dept, ph = c.text_input("Department"), dd.text_input("Phone")
            if st.form_submit_button("Add employee", type="primary"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    ex("INSERT INTO employees(name,emp_code,department,phone) VALUES(?,?,?,?)", (name.strip(), code, dept, ph))
                    st.toast("Employee added")
                    st.rerun()
        A = q("SELECT * FROM employees ORDER BY name")
        if len(A):
            show = A.assign(Active=A.active.map({1: "Yes", 0: "No"}))[["name", "emp_code", "department", "phone", "Active"]]
            st.dataframe(show.rename(columns={"name": "Employee", "emp_code": "Employee ID", "department": "Department", "phone": "Phone"}),
                         width="stretch", hide_index=True)
            pick = st.selectbox("Employee", A.id, format_func=lambda i: A[A.id == i].name.iloc[0])
            on = int(A[A.id == pick].active.iloc[0])
            if st.button("Deactivate (left the company)" if on else "Reactivate"):
                ex("UPDATE employees SET active=? WHERE id=?", (0 if on else 1, int(pick)))
                st.rerun()
            st.caption("Deactivated employees disappear from daily marking but stay in past reports.")


def page_settings():
    head("Settings", "Backup and security")
    try:
        with open(DB, "rb") as fh:
            st.download_button("⬇ Download database backup", fh.read(), "smaos_backup.db")
    except FileNotFoundError:
        pass
    st.info("To require a password, create the file .streamlit/secrets.toml with the line:  APP_PASSWORD = \"choose-a-password\"")
    st.warning("This app stores data in a local file. It is fine for one office computer, but not for many people at once. "
               "For a company-wide system, move to a hosted database as discussed earlier.")


# ---------------------------------------------------------------------- main
init_db()
st.markdown(CSS, unsafe_allow_html=True)
gate()
PAGES = {"Dashboard": ("🏠", page_dashboard), "Leads": ("👥", page_leads), "Deals": ("💼", page_deals),
         "Attendance": ("🗓️", page_attendance), "Settings": ("⚙️", page_settings)}
with st.sidebar:
    st.image(LOGO)
    page = st.radio("Menu", list(PAGES), label_visibility="collapsed", format_func=lambda p: f"{PAGES[p][0]}  {p}")
    st.divider()
    st.markdown('<div class="foot"><b>Skill Mastery Pvt Ltd</b><br>info@skillmastery.co.in</div>', unsafe_allow_html=True)
PAGES[page][1]()
