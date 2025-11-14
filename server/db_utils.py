# aos/server/db_utils.py
import sqlite3
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ---------------- Connection ----------------
def get_connection(node_id):
    db_name = os.path.join(DATA_DIR, f"node{node_id}_db.sqlite")
    conn = sqlite3.connect(db_name, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ---------------- User Queries ----------------
def create_user(conn, username, password_hash):
    try:
        conn.execute("INSERT INTO User (UserID, Password) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def validate_user(conn, username, password_hash):
    cursor = conn.execute("SELECT * FROM User WHERE UserID=? AND Password=?", (username, password_hash))
    return cursor.fetchone() is not None

# ---------------- Booking Queries ----------------
def add_booking(conn, user_id, source, destination, num_passengers):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Booking (UserID, Source, Destination, NumPassengers)
        VALUES (?, ?, ?, ?)
    """, (user_id, source, destination, num_passengers))
    booking_id = cursor.lastrowid

    conn.execute("""
        INSERT INTO LogFile (Timestamp, Action, BookingID)
        VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), "Booked", booking_id))

    conn.commit()
    return booking_id

def get_bookings_by_user(conn, user_id):
    cursor = conn.execute("SELECT * FROM Booking WHERE UserID=?", (user_id,))
    return cursor.fetchall()
