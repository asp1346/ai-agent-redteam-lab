#Main agent file

import anthropic
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

client = anthropic.Anthropic()  # Initialize the Anthropic client

messages = []

while True:
    entry = input("Enter message: ")

    #skip empty messages
    if entry.strip() == "":
        continue

    #exit the program if the user types "exit" or "quit"
    if entry in ["exit", "quit"]:
        print("Exiting the program. Have a nice day!")
        break

    messages.append({"role": "user", "content": entry})  # Append user message to messages list

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        messages=messages
    )
    #Skip thinking blocks and print only the text response from the model
    for block in response.content:
        if block.type == "text":
            print(block.text)  # Print the response from the model

    messages.append({"role": "assistant", "content": response.content})  # Append assistant response to messages list
    