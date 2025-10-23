import grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import hashlib

#TODO: IMPLEMENT STUFF TO DO HERE
def do_stuff() :
    print("DOING LOTS OF AMAZING STUFF!!!")
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
    if response.success:
        print("Login Token: ", response.token)
        do_stuff()

def signup():
    channel = grpc.insecure_channel('localhost:50051')
    stub = auth_pb2_grpc.AuthServiceStub(channel)

    username = input("Choose a username: ")
    password_hash = hashlib.sha256(input("Type your password: ").encode()).hexdigest()
    response = stub.Signup(auth_pb2.SignupRequest(username=username,password=password_hash))
    print("Signup status: ",response.success)
    print(response.message)
    if response.success:
        print("You have been successfully registered " + username + "!")

if __name__ == '__main__':
    while True:
        try:
            channel = grpc.insecure_channel("localhost:50051")
            stub = auth_pb2_grpc.AuthServiceStub(channel)
            case = int(input(" 1.Login\n 2.Signup\n 0.Exit\nSelect an option: "))
            if case == 1:
                login()
            elif case == 2:
                signup()
            else:
                print("Goodbye")
                exit(0)
        except Exception as e:
            print("EXCEPTION: ", e)