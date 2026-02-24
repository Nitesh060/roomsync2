# RoomSync — Conference Room Booking System

A full-stack internal booking platform for your firm. Built with **Flask** (Python) backend + **SQLite** database + plain HTML/CSS/JS frontend.

---

## 📁 Project Structure

```
roomsync/
├── app.py              ← Flask backend (all API routes)
├── requirements.txt    ← Python dependencies
├── roomsync.db         ← SQLite database (auto-created on first run)
└── templates/
    └── index.html      ← Full frontend UI
```

---

## 🚀 Setup & Run

### Step 1 — Install Python (3.8+)
Download from https://python.org if not installed.

### Step 2 — Install dependencies
Open a terminal in the `roomsync/` folder and run:
```bash
pip install -r requirements.txt
```

### Step 3 — Start the server
```bash
python app.py
```

### Step 4 — Open in browser
Visit: **http://127.0.0.1:5000**

---

## 🔐 Default Login Credentials

| Role  | Employee ID | Password   |
|-------|-------------|------------|
| Admin | `admin`     | `admin123` |
| Staff | `EMP001`    | `pass123`  |
| Staff | `EMP002`    | `pass123`  |
| Staff | `EMP003`    | `pass123`  |

> ⚠️ Change passwords after first login (via Admin → Manage Staff → Delete & Re-add)

---

## ✅ Features

### All Staff
- Login with Employee ID + Password
- Book any conference room with date & time
- **Clash detection** — popup alert if room is already booked
- Cancel your own bookings
- View all bookings with filters (room / date)
- Live room status — see which rooms are in use right now

### Admin Only
- **Manage Staff** — add / remove users, assign admin or staff role
- **Manage Rooms** — add new rooms, set capacity, remove rooms
- **Export** — download monthly Excel report of all bookings (color-coded, formatted)

---

## ⚙️ Configuration

### Change the secret key (important for production!)
In `app.py`, line 10:
```python
app.secret_key = "roomsync_secret_change_this_in_production"
```
Replace with a long random string.

### Run on a different port
```python
app.run(debug=True, port=8080)  # change 5000 to any port
```

### Run on local network (all office PCs can access)
```python
app.run(host="0.0.0.0", port=5000)
```
Then staff can open `http://YOUR_PC_IP:5000` from any computer on the same network.

---

## 🏢 Default Rooms

- Boardroom A (12 seats)
- Meeting Room B (6 seats)
- Meeting Room C (6 seats)
- Training Hall (30 seats)
- Huddle Pod 1 (4 seats)
- Huddle Pod 2 (4 seats)

Add/remove rooms anytime from the Admin panel without restarting.

---

## 🗄️ Database

The SQLite file `roomsync.db` is auto-created in the project folder.
- No installation required — it's a single file
- Back it up by simply copying the `.db` file

---

## 🔒 Security Notes

- This system is designed for **internal network use only**
- Do not expose it directly to the public internet without adding HTTPS and stronger auth
- For office-only use, run on a PC/server inside your office network
