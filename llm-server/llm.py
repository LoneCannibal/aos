from ollama import chat
system_instruction = 'You are in charge of a ticket booking system. The cost for a ticket to delhi from pilani costs 20 rupees per person by bus'
stream = chat(
    model='deepseek-r1:1.5b',
    messages=[
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': 'How much does a ticket from Pilani to delhi cost?'}
    ],
    stream=True,
)

for chunk in stream:
  print(chunk['message']['content'], end='', flush=True)