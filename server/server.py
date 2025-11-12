from urllib import response

import grpc
from concurrent import futures
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import json
import jwt
import time

SECRET_KEY = "sueprsecretkey"
# PORT_ADDRESS = '[::]:50051'
PORT_ADDRESS_START ='[::]:5005' #Range from port 500050 to 50059, can be extended later Currently 50050 to 50059
PORT_ADDRESS_RANGE = 9
leader_address = ''

# Load user data
def load_users():
    try:
        with open('users.json', 'r') as users_file:
            return json.load(users_file)
    except Exception as e:
        print("USERS FILE NOT FOUND: ",users_file, e)
        return{}

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
            {"username": username, "expiry": time.time()+3600},
            SECRET_KEY,
            algorithm="HS256"
        )
        print("User ",username," logged in")
        return auth_pb2.LoginResponse(success=True, message="Login Successful!",token=token)

    def Signup(self, request, context):

        #User already exists
        users = load_users()
        if request.username in users:
            return auth_pb2.SignupResponse(success=False, message='Username already exists! Please choose another one')

        #User signed up successfully
        #TODO: CHECK IF THE PASSWORD HASHING IS WORKING PROPERLY HERE!!!!
        users[request.username] ={
            "password": request.password,
        }
        save_users(users)
        print("Signup successful")
        return auth_pb2.SignupResponse(success=True, message="Signed up successfully!")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    # Search for available ports and generate the port address
    port_address = ''
    for port in  range (PORT_ADDRESS_RANGE):
        try:
            port_address = PORT_ADDRESS_START+str(port)
            server.add_insecure_port(port_address)
            print("Server started on port ", port_address)
            server.start()
            server.wait_for_termination()
            break
        except Exception as e:
            print("Port ",port_address," not available trying next one")
    print("Failed to find available port. Too many nodes are online!")

# TODO: FIX SERVER STOPPING USING KEYBOARD INTERRUPT
if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print("Server stopped")
        print("Goodbye!")
