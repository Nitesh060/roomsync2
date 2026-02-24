from flask import Flask, request, jsonify, session, render_template, send_file
import sqlite3, os, io
from datetime import datetime
from functools import wraps

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

app = Flask(__name__)
app.secret_key = "roomsync_secret_change_this_in_production"

DB = "roomsync.db"

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id   TEXT UNIQUE NOT NULL,
            name     TEXT NOT NULL,
            password TEXT NOT NULL,
            role     TEXT DEFAULT 'staff'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE NOT NULL,
            capacity INTEGER DEFAULT 0,
            active   INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            room      TEXT NOT NULL,
            title     TEXT NOT NULL,
            date      TEXT NOT NULL,
            start     TEXT NOT NULL,
            end       TEXT NOT NULL,
            booked_by TEXT NOT NULL,
            created   TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # Default admin
    c.execute("SELECT * FROM users WHERE emp_id='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (emp_id,name,password,role) VALUES (?,?,?,?)",
                  ("admin","Administrator","admin123","admin"))

    # Sample staff
    for s in [("EMP001","Rahul Sharma","pass123","staff"),
              ("EMP002","Priya Mehta","pass123","staff"),
              ("EMP003","Arjun Patel","pass123","staff")]:
        c.execute("INSERT OR IGNORE INTO users (emp_id,name,password,role) VALUES (?,?,?,?)", s)

    # Default rooms
    for r in [("Boardroom A",12),("Meeting Room B",6),("Meeting Room C",6),
              ("Training Hall",30),("Huddle Pod 1",4),("Huddle Pod 2",4)]:
        c.execute("INSERT OR IGNORE INTO rooms (name,capacity) VALUES (?,?)", r)

    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "emp_id" not in session:
            return jsonify({"success": False, "error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "Admin only"}), 403
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    emp_id = data.get("emp_id","").strip()
    password = data.get("password","")
    if not emp_id or not password:
        return jsonify({"success": False, "error": "Missing credentials"})
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE emp_id=? AND password=?", (emp_id, password)).fetchone()
    conn.close()
    if user:
        session["emp_id"] = user["emp_id"]
        session["name"]   = user["name"]
        session["role"]   = user["role"]
        return jsonify({"success": True, "role": user["role"], "name": user["name"]})
    return jsonify({"success": False, "error": "Invalid credentials"})

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/me")
def me():
    if "emp_id" in session:
        return jsonify({"logged_in": True, "emp_id": session["emp_id"],
                        "name": session["name"], "role": session["role"]})
    return jsonify({"logged_in": False})

# ─────────────────────────────────────────────
# ROOMS
# ─────────────────────────────────────────────
@app.route("/get_rooms")
@login_required
def get_rooms():
    conn = get_db()
    rooms = conn.execute("SELECT * FROM rooms WHERE active=1 ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rooms])

@app.route("/add_room", methods=["POST"])
@login_required
@admin_required
def add_room():
    data = request.get_json()
    name = data.get("name","").strip()
    capacity = data.get("capacity", 0)
    if not name:
        return jsonify({"success": False, "error": "Room name required"})
    try:
        conn = get_db()
        conn.execute("INSERT INTO rooms (name,capacity) VALUES (?,?)", (name, capacity))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Room already exists"})

@app.route("/delete_room/<int:rid>", methods=["DELETE"])
@login_required
@admin_required
def delete_room(rid):
    conn = get_db()
    conn.execute("UPDATE rooms SET active=0 WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# BOOKINGS
# ─────────────────────────────────────────────
@app.route("/get_bookings")
@login_required
def get_bookings():
    conn = get_db()
    bookings = conn.execute("SELECT * FROM bookings ORDER BY date ASC, start ASC").fetchall()
    conn.close()
    return jsonify([dict(b) for b in bookings])

@app.route("/book", methods=["POST"])
@login_required
def book():
    data  = request.get_json()
    room  = data.get("room","").strip()
    title = data.get("title","").strip()
    date  = data.get("date","").strip()
    start = data.get("start","").strip()
    end   = data.get("end","").strip()

    if not all([room, title, date, start, end]):
        return jsonify({"success": False, "error": "All fields required"})
    if start >= end:
        return jsonify({"success": False, "error": "End time must be after start time"})

    conn = get_db()
    clash = conn.execute("""
        SELECT * FROM bookings
        WHERE room=? AND date=? AND start < ? AND end > ?
    """, (room, date, end, start)).fetchone()

    if clash:
        conn.close()
        return jsonify({
            "success": False, "clash": True,
            "clash_info": {
                "bookedBy": clash["booked_by"],
                "title":    clash["title"],
                "start":    clash["start"],
                "end":      clash["end"],
            }
        })

    conn.execute("INSERT INTO bookings (room,title,date,start,end,booked_by) VALUES (?,?,?,?,?,?)",
                 (room, title, date, start, end, session["emp_id"]))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/cancel/<int:bid>", methods=["DELETE"])
@login_required
def cancel(bid):
    conn = get_db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
    if not booking:
        conn.close()
        return jsonify({"success": False, "error": "Not found"})
    if booking["booked_by"] != session["emp_id"] and session["role"] != "admin":
        conn.close()
        return jsonify({"success": False, "error": "Not authorized"})
    conn.execute("DELETE FROM bookings WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# ADMIN: USERS
# ─────────────────────────────────────────────
@app.route("/get_users")
@login_required
@admin_required
def get_users():
    conn = get_db()
    users = conn.execute("SELECT id, emp_id, name, role FROM users ORDER BY role, name").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route("/add_user", methods=["POST"])
@login_required
@admin_required
def add_user():
    data     = request.get_json()
    emp_id   = data.get("emp_id","").strip()
    name     = data.get("name","").strip()
    password = data.get("password","").strip()
    role     = data.get("role","staff")
    if not all([emp_id, name, password]):
        return jsonify({"success": False, "error": "All fields required"})
    if role not in ("staff","admin"):
        role = "staff"
    try:
        conn = get_db()
        conn.execute("INSERT INTO users (emp_id,name,password,role) VALUES (?,?,?,?)",
                     (emp_id, name, password, role))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Employee ID already exists"})

@app.route("/delete_user/<int:uid>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(uid):
    conn = get_db()
    user = conn.execute("SELECT emp_id FROM users WHERE id=?", (uid,)).fetchone()
    if user and user["emp_id"] == "admin":
        conn.close()
        return jsonify({"success": False, "error": "Cannot delete primary admin"})
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────
@app.route("/export/<month>")
@login_required
@admin_required
def export(month):
    year = datetime.now().year
    conn = get_db()
    bookings = conn.execute("""
        SELECT * FROM bookings
        WHERE strftime('%m', date)=? ORDER BY date, start
    """, (month,)).fetchall()
    conn.close()

    if not EXCEL_AVAILABLE:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID","Room","Title","Date","Start","End","Booked By","Created"])
        for b in bookings:
            writer.writerow([b["id"],b["room"],b["title"],b["date"],b["start"],b["end"],b["booked_by"],b["created"]])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
                         as_attachment=True, download_name=f"bookings_{year}_{month}.csv")

    wb = openpyxl.Workbook()
    ws = wb.active
    month_name = datetime(year, int(month), 1).strftime("%B")
    ws.title = f"{month_name} {year}"

    hdr_fill  = PatternFill("solid", fgColor="1E1E28")
    acc_fill  = PatternFill("solid", fgColor="E8C547")
    alt_fill  = PatternFill("solid", fgColor="16161D")
    row_fill  = PatternFill("solid", fgColor="1A1A24")
    hdr_font  = Font(color="E8E8F0", bold=True, size=11)
    title_fnt = Font(color="0F0F13", bold=True, size=12)
    cell_font = Font(color="E8E8F0", size=10)
    thin      = Side(style='thin', color='2A2A38')
    border    = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells("A1:H1")
    t = ws["A1"]
    t.value = f"RoomSync — Bookings Report | {month_name} {year}"
    t.font = title_fnt; t.fill = acc_fill
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    headers = ["#","Room","Meeting Title","Date","Start","End","Booked By","Booked On"]
    widths  = [5, 20, 28, 14, 10, 10, 16, 22]
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=2, column=i, value=h)
        c.font = hdr_font; c.fill = hdr_fill; c.border = border
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[2].height = 22

    for ri, b in enumerate(bookings, 3):
        fill = alt_fill if ri % 2 == 0 else row_fill
        row = [ri-2, b["room"], b["title"], b["date"], b["start"], b["end"],
               b["booked_by"], b["created"][:16] if b["created"] else ""]
        for ci, val in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font = cell_font; c.fill = fill; c.border = border
            c.alignment = Alignment(horizontal="center" if ci in [1,4,5,6] else "left", vertical="center")
        ws.row_dimensions[ri].height = 18

    sr = len(bookings)+3
    ws.merge_cells(f"A{sr}:H{sr}")
    sc = ws.cell(row=sr, column=1, value=f"Total Bookings in {month_name}: {len(bookings)}")
    sc.font = Font(color="E8C547", bold=True, size=11)
    sc.fill = PatternFill("solid", fgColor="16161D")
    sc.alignment = Alignment(horizontal="right")

    ws.freeze_panes = "A3"
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"RoomSync_Bookings_{month_name}_{year}.xlsx")

if __name__ == "__main__":
    init_db()
    print("\n✅  RoomSync started →  http://127.0.0.1:5000")
    print("   Admin:  emp_id=admin   | password=admin123")
    print("   Staff:  emp_id=EMP001  | password=pass123\n")
    app.run(debug=True, port=5000)
