import customtkinter as ctk
from tkinter import messagebox
from .chat_ui import create_chat_section


def create_ticket_page(root, username):
    for widget in root.winfo_children():
        widget.destroy()

    frame_main = ctk.CTkFrame(root, corner_radius=15)
    frame_main.pack(fill="both", expand=True, padx=15, pady=15)

    # Left frame — Ticket booking
    left_frame = ctk.CTkFrame(frame_main, width=450, corner_radius=15)
    left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    ctk.CTkLabel(left_frame, text=f"Welcome, {username}", font=("Arial", 18, "bold")).pack(pady=5)
    ctk.CTkLabel(left_frame, text="Book Your Train Ticket", font=("Arial", 22, "bold")).pack(pady=10)

    from_box = ctk.CTkEntry(left_frame, placeholder_text="From")
    to_box = ctk.CTkEntry(left_frame, placeholder_text="To")
    date_box = ctk.CTkEntry(left_frame, placeholder_text="Date (YYYY-MM-DD)")
    passengers_box = ctk.CTkEntry(left_frame, placeholder_text="No. of Passengers")
    for e in [from_box, to_box, date_box, passengers_box]:
        e.pack(pady=8)

    def book_ticket():
        source = from_box.get()
        destination = to_box.get()
        passengers = passengers_box.get()
        if not source or not destination or not passengers:
            messagebox.showerror("Error", "Please fill all fields")
            return
        fare = int(passengers) * 80
        messagebox.showinfo("Booking Confirmed", f"Ticket booked!\nFrom: {source}\nTo: {destination}\nFare: ₹{fare}")

    ctk.CTkButton(left_frame, text="Book Ticket", command=book_ticket, width=200).pack(pady=10)
    ctk.CTkButton(left_frame, text="Logout", command=lambda: root.destroy(), fg_color="red").pack(pady=10)

    # Right frame — Chatbot
    right_frame = ctk.CTkFrame(frame_main, width=450, corner_radius=15)
    right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
    create_chat_section(right_frame)
