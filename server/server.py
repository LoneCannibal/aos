import random
import grpc
from concurrent import futures
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
import json
import os
import sqlite3
import jwt
import time
from datetime import datetime

NOISY = False  # !!! CHANGE THIS TO FALSE TO REDUCE NUMBER OF PRINTED LOGS !!!
SECRET_KEY = "super_secret_key"
# PORT_ADDRESS = '[::]:50051'
PORT_ADDRESS_START = 50050  # Range from port 500050 to 50059, can be extended later Currently 50050 to 50059
PORT_ADDRESS_RANGE = 10
leader_address = ''  # Current known leader's address
online_servers = []  # List of servers online currently
heartbeat_timeout = 0
current_role = "follower"
last_heartbeat = time.time()
port_address = ''
FAILURE_THRESHOLD = 3  # consecutive heartbeat failures before deeming a peer offline
failure_counts = {}  # target_addr -> consecutive failure count


def _get_db_connection():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    node_id = _extract_port(port_address) % 10  # Last digit of port address
    db_path = os.path.join(data_dir, f"node{node_id}_db.sqlite")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def _get_db_connection_for_node(node_id: int):
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, f"node{node_id}_db.sqlite")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def replicate_log(action: str, data: dict, term: int = 0):
    """Replicate a single log entry using gRPC AppendEntries to peers.

    - Appends locally to this node's Logs table.
    - Sends the same entry to all other known online servers via RaftService.AppendEntries.
    """
    # Serialize payload
    try:
        serialized = json.dumps(data, separators=(",", ":")) if isinstance(data, dict) else str(data)
    except Exception:
        serialized = str(data)

    timestamp = datetime.utcnow().isoformat()
    leader_id = port_address

    # 1) Append locally
    try:
        conn = _get_db_connection()
        cur = conn.execute(
            "INSERT INTO Logs (Term, Timestamp, LeaderID, Action, Data) VALUES (?, ?, ?, ?, ?)",
            (term, timestamp, leader_id, action, serialized),
        )
        conn.commit()
        # Apply to local state machine immediately (Raft-style apply on leader when entry is appended)
        try:
            _apply_log_entry(action, data if isinstance(data, dict) else json.loads(serialized))
        except Exception as e:
            if NOISY:
                print(f"[{port_address}] Failed to apply local log entry: ", e)
        conn.close()
    except Exception as e:
        print(f"[{port_address}] Failed to append local log entry:", e)

    # 2) Send to peers via gRPC AppendEntries
    # Snapshot to avoid concurrent modification
    peers = [s for s in list(online_servers) if s != port_address]

    entry = raft_pb2.LogEntry(
        term=term,
        timestamp=timestamp,
        leader_id=leader_id,
        action=action,
        data=serialized,
    )

    for target in peers:
        host = target.replace("[::]:", "localhost:")
        try:
            channel = grpc.insecure_channel(host)
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            req = raft_pb2.AppendEntriesRequest(entries=[entry])
            resp = stub.AppendEntries(req, timeout=0.5)
            if NOISY:
                print(f"[{port_address}] AppendEntries to {target}: success={resp.success} count={resp.count}")
        except Exception as e:
            if NOISY:
                print(f"[{port_address}] AppendEntries RPC failed to {target}:", e)


