#Main agent file

import anthropic
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

client = anthropic.Anthropic()  # Initialize the Anthropic client

messages = []

weather_tool = {
    "name": "get_weather",
    "description": "Get the current weather for a given location.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name, e.g. Portland"}
        },
        "required": ["location"]
    }
}

def get_weather(location):
    # Placeholder function to simulate getting weather data
    # In a real implementation, you would call a weather API here
    return f"The current weather in {location} is sunny with a temperature of 73°F."

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

    #Keep talking to Claude until it gives a real answer, not just a tool request
    while True:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            messages=messages,
            tools=[weather_tool]
        )

        messages.append({"role": "assistant", "content": response.content})  # Append assistant response to messages list

        #Skip thinking blocks and print only the text response from the model
        for block in response.content:
            if block.type == "text":
                print(block.text)  # Print the response from the model

        if response.stop_reason != "tool_use":
            break  # Claude gave a final answer - go back to waiting for user input

        #Resolve every tool call in this response, then send all results back in one message
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                if tool_name == "get_weather":
                    result = get_weather(tool_input["location"])

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result
                })

        messages.append({"role": "user", "content": tool_results})  # Append tool results to messages list
