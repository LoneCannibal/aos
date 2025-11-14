"""
ENTRY POINT: client/ui.py
--------------------------------
Starts backend servers (Auth + LLM) if not running.
Loads Login UI, which on success opens Ticket + Chatbot.
"""

import subprocess, threading, socket, time
import customtkinter as ctk
from frontend.login_ui import create_login_page


def is_port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result == 0


def start_backend_if_not_running():
    # Auth Server
    if not is_port_open(50051):
        print("🔹 Starting Auth Server...")
        threading.Thread(target=lambda: subprocess.run(["python", "../server/server.py"])).start()
        time.sleep(3)

    # LLM Server
    if not is_port_open(50080):
        print("🔹 Starting LLM Server...")
        threading.Thread(target=lambda: subprocess.run(["python", "../llm-server/llm.py"])).start()
        time.sleep(6)

    print("✅ Backend ready.\n")


if __name__ == "__main__":
    start_backend_if_not_running()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Distributed Ticket Booking System")
    root.geometry("950x600")

    create_login_page(root)
    root.mainloop()
