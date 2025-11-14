import customtkinter as ctk
from tkinter import messagebox
import grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import hashlib
from .ticket_ui import create_ticket_page


def create_login_page(root):
    # Clear window if switching screens
    for widget in root.winfo_children():
        widget.destroy()

    frame = ctk.CTkFrame(root, corner_radius=12)
    frame.pack(pady=50, padx=50, fill="both", expand=True)

    title = ctk.CTkLabel(frame, text="🚆 Train Booking Login", font=("Arial", 22, "bold"))
    title.pack(pady=20)

    username_entry = ctk.CTkEntry(frame, placeholder_text="Username")
    password_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*")
    username_entry.pack(pady=10)
    password_entry.pack(pady=10)

    def handle_login():
        username = username_entry.get()
        password = password_entry.get()
        if not username or not password:
            messagebox.showerror("Error", "Please fill all fields")
            return

        channel = grpc.insecure_channel('localhost:50051')
        stub = auth_pb2_grpc.AuthServiceStub(channel)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        response = stub.Login(auth_pb2.LoginRequest(username=username, password=password_hash))

        if response.success:
            messagebox.showinfo("Success", response.message)
            create_ticket_page(root, username)
        else:
            messagebox.showerror("Error", response.message)

    def handle_signup():
        username = username_entry.get()
        password = password_entry.get()
        if not username or not password:
            messagebox.showerror("Error", "Please fill all fields")
            return

        channel = grpc.insecure_channel('localhost:50051')
        stub = auth_pb2_grpc.AuthServiceStub(channel)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        response = stub.Signup(auth_pb2.SignupRequest(username=username, password=password_hash))

        if response.success:
            messagebox.showinfo("Success", "Signup successful. You can now login.")
        else:
            messagebox.showerror("Error", response.message)

    login_btn = ctk.CTkButton(frame, text="Login", command=handle_login, width=200)
    signup_btn = ctk.CTkButton(frame, text="Signup", command=handle_signup, width=200)
    login_btn.pack(pady=10)
    signup_btn.pack(pady=5)
