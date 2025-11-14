import random
from asyncio import timeout
from urllib import response

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

NOISY = True # !!! CHANGE THIS TO FALSE TO REDUCE NUMBER OF PRINTED LOGS !!!
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
    node_id = _extract_port(port_address)%10 #Last digit of port address
    db_path = os.path.join(data_dir, f"node{node_id}_db.sqlite")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


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

        # User signed up successfully
        users[request.username] = {
            "password": request.password,
        }
        save_users(users)
        print("Signup successful")
        return auth_pb2.SignupResponse(success=True, message="Signed up successfully!")


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
        # If we are leader and receive a heartbeat from another node, resolve conflict by
        # choosing the node with the lower port number as leader (simple deterministic rule).
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
