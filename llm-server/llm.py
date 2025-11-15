import grpc
from concurrent import futures
import ollama
import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc

PORT_ADDRESS = '[::]:50080'


def get_answer(query):
    # Download the LLM model if it is not present
    preferred_model = "llama3.2:3b"
    models = ollama.list()
    model_list = str(models)
    if preferred_model not in model_list:
        print("LLM Model not found. Downloading it. This will take a long time.")
        ollama.pull(preferred_model)

    system_instruction = 'You are in charge of a train ticket booking system. Customers will ask questions to you about the booking procedure and related topics. Here are the train details Idx  TrainNo  Name                          Source -> Destination   Departs           Fare   Seats 1  T001     Pilani-Delhi Express          Pilani  -> Delhi        2025-11-15 09:00     80     200 2  T002     Delhi-Jaipur Express          Delhi   -> Jaipur       2025-11-15 11:00    120     200 3  T003     Pilani-Jaipur Express         Pilani  -> Jaipur       2025-11-15 07:00    100     200 4  T004     Jaipur-Delhi Express          Jaipur  -> Delhi        2025-11-15 15:00    130     200 5  T005     Pilani-Chandigarh Express     Pilani  -> Chandigarh   2025-11-15 06:00    150     200'
    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': query}
    ]

    response = ollama.chat(model=preferred_model, messages=messages)
    print(response['message']['content'])
    return response['message']['content']


class LlmService(llm_pb2_grpc.LlmServiceServicer):
    def GetLlmAnswer(self, request, context):
        print(request.query, " Query received")
        answer = get_answer(request.query)
        return llm_pb2.LlmReply(queryId=request.queryId, answer=answer)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    llm_pb2_grpc.add_LlmServiceServicer_to_server(LlmService(), server)
    server.add_insecure_port(PORT_ADDRESS)
    print("LLM server started on port ", PORT_ADDRESS)
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print("LLM Server stopped")
        print("Goodbye!")
