#Main agent file

import anthropic
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

client = anthropic.Anthropic()  # Initialize the Anthropic client
input = input("Enter message: ")

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": input}
    ]
)

print(response.content[0].text)  # Print the response from the model