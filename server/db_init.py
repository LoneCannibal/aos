import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def init_node_db(node_name):
    db_name = os.path.join(DATA_DIR, f"{node_name}_db.sqlite")
    if os.path.exists(db_name):
        print(f"{db_name} already exists.")
        return

    conn = sqlite3.connect(db_name)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
        CREATE TABLE User (
            UserID TEXT PRIMARY KEY,
            Password TEXT NOT NULL
        );
    """)

    conn.execute("""
        CREATE TABLE Booking (
            BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
            UserID TEXT,
            Source TEXT,
            Destination TEXT,
            NumPassengers INTEGER,
            FOREIGN KEY (UserID) REFERENCES User(UserID)
        );
    """)

    conn.execute("""
        CREATE TABLE LogFile (
            LogID INTEGER PRIMARY KEY AUTOINCREMENT,
            Timestamp TEXT,
            Action TEXT,
            BookingID INTEGER,
            FOREIGN KEY (BookingID) REFERENCES Booking(BookingID)
        );
    """)

    conn.commit()
    conn.close()
    print(f"{db_name} created successfully.")


if __name__ == "__main__":
    for i in range(0, 10):
        init_node_db(f"node{i}")
