import grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc
import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
import hashlib

PORT_ADDRESS_START ='[::]:5005' #Range from port 500050 to 50059, can be extended later Currently 50050 to 50059
PORT_ADDRESS_RANGE = 9

def do_stuff() :
    while True:
        case = int(input("---MENU---\n1.Ask a question\n2.Book ticket\n3.View timetable\n0.Logout\nCHOOSE WHAT TO DO: "))

        if case == 1:
            channel = grpc.insecure_channel('localhost:50080')
            stub = llm_pb2_grpc.LlmServiceStub(channel)
            query = input("What would you like to know? ")
            #TODO: IMPLEMENT QUERY ID
            response = stub.GetLlmAnswer(llm_pb2.LlmRequest(queryId='1', query=query))
            print(response.answer)

        elif case == 2:
            source = input("Enter place from where you want to travel: ")
            destination = input("Enter destination: ")
            confirmation = input("Ticket costs 80 rupees. Would you like to confirm your ticket? Y/N")
            if confirmation == 'Y' or confirmation == 'yes' or confirmation == 'YES' or confirmation=='y':
                print("Booking confirmed")
            else:
                print("Booking not done")

        elif case == 3:
            print("Timetable")

        else:
            logout()


#TODO: IMPLEMENT LOGOUT FUNCTIONALITY
def logout() :
    print("LOGGED OUT\n")

def login():
    channel = grpc.insecure_channel('localhost:50050')
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
    channel = grpc.insecure_channel('localhost:50050')
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
        case = int(input(" 1.Login\n 2.Signup\n 0.Exit\nSelect an option: "))
        if case == 1:
            login()
        elif case == 2:
            signup()
        else:
            print("Goodbye")
            exit(0)
