import grpc
from concurrent import futures
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import json
import jwt
import time

SECRET_KEY = "sueprsecretkey"

# Load user data
def load_users():
    try:
        with open('users.json', 'r') as users_file:
            return json.load(users_file)
    except FileNotFoundError:
        print("USERS FILE NOT FOUND: user.json")
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
            return auth_pb2_grpc.LoginResponse(success=False, message='Incorrect username or password! Try again.', token='')

        # Login successful
        token = jwt.encode(
            {"username": username, "expiry": time.time()+3600},
            SECRET_KEY,
            algorithm="HS256"
        )
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
        return auth_pb2.SignupResposne(success=True, message="Signed up successfully!")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    server.add_insecure_port('[::]:50051')
    print(" Server running on port 50051")
    server.start()
    server.wait_for_termination()

# TODO: FIX SERVER STOPPING USING KEYBOARD INTERRUPT
if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print("Server stopped!")
        print("Goodbye")
