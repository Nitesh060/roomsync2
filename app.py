from flask import Flask, request, jsonify, session, render_template, send_file
import sqlite3
import io
from functools import wraps
import openpyxl

app = Flask(__name__)
app.secret_key = "roomsync_super_secure_key_change_this"

# ---- SESSION FIX FOR RENDER HTTPS ----
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True

DB = "roomsync.db"

# =========================
# DATABASE
# =========================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'staff'
        )
    """)

    # ROOMS
    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            capacity INTEGER DEFAULT 0
        )
    """)

    # BOOKINGS
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            booked_by TEXT NOT NULL
        )
    """)

    # DEFAULT ADMIN
    c.execute("SELECT * FROM users WHERE emp_id='admin'")
    if not c.fetchone():
        c.execute("""
            INSERT INTO users (emp_id,name,password,role)
            VALUES (?,?,?,?)
        """, ("admin", "Administrator", "admin123", "admin"))

    # DEFAULT STAFF
    staff_list = ["63326", "63329", "63324"]
    for emp in staff_list:
        c.execute("""
            INSERT OR IGNORE INTO users (emp_id,name,password,role)
            VALUES (?,?,?,?)
        """, (emp, f"Staff {emp}", f"afpl@{emp}", "staff"))

    # DEFAULT ROOMS
    rooms = [("Boardroom A",12),
             ("Meeting Room B",6),
             ("Meeting Room C",6)]
    for r in rooms:
        c.execute("INSERT OR IGNORE INTO rooms (name,capacity) VALUES (?,?)", r)

    conn.commit()
    conn.close()

# IMPORTANT — RUN DB INIT HERE (NOT INSIDE __main__)
init_db()

# =========================
# DECORATORS
# =========================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "emp_id" not in session:
            return jsonify({"success": False, "error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "Admin only"}), 403
        return f(*args, **kwargs)
    return wrapper

# =========================
# PAGE
# =========================
@app.route("/")
def index():
    return render_template("conference_booking.html")

# =========================
# AUTH
# =========================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    emp_id = data.get("emp_id")
    password = data.get("password")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE emp_id=? AND password=?",
        (emp_id, password)
    ).fetchone()
    conn.close()

    if user:
        session["emp_id"] = user["emp_id"]
        session["role"] = user["role"]
        return jsonify({"success": True, "role": user["role"]})

    return jsonify({"success": False})

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})

# =========================
# BOOKINGS
# =========================
@app.route("/get_bookings")
@login_required
def get_bookings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM bookings ORDER BY date,start").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/book", methods=["POST"])
@login_required
def book():
    data = request.get_json()
    room = data.get("room")
    title = data.get("title")
    date = data.get("date")
    start = data.get("start")
    end = data.get("end")

    conn = get_db()

    clash = conn.execute("""
        SELECT * FROM bookings
        WHERE room=? AND date=? AND start < ? AND end > ?
    """, (room, date, end, start)).fetchone()

    if clash:
        conn.close()
        return jsonify({"success": False, "clash": True})

    conn.execute("""
        INSERT INTO bookings (room,title,date,start,end,booked_by)
        VALUES (?,?,?,?,?,?)
    """, (room, title, date, start, end, session["emp_id"]))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/cancel/<int:bid>", methods=["DELETE"])
@login_required
def cancel(bid):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=?",
        (bid,)
    ).fetchone()

    if not booking:
        conn.close()
        return jsonify({"success": False})

    if booking["booked_by"] != session["emp_id"] and session["role"] != "admin":
        conn.close()
        return jsonify({"success": False})

    conn.execute("DELETE FROM bookings WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# =========================
# ROOMS (ADMIN)
# =========================
@app.route("/add_room", methods=["POST"])
@login_required
@admin_required
def add_room():
    data = request.get_json()
    name = data.get("name")
    capacity = data.get("capacity")

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO rooms (name,capacity) VALUES (?,?)",
            (name, capacity)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Room already exists"})

@app.route("/get_rooms")
@login_required
def get_rooms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# =========================
# EXPORT (ADMIN)
# =========================
@app.route("/export/<month>")
@login_required
@admin_required
def export(month):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM bookings
        WHERE strftime('%m', date)=?
        ORDER BY date,start
    """, (month,)).fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Room","Title","Date","Start","End","Booked By"])

    for r in rows:
        ws.append([
            r["room"],
            r["title"],
            r["date"],
            r["start"],
            r["end"],
            r["booked_by"]
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="monthly_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# LOCAL RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
