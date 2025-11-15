import grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc
import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
import hashlib
from datetime import datetime
import json

# Local mirror of initial train data (kept in sync with server/db_init.py)
TRAIN_DATA = [
    ("T001", "Pilani-Delhi Express", "Pilani", "Delhi", 80.0, 200, "09:00"),
    ("T002", "Delhi-Jaipur Express", "Delhi", "Jaipur", 120.0, 200, "11:00"),
    ("T003", "Pilani-Jaipur Express", "Pilani", "Jaipur", 100.0, 200, "07:00"),
    ("T004", "Jaipur-Delhi Express", "Jaipur", "Delhi", 130.0, 200, "15:00"),
    ("T005", "Pilani-Chandigarh Express", "Pilani", "Chandigarh", 150.0, 200, "06:00"),
]

# In-memory availability tracker for this client session
_available_seats = {row[0]: row[5] for row in TRAIN_DATA}

def _today_dt_str(time_str: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{today} {time_str}"

def _print_timetable():
    print("\nAvailable Trains:")
    print("Idx  TrainNo  Name                          Source -> Destination   Departs           Fare   Seats")
    print("---- -------- ----------------------------- ----------------------- ----------------- ------ -----")
    for idx, (tn, name, src, dst, cost, _seats, dep_time) in enumerate(TRAIN_DATA, start=1):
        seats_left = _available_seats.get(tn, 0)
        print(
            f"{idx:>3}  {tn:<8} {name:<29} {src:<7} -> {dst:<12} {_today_dt_str(dep_time):<17} {cost:>5.0f}   {seats_left:>5}"
        )
    print("")

NOISY = True # !!! CHANGE THIS TO FALSE TO REDUCE NUMBER OF PRINTED LOGS !!!
PORT_ADDRESS_START = 50050  # Range from port 500050 to 50059, can be extended later Currently 50050 to 50059
PORT_ADDRESS_RANGE = 10
LLM_ADDRESS = 'localhost:50080'
current_leader_address = ''  # Cache the current leader address
CURRENT_USER = ''  # Logged-in username for booking attribution



def do_stuff():
    while True:
        case = int(
            input("---MENU---\n1.Ask a question\n2.Book ticket\n3.View timetable\n0.Logout\nCHOOSE WHAT TO DO: "))

        if case == 1:
            channel = grpc.insecure_channel(LLM_ADDRESS)
            stub = llm_pb2_grpc.LlmServiceStub(channel)
            query = input("What would you like to know? ")
            # TODO: IMPLEMENT QUERY ID
            response = stub.GetLlmAnswer(llm_pb2.LlmRequest(queryId='1', query=query))
            print(response.answer)

        elif case == 2:
            # Book tickets: show timetable, pick a train, choose number of tickets, and confirm
            _print_timetable()
            try:
                choice = int(input("Enter the index of the train you want to book (0 to cancel): "))
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue
            if choice == 0:
                continue
            if choice < 1 or choice > len(TRAIN_DATA):
                print("Invalid train selection.")
                continue
            tn, name, src, dst, cost, _seats, dep_time = TRAIN_DATA[choice - 1]

            try:
                qty = int(input("How many tickets would you like to book? "))
            except ValueError:
                print("Please enter a valid number for tickets.")
                continue
            if qty <= 0:
                print("Number of tickets must be positive.")
                continue

            seats_left = _available_seats.get(tn, 0)
            if qty > seats_left:
                print(f"Sorry, only {seats_left} seats are available on {tn}.")
                continue

            total_cost = qty * cost
            confirmation = input(
                f"You are booking {qty} ticket(s) on {tn} ({src}->{dst}) departing {_today_dt_str(dep_time)}.\n"
                f"Total cost: Rs {total_cost}. Confirm? Y/N: "
            )
            if confirmation.lower() in ['y', 'yes']:
                if not CURRENT_USER:
                    print("You must be logged in to book. Please login again.")
                    continue
                # Send booking to server via AuthService.CreateBooking; server will replicate via Raft
                try:
                    channel = grpc.insecure_channel(current_leader_address)
                    auth_stub = auth_pb2_grpc.AuthServiceStub(channel)
                    resp = auth_stub.CreateBooking(
                        auth_pb2.BookingRequest(
                            username=CURRENT_USER,
                            train_number=tn,
                            qty=qty,
                        ),
                        timeout=1.0,
                    )
                    if getattr(resp, 'success', False):
                        _available_seats[tn] = seats_left - qty
                        print(f"Booking confirmed and saved! {qty} ticket(s) booked. Remaining seats on {tn}: {_available_seats[tn]}\n")
                    else:
                        print(f"Booking failed: {getattr(resp, 'message', 'Unknown error')}\n")
                except Exception as e:
                    print(f"Error while saving booking: {e}")
            else:
                print("Booking cancelled.\n")

        elif case == 3:
            _print_timetable()

        else:
            logout()
            return

def find_leader():
    for i in range(PORT_ADDRESS_RANGE):
        global current_leader_address
        server_address = f"localhost:{PORT_ADDRESS_START + i}"
        # Ping all servers and see which ones are online
        try:
            channel = grpc.insecure_channel(server_address)
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            ping_response = stub.Ping(raft_pb2.Empty(), timeout=0.1)

            # If any server is found, ask it for current leader address
            if ping_response.message =='Hi':
                if NOISY: print("Found server: ", server_address)
                temp_address = stub.CheckLeader(raft_pb2.Empty()).current_leader
                current_leader_address = f"localhost:{temp_address.split(':')[-1]}"
                if NOISY: print("Leader found at: ", current_leader_address)
                break


        except Exception as e:
            if NOISY:
                print("No server found at: ", server_address)



# TODO: IMPLEMENT LOGOUT FUNCTIONALITY
def logout():
    print("LOGGED OUT\n")
    return


def login():
    global current_leader_address
    global CURRENT_USER
    find_leader()
    channel = grpc.insecure_channel(current_leader_address)
    stub = auth_pb2_grpc.AuthServiceStub(channel)

    # Enter username and password
    username = input("Enter your username: ")
    password_hash = hashlib.sha256(input("Enter your password: ").encode()).hexdigest()

    response = stub.Login(auth_pb2.LoginRequest(username=username, password=password_hash))
    print("Login status: ", response.success)
    print(response.message)
    if response.success:
        print("Login Token: ", response.token)
        CURRENT_USER = username
        do_stuff()
        return


def signup():
    global current_leader_address
    find_leader()
    channel = grpc.insecure_channel(current_leader_address)
    stub = auth_pb2_grpc.AuthServiceStub(channel)

    username = input("Choose a username: ")
    password_hash = hashlib.sha256(input("Type your password: ").encode()).hexdigest()
    response = stub.Signup(auth_pb2.SignupRequest(username=username, password=password_hash))
    print("Signup status: ", response.success)
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
