import grpc
from concurrent import futures

import ollama

import protos.llm_pb2 as llm_pb2
import protos.llm_pb2_grpc as llm_pb2_grpc
from ollama import chat

#def getLLMAnswer(requestId, query, context):

# Download the LLM model if it is not present
models = ollama.list()
model_list = str(models)
if "llama3.2" not in model_list:
    print("LLM Model not found. Downloading it. This will take a long time.")
    ollama.pull('llama3.2:3b')

system_instruction = 'You are in charge of a ticket booking system. The cost for a ticket to delhi from pilani costs 20 rupees per person by bus. Make sure you say a fun fact after giving the user any advice unrelated to travel'
stream = chat(
    model='llama3.2:3b',
    messages=[
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': 'How much does a ticket from Pilani to delhi cost?'}
    ],
    stream=True,
)

for chunk in stream:
  print(chunk['message']['content'], end='', flush=True)