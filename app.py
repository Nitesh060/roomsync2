from flask import Flask, request, jsonify, session, render_template, send_file
import sqlite3
import io
from functools import wraps
import openpyxl

app = Flask(__name__)
app.secret_key = "roomsync_secure_key_change_this"

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
            role TEXT
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

    c.execute("INSERT OR IGNORE INTO users VALUES (1,'admin','Administrator','admin123','admin')")

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

# ---------------- AUTH ----------------

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

# ---------------- STAFF MANAGEMENT ----------------

@app.route("/add_user", methods=["POST"])
@login_required
@admin_required
def add_user():
    data = request.get_json()
    emp_id = data.get("emp_id")
    name = data.get("name")
    password = data.get("password")
    role = data.get("role")

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO users (emp_id,name,password,role) VALUES (?,?,?,?)",
            (emp_id, name, password, role)
        )
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
    rows = conn.execute("SELECT emp_id,name,role FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/delete_user/<emp_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(emp_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE emp_id=?", (emp_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ---------------- ROOM MANAGEMENT ----------------

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
    except:
        return jsonify({"success": False})

@app.route("/get_rooms")
@login_required
def get_rooms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ---------------- BOOKINGS ----------------

@app.route("/get_bookings")
@login_required
def get_bookings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM bookings").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/book", methods=["POST"])
@login_required
def book():
    data = request.get_json()
    conn = get_db()

    conn.execute("""
        INSERT INTO bookings (room,title,date,start,end,booked_by)
        VALUES (?,?,?,?,?,?)
    """, (
        data.get("room"),
        data.get("title"),
        data.get("date"),
        data.get("start"),
        data.get("end"),
        session["emp_id"]
    ))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

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
