import grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import hashlib

#TODO: IMPLEMENT STUFF TO DO HERE
def do_stuff() :
    return
def login():
    channel = grpc.insecure_channel('localhost:50051')
    stub = auth_pb2_grpc.AuthServiceStub(channel)

    #Enter username and password
    username =input("Enter your username: ")
    password_hash = hashlib.sha256(input("Enter your password: ").encode()).hexdigest()

    response = stub.Login(auth_pb2.LoginRequest(username=username,password=password_hash))
    print("Login status: ",response.success)
    print(response.message)
    do_stuff()
    if not response.success:
        login()
    print("Token: ", response.token)
