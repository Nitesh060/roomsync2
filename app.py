from flask import Flask, request, jsonify, session, render_template
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "roomsync_secure_key"

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True

DB = "roomsync.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE,
            name TEXT,
            password TEXT,
            role TEXT,
            department TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            capacity INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            title TEXT,
            date TEXT,
            start TEXT,
            end TEXT,
            booked_by TEXT
        )
    """)

    c.execute("""
        INSERT OR IGNORE INTO users 
        (id,emp_id,name,password,role,department)
        VALUES (1,'admin','Administrator','admin123','admin','Management')
    """)

    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "emp_id" not in session:
            return jsonify({"success": False}), 401
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"success": False}), 403
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return render_template("conference_booking.html")

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

@app.route("/add_user", methods=["POST"])
@login_required
@admin_required
def add_user():
    data = request.get_json()

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO users (emp_id,name,password,role,department)
            VALUES (?,?,?,?,?)
        """, (
            data.get("emp_id"),
            data.get("name"),
            data.get("password"),
            data.get("role"),
            data.get("department")
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

@app.route("/get_users")
@login_required
@admin_required
def get_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT emp_id,name,role,department FROM users"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/add_room", methods=["POST"])
@login_required
@admin_required
def add_room():
    data = request.get_json()

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO rooms (name,capacity) VALUES (?,?)",
            (data.get("name"), data.get("capacity"))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

@app.route("/get_rooms")
@login_required
def get_rooms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

def time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h*60 + m

@app.route("/book", methods=["POST"])
@login_required
def book():
    data = request.get_json()

    room = data.get("room")
    date = data.get("date")
    start = data.get("start")
    end = data.get("end")

    start_m = time_to_minutes(start)
    end_m = time_to_minutes(end)

    conn = get_db()

    bookings = conn.execute("""
        SELECT * FROM bookings
        WHERE room=? AND date=?
    """, (room, date)).fetchall()

    for b in bookings:
        existing_start = time_to_minutes(b["start"])
        existing_end = time_to_minutes(b["end"])

        if start_m < existing_end and end_m > existing_start:
            conn.close()
            return jsonify({
                "success": False,
                "clash": True
            })

    conn.execute("""
        INSERT INTO bookings (room,title,date,start,end,booked_by)
        VALUES (?,?,?,?,?,?)
    """, (
        room,
        data.get("title"),
        date,
        start,
        end,
        session["emp_id"]
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/get_bookings")
@login_required
def get_bookings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM bookings").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/cancel/<int:bid>", methods=["DELETE"])
@login_required
def cancel(bid):
    conn = get_db()
    conn.execute("DELETE FROM bookings WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
