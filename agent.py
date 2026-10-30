#Main agent file

import anthropic
import sys
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

time_tool = {
    "name": "get_time",
    "description": "Get the current time.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

read_file_tool = {
    "name": "read_file",
    "description": "Read the contents of a file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."}
        },
        "required": ["path"]
    }
}

def get_weather(location):
    # Placeholder function to simulate getting weather data
    # In a real implementation, you would call a weather API here
    return f"The current weather in {location} is sunny with a temperature of 73°F."

def get_time():
    from datetime import datetime
    current_time=datetime.now()
    return f"The current time is {current_time}."

MAX_FILE_CHARS = 10_000  # Cap on how much of a file gets sent back to Claude

def read_file(path):
    # Errors (missing file, directory, no permission, binary file) are raised on purpose -
    # the tool dispatch loop catches them and reports them to Claude with is_error=True
    with open(path, "r", encoding="utf-8") as f:
        contents = f.read(MAX_FILE_CHARS + 1)  # Read one extra char so we can tell if the file is longer than the cap

    if len(contents) > MAX_FILE_CHARS:
        return contents[:MAX_FILE_CHARS] + f"\n\n[Truncated: file is longer than {MAX_FILE_CHARS} characters]"
    return contents

def main():
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
            try:
                response = client.messages.create(
                    model="claude-sonnet-5",
                    max_tokens=1024,
                    messages=messages,
                    tools=[weather_tool, time_tool, read_file_tool]
                )
            except anthropic.AuthenticationError:
                print("Authentication failed. Please check your ANTHROPIC_API_KEY in the .env file.")
                sys.exit(1)
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                print(f"Something went wrong while talking with Claude: {e}")
                break  # Exit the inner loop and wait for user input again

            messages.append({"role": "assistant", "content": response.content})  # Append assistant response to messages list

            #Skip thinking blocks and print only the text response from the model
            for block in response.content:
                if block.type == "text":
                    print(block.text)  # Print the response from the model

            if response.stop_reason != "tool_use":
                break  # Claude gave a final answer - go back to waiting for user input

            #Find every tool call in this response, then send all results back in one message
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id
                    is_error = False  # Reset for every tool call so one failure doesn't mark the others as errors

                    #Any exception a tool raises becomes an error result for Claude instead of crashing the program
                    try:
                        if tool_name == "get_weather":
                            result = get_weather(tool_input["location"])

                        elif tool_name == "get_time":
                            result = get_time()

                        elif tool_name == "read_file":
                            result = read_file(tool_input["path"])

                        else:
                            is_error = True
                            result = f"Error: Unknown tool '{tool_name}'."

                    except Exception as e:
                        is_error = True
                        result = f"Error: {type(e).__name__}: {e}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                        "is_error": is_error
                    })

            messages.append({"role": "user", "content": tool_results})  # Append tool results to messages list

if __name__ == "__main__":
    main()
