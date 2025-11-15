import sqlite3
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

TRAIN_DATA = [
    ("Pilani", "Delhi", "09:00", "13:00", 80),
    ("Delhi", "Jaipur", "11:00", "14:30", 120),
    ("Pilani", "Jaipur", "07:00", "10:00", 100),
    ("Jaipur", "Delhi", "15:00", "19:00", 130),
    ("Pilani", "Chandigarh", "06:00", "12:00", 150),
]


def seed_trains(conn: sqlite3.Connection):
    """Insert initial trains if the table is empty.

    Uses TRAIN_DATA and assumes values for TrainNumber, TrainName, AvailableSeats, and Date.
    DateTime column stores the departure timestamp.
    """
    try:
        cur = conn.execute("SELECT COUNT(*) FROM Trains;")
    except sqlite3.OperationalError:
        # Table doesn't exist in this database
        return

    count = cur.fetchone()[0]
    if count > 0:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for idx, (src, dst, dep_time, _arr_time, cost) in enumerate(TRAIN_DATA, start=1):
        train_number = f"T{idx:03d}"
        train_name = f"{src}-{dst} Express"
        available_seats = 200  # assumed default capacity
        departure_dt = f"{today} {dep_time}"
        rows.append(
            (train_number, train_name, src, dst, float(cost), available_seats, departure_dt)
        )

    conn.executemany(
        """
        INSERT INTO Trains (TrainNumber, TrainName, Source, Destination, Cost, AvailableSeats, DateTime)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        rows,
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        cur = conn.execute(f"PRAGMA table_info({table});")
        cols = [row[1] for row in cur.fetchall()]
        return column in cols
    except sqlite3.OperationalError:
        return False


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table,),
        )
        return cur.fetchone() is not None
    except sqlite3.OperationalError:
        return False


def _migrate_schema(conn: sqlite3.Connection):
    """Bring existing databases up to date with the latest schema.

    - Ensure Booking table has TrainNumber, NumPassengers, TotalCost, Timestamp columns.
    - Create Booking table if missing.
    - Ensure Trains table exists (created elsewhere) and then seed data if empty (handled by seed_trains).
    """
    # Ensure Booking table exists
    if not _table_exists(conn, "Booking"):
        conn.execute(
            """
            CREATE TABLE Booking (
                BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID TEXT NOT NULL,
                TrainNumber TEXT NOT NULL,
                NumPassengers INTEGER NOT NULL,
                TotalCost REAL NOT NULL,
                Timestamp TEXT NOT NULL,
                FOREIGN KEY (UserID) REFERENCES User(UserID),
                FOREIGN KEY (TrainNumber) REFERENCES Trains(TrainNumber)
            );
            """
        )
    else:
        # Add missing columns if any (use relaxed constraints to satisfy SQLite ALTER limitations)
        if not _column_exists(conn, "Booking", "TrainNumber"):
            conn.execute("ALTER TABLE Booking ADD COLUMN TrainNumber TEXT;")
        if not _column_exists(conn, "Booking", "NumPassengers"):
            conn.execute("ALTER TABLE Booking ADD COLUMN NumPassengers INTEGER;")
        if not _column_exists(conn, "Booking", "TotalCost"):
            conn.execute("ALTER TABLE Booking ADD COLUMN TotalCost REAL;")
        if not _column_exists(conn, "Booking", "Timestamp"):
            conn.execute("ALTER TABLE Booking ADD COLUMN Timestamp TEXT;")


def init_node_db(node_name):
    db_name = os.path.join(DATA_DIR, f"{node_name}_db.sqlite")
    if os.path.exists(db_name):
        # If DB exists, try to migrate schema and seed trains if the table exists and is empty
        conn = sqlite3.connect(db_name)
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            _migrate_schema(conn)
            seed_trains(conn)
            conn.commit()
            print(f"{db_name} already exists. Ensured schema is up-to-date and Trains are seeded if empty.")
        finally:
            conn.close()
        return

    conn = sqlite3.connect(db_name)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
        CREATE TABLE User (
            UserID TEXT PRIMARY KEY,
            Password TEXT NOT NULL
        );
    """)

    # Trains first (to satisfy FK in Booking)
    conn.execute("""
        CREATE TABLE Trains (
            TrainNumber TEXT PRIMARY KEY,
            TrainName TEXT NOT NULL,
            Source TEXT NOT NULL,
            Destination TEXT NOT NULL,
            Cost REAL NOT NULL,
            AvailableSeats INTEGER NOT NULL,
            DateTime TEXT NOT NULL
        );
    """)

    # Then Booking referencing User and Trains
    conn.execute("""
        CREATE TABLE Booking (
            BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
            UserID TEXT NOT NULL,
            TrainNumber TEXT NOT NULL,
            NumPassengers INTEGER NOT NULL,
            TotalCost REAL NOT NULL,
            Timestamp TEXT NOT NULL,
            FOREIGN KEY (UserID) REFERENCES User(UserID),
            FOREIGN KEY (TrainNumber) REFERENCES Trains(TrainNumber)
        );
    """)


    conn.execute(
        """
        CREATE TABLE Logs (
            LogIndex INTEGER PRIMARY KEY AUTOINCREMENT,
            Term INTEGER DEFAULT 0,
            Timestamp TEXT NOT NULL,
            LeaderID TEXT,
            Action TEXT NOT NULL,
            Data TEXT
        );
        """
    )

    # Seed initial trains data
    seed_trains(conn)

    conn.commit()
    conn.close()
    print(f"{db_name} created successfully.")


if __name__ == "__main__":
    for i in range(0, 10):
        init_node_db(f"node{i}")
