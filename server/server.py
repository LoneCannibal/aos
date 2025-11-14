from asyncio import timeout
from urllib import response

import grpc
from concurrent import futures
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
import json
import jwt
import time

SECRET_KEY = "super_secret_key"
# PORT_ADDRESS = '[::]:50051'
PORT_ADDRESS_START = 50050  # Range from port 500050 to 50059, can be extended later Currently 50050 to 50059
PORT_ADDRESS_RANGE = 10
leader_address = ''  # TODO: Implement functionality where the server checks if it is the leader
online_servers = []  # List of servers online currently


# Load user data
def load_users():
    try:
        with open('users.json', 'r') as users_file:
            return json.load(users_file)
    except Exception as e:
        print("USERS FILE NOT FOUND: ", users_file, e)
        return {}


def save_users(users):
    with open('users.json', 'w') as users_file:
        json.dump(users, users_file)


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
        # TODO: CHECK IF THE PASSWORD HASHING IS WORKING PROPERLY HERE!!!!
        users[request.username] = {
            "password": request.password,
        }
        save_users(users)
        print("Signup successful")
        return auth_pb2.SignupResponse(success=True, message="Signed up successfully!")

class RaftService(raft_pb2_grpc.RaftServiceServicer):
    def Ping(self, request, context):
        return raft_pb2.Pong(message="Hi")

def serve():
    # SERVER DISCOVERY
    for i in range(PORT_ADDRESS_RANGE):
        server_address =  f"[::]:{PORT_ADDRESS_START + i}"
        #Ping all servers and see which ones are online
        try:
            channel = grpc.insecure_channel( f"localhost:{PORT_ADDRESS_START + i}")
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            ping_response = stub.Ping(raft_pb2.Empty(),timeout=0.1)
            online_servers.append(server_address)
            print("Server found at: ",server_address)
        except Exception as e:
            print("No server found at: ",server_address)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(), server)

    # Search for available ports and generate the port address
    port_address = ''
    for port in range(PORT_ADDRESS_RANGE):
        try:
            port_address =  f"[::]:{PORT_ADDRESS_START + port}"
            server.add_insecure_port(port_address)
            print("Server started on port ", port_address)
            server.start()
            server.wait_for_termination()
            break
        except Exception as e:
            print("Port ", port_address, " not available trying next one")
    print("Failed to find available port. Too many nodes are online!")


# TODO: FIX SERVER STOPPING USING KEYBOARD INTERRUPT
if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print("Server stopped")
        print("Goodbye!")
