import customtkinter as ctk
import grpc
import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc


def create_chat_section(parent_frame):
    ctk.CTkLabel(parent_frame, text="🤖 Chat with Train Assistant", font=("Arial", 18, "bold")).pack(pady=10)
    chatbox = ctk.CTkTextbox(parent_frame, width=400, height=350)
    chatbox.pack(pady=10)
    entry = ctk.CTkEntry(parent_frame, placeholder_text="Type your question...")
    entry.pack(pady=5)
    send_btn = ctk.CTkButton(parent_frame, text="Send")
    send_btn.pack(pady=5)

    def send_message():
        user_msg = entry.get().strip()
        if not user_msg:
            return
        entry.delete(0, 'end')
        chatbox.insert("end", f"You: {user_msg}\n")

        channel = grpc.insecure_channel('localhost:50080')
        stub = llm_pb2_grpc.LlmServiceStub(channel)
        response = stub.GetLlmAnswer(llm_pb2.LlmRequest(queryId="1", query=user_msg))
        bot_reply = response.answer

        chatbox.insert("end", f"Bot: {bot_reply}\n\n")
        chatbox.see("end")

    send_btn.configure(command=send_message)