def _apply_log_entry_conn(conn, action: str, data: dict):
    """Apply a single log entry to the local database using the provided connection."""
    if action == "Signup":
        username = data.get("username")
        password = data.get("password")
        if not username:
            return
        # Upsert user using INSERT OR REPLACE if password provided, else INSERT OR IGNORE
        if password is not None:
            conn.execute(
                "INSERT OR REPLACE INTO User (UserID, Password) VALUES (?, ?)",
                (username, password),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO User (UserID, Password) VALUES (?, COALESCE((SELECT Password FROM User WHERE UserID = ?), ''))",
                (username, username),
            )
    elif action == "BookingCreate":
        # Expected payload: {"username": str, "train_number": str, "qty": int}
        username = data.get("username")
        train_no = data.get("train_number")
        qty = int(data.get("qty") or 0)
        if not username or not train_no or qty <= 0:
            raise ValueError("Invalid booking payload")

        # Fetch train info
        cur = conn.execute(
            "SELECT AvailableSeats, Cost FROM Trains WHERE TrainNumber=?",
            (train_no,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Train not found")
        available, cost = int(row[0]), float(row[1])
        if qty > available:
            raise ValueError("Not enough seats")

        total_cost = qty * cost
        ts = datetime.utcnow().isoformat()

        # Insert booking and decrement seats atomically
        conn.execute(
            """
            INSERT INTO Booking (UserID, TrainNumber, NumPassengers, TotalCost, Timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, train_no, qty, total_cost, ts),
        )
        conn.execute(
            "UPDATE Trains SET AvailableSeats = AvailableSeats - ? WHERE TrainNumber = ?",
            (qty, train_no),
        )
    # Add more action handlers here as the system grows (e.g., BookingCreate, TrainUpdate, etc.)


def _apply_log_entry(action: str, data: dict):
    """Apply a single log entry to the local database state using its own connection.

    Currently supports:
    - Signup: create or update a user with provided username and password.
    """
    try:
        conn = _get_db_connection()
        _apply_log_entry_conn(conn, action, data)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[{port_address}] Error applying log entry action={action}: ", e)


def _replay_all_logs():
    """Re-apply all logs from the local Logs table to ensure DB state converges.

    This is a simplified catch-up mechanism. Because our apply operations are
    idempotent (INSERT OR REPLACE/IGNORE), re-applying is safe.
    """
    try:
        conn = _get_db_connection()
        cursor = conn.execute("SELECT Action, Data FROM Logs ORDER BY LogIndex ASC")
        rows = cursor.fetchall()
        conn.close()
        for action, data in rows:
            try:
                payload = json.loads(data)
            except Exception:
                payload = {"raw": data}
            _apply_log_entry(action, payload if isinstance(payload, dict) else {"raw": data})
    except Exception as e:
        if NOISY:
            print(f"[{port_address}] Failed to replay logs: ", e)


def load_users():
    try:
        conn = _get_db_connection()
        cursor = conn.execute("SELECT UserID, Password FROM User")
        users = {row[0]: {"password": row[1]} for row in cursor.fetchall()}
        conn.close()
        return users
    except Exception as e:
        print("Failed to load users from SQLite:", e)
        return {}


def save_users(users):
    try:
        conn = _get_db_connection()
        # Upsert each user record
        for username, info in users.items():
            password_hash = info.get("password") if isinstance(info, dict) else info
            conn.execute(
                "INSERT OR REPLACE INTO User (UserID, Password) VALUES (?, ?)",
                (username, password_hash),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print("Failed to save users to SQLite:", e)


def _extract_port(addr: str) -> int:
    try:
        return int(str(addr).split(":")[-1])
    except Exception:
        return -1


def leader_heartbeat_loop():
    global failure_counts, leader_address
    while True:
        time.sleep(0.15)  # heartbeat interval

        if current_role != "leader":
            continue

        # Iterate over a snapshot to allow safe removal from online_servers
        for target in list(online_servers):
            if target == port_address:
                continue

            host = target.replace("[::]:", "localhost:")

            try:
                channel = grpc.insecure_channel(host)
                stub = raft_pb2_grpc.RaftServiceStub(channel)

                response = stub.HeartBeat(
                    raft_pb2.HeartBeatRequest(
                        id=port_address,
                        timestamp=time.time_ns()
                    ),
                    timeout=0.2
                )

                if NOISY: print(f"[{port_address}] Heartbeat ACK from {response.id}")
                # Reset failure counter on success
                if target in failure_counts:
                    failure_counts[target] = 0

            except Exception as e:
                # Increment failure count and remove unreachable peers quietly after threshold
                count = failure_counts.get(target, 0) + 1
                failure_counts[target] = count
                if count >= FAILURE_THRESHOLD:
                    if target in online_servers:
                        online_servers.remove(target)
                    # Clear known leader if it was the unreachable peer
                    if leader_address == target:
                        leader_address = ''
                    print(f"[{port_address}] Removed unreachable server {target} after {count} failures")
                    failure_counts.pop(target, None)
                else:
                    # Log only a brief note on first failure to reduce noise
                    if count == 1:
                        print(f"[{port_address}] Heartbeat failed to reach {host}; will retry")


def election_timeout_loop():
    global current_role, last_heartbeat, leader_address
    while True:
        time.sleep(0.1)
        timeout_period = random.uniform(1.0, 2.0)

        if current_role != "leader" and (time.time() - last_heartbeat) > timeout_period:
            print(f"[{port_address}] HEARTBEAT TIMEOUT → become leader")
            current_role = "leader"
            leader_address = port_address
            last_heartbeat = time.time()


def start_background_threads():
    import threading
    threading.Thread(target=election_timeout_loop, daemon=True).start()
    threading.Thread(target=leader_heartbeat_loop, daemon=True).start()


class AuthService(auth_pb2_grpc.AuthServiceServicer):
    def Login(self, request, context):
        users = load_users()
        username = request.username
        password_hash = request.password

        # Login failed due to invalid credentials
        if username not in users or users[username]['password'] != password_hash:
            return auth_pb2.LoginResponse(success=False, message='Incorrect username or password! Try again.', token='')

        # Login successful
        token = jwt.encode(
            {"username": username, "expiry": time.time() + 3600},
            SECRET_KEY,
            algorithm="HS256"
        )
        print("User ", username, " logged in")
        return auth_pb2.LoginResponse(success=True, message="Login Successful!", token=token)

    def Signup(self, request, context):

        # User already exists
        users = load_users()
        if request.username in users:
            return auth_pb2.SignupResponse(success=False, message='Username already exists! Please choose another one')

        # Build log entry to drive state via Raft log apply on all nodes (leader and followers)
        entry_data = {"username": request.username, "password": request.password}
        if current_role == "leader":
            try:
                replicate_log("Signup", entry_data)
            except Exception as e:
                if NOISY:
                    print(f"[{port_address}] replicate_log failed for Signup:", e)
                return auth_pb2.SignupResponse(success=False, message="Internal error during replication")
        else:
            # If not leader, we still apply locally to allow single-node operation; in a real Raft, client should redirect to leader.
            try:
                _apply_log_entry("Signup", entry_data)
            except Exception as e:
                if NOISY:
                    print(f"[{port_address}] local apply failed for follower Signup:", e)
                return auth_pb2.SignupResponse(success=False, message="Internal error")
        print("Signup successful")
        return auth_pb2.SignupResponse(success=True, message="Signed up successfully!")

    def CreateBooking(self, request, context):
        # Build log entry to replicate booking creation across the cluster
        try:
            username = request.username
            train_no = request.train_number
            qty = int(request.qty)
            if not username or not train_no or qty <= 0:
                return auth_pb2.BookingResponse(success=False, message="Invalid booking request")

            entry_data = {"username": username, "train_number": train_no, "qty": qty}

            # Prefer replication via the current leader (this node should be leader; client discovered it)
            try:
                replicate_log("BookingCreate", entry_data)
            except Exception as e:
                if NOISY: print(f"[{port_address}] replicate_log failed for BookingCreate:", e)
                return auth_pb2.BookingResponse(success=False, message="Internal error during replication")

            return auth_pb2.BookingResponse(success=True, message="Booking created and replicated")
        except Exception as e:
            if NOISY: print(f"[{port_address}] CreateBooking error:", e)
            return auth_pb2.BookingResponse(success=False, message="Internal server error")


class RaftService(raft_pb2_grpc.RaftServiceServicer):
    def Ping(self, request, context):
        return raft_pb2.Pong(message="Hi")

    def HeartBeat(self, request, context):
        global last_heartbeat, current_role, heartbeat_timeout, leader_address
        # follower receives heartbeat from leader
        last_heartbeat = time.time()

        sender = request.id
        # Ensure we track the sender in membership list
        if sender not in online_servers:
            online_servers.append(sender)
        # If we are leader and receive a heartbeat from another node, resolve conflict by choosing the node with the lower port number as leader
        if current_role == "leader":
            my_port = _extract_port(port_address)
            sender_port = _extract_port(sender)
            if sender_port != -1 and my_port != -1 and sender_port < my_port:
                print(f"[{port_address}] Stepping down. Higher-priority leader detected: {sender}")
                current_role = "follower"
                leader_address = sender
        else:
            # We are follower; update known leader
            leader_address = sender

        if NOISY: print(f"[{port_address}] Received heartbeat from {request.id}")

        # follower replies to leader
        return raft_pb2.HeartBeatResponse(
            id=port_address,
            timestamp=time.time_ns()
        )

    def CheckLeader(self, request, context):
        return raft_pb2.CheckLeaderResponse(current_leader=leader_address)

    def AppendEntries(self, request, context):
        # Append provided log entries to local Logs table
        count = 0
        try:
            conn = _get_db_connection()
            for e in request.entries:
                conn.execute(
                    "INSERT INTO Logs (Term, Timestamp, LeaderID, Action, Data) VALUES (?, ?, ?, ?, ?)",
                    (int(e.term), e.timestamp, e.leader_id, e.action, e.data),
                )
                count += 1
                # Apply to state machine
                try:
                    payload = json.loads(e.data)
                except Exception:
                    payload = {"raw": e.data}
                try:
                    _apply_log_entry(e.action, payload if isinstance(payload, dict) else {"raw": e.data})
                except Exception as ap_e:
                    if NOISY:
                        print(f"[{port_address}] Failed to apply entry during AppendEntries: ", ap_e)
            conn.commit()
            conn.close()
            return raft_pb2.AppendEntriesResponse(success=True, count=count)
        except Exception as e:
            print(f"[{port_address}] Failed to append entries via AppendEntries:", e)
            return raft_pb2.AppendEntriesResponse(success=False, count=count)

    def GetAllLogs(self, request, context):
        # Return all known logs in order
        try:
            conn = _get_db_connection()
            cur = conn.execute("SELECT Term, Timestamp, LeaderID, Action, Data FROM Logs ORDER BY LogIndex ASC")
            entries = []
            for term, ts, leader_id, action, data in cur.fetchall():
                entries.append(
                    raft_pb2.LogEntry(
                        term=int(term) if term is not None else 0,
                        timestamp=ts or "",
                        leader_id=leader_id or "",
                        action=action or "",
                        data=data or "",
                    )
                )
            conn.close()
            return raft_pb2.GetAllLogsResponse(entries=entries)
        except Exception as e:
            if NOISY:
                print(f"[{port_address}] GetAllLogs error: ", e)
            # Return empty on error
            return raft_pb2.GetAllLogsResponse(entries=[])


def serve():
    global port_address, leader_address
    # SERVER DISCOVERY
    for i in range(PORT_ADDRESS_RANGE):
        server_address = f"[::]:{PORT_ADDRESS_START + i}"
        # Ping all servers and see which ones are online
        try:
            channel = grpc.insecure_channel(f"localhost:{PORT_ADDRESS_START + i}")
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            ping_response = stub.Ping(raft_pb2.Empty(), timeout=0.1)
            online_servers.append(server_address)
            print("Server found at: ", server_address)
        except Exception as e:
            if NOISY: print("No server found at: ", server_address)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(), server)

    # Search for available ports and generate the port address
    for port in range(PORT_ADDRESS_RANGE):
        try:
            port_address = f"[::]:{PORT_ADDRESS_START + port}"
            server.add_insecure_port(port_address)
            print("Server started on port ", port_address)
            # Add self to the known online servers list if not present
            if port_address not in online_servers:
                online_servers.append(port_address)
            # Proactively introduce this node to already-running peers so they can add us
            try:
                for i in range(PORT_ADDRESS_RANGE):
                    target_addr = f"localhost:{PORT_ADDRESS_START + i}"
                    if target_addr.endswith(str(_extract_port(port_address))):
                        continue  # skip self
                    try:
                        channel = grpc.insecure_channel(target_addr)
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        # If the peer is up, send a one-time HeartBeat with our id so it adds us to its membership
                        stub.Ping(raft_pb2.Empty(), timeout=0.1)
                        try:
                            stub.HeartBeat(
                                raft_pb2.HeartBeatRequest(id=port_address, timestamp=time.time_ns()),
                                timeout=0.2,
                            )
                            if NOISY:
                                print(f"[{port_address}] Introduced self to {target_addr}")
                        except Exception:
                            pass
                    except Exception:
                        # Peer not up; ignore
                        pass
            except Exception:
                pass
            # Try to proactively sync full log from any online peer (late join)
            try:
                for peer in list(online_servers):
                    if peer == port_address:
                        continue
                    host = peer.replace("[::]:", "localhost:")
                    try:
                        channel = grpc.insecure_channel(host)
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        resp = stub.GetAllLogs(raft_pb2.Empty(), timeout=0.8)
                        if resp and resp.entries:
                            # Insert and apply
                            conn = _get_db_connection()
                            for e in resp.entries:
                                try:
                                    conn.execute(
                                        "INSERT INTO Logs (Term, Timestamp, LeaderID, Action, Data) VALUES (?, ?, ?, ?, ?)",
                                        (int(e.term), e.timestamp, e.leader_id, e.action, e.data),
                                    )
                                    try:
                                        payload = json.loads(e.data)
                                    except Exception:
                                        payload = {"raw": e.data}
                                    _apply_log_entry_conn(conn, e.action,
                                                          payload if isinstance(payload, dict) else {"raw": e.data})
                                except Exception:
                                    # ignore duplicates or individual failures
                                    pass
                            conn.commit()
                            conn.close()
                            if NOISY:
                                print(f"[{port_address}] Synced {len(resp.entries)} logs from {peer}")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            _replay_all_logs()
            start_background_threads()
            server.start()
            server.wait_for_termination()
            break
        except Exception as e:
            if NOISY: print("Port ", port_address, " not available trying next one")
    print("Failed to find available port. Too many nodes are online!")

    # TODO: HEARTBEAT GENERATION


# TODO: FIX SERVER STOPPING USING KEYBOARD INTERRUPT
if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print("Server stopped")
        print("Goodbye!")
