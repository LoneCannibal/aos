import grpc
from concurrent import futures
import ollama
import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc

PORT_ADDRESS = '[::]:50080'

def get_answer(query):
    # Download the LLM model if it is not present
    preferred_model ="llama3.2:3b"
    models = ollama.list()
    model_list = str(models)
    if preferred_model not in model_list:
        print("LLM Model not found. Downloading it. This will take a long time.")
        ollama.pull(preferred_model)

    system_instruction = 'You are in charge of a train ticket booking system. Customers will ask questions to you about the booking procedure and related topics. The cost for a ticket to delhi from pilani costs 80 rupees per person by train. Make sure you say a fun fact after giving the user any advice unrelated to travel'
    messages=[
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
