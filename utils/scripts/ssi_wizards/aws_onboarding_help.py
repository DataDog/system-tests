import os
import time
import re
import subprocess
from dotenv import load_dotenv
import openai
import ast
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from utils.scripts.ssi_wizards.aws_create_vm_wizard import add_virtual_machine

# openai>=0.27.0
# python-dotenv>=0.20.0
# rich>=13.9.4
console = Console()


def extract_clean_text(content) -> str:
    """Extracts the 'value' field from the string representation of the content,
    then removes file citation annotations.
    """
    # Convert content to string if it's not already
    content_str = content if isinstance(content, str) else str(content)

    # Try to extract text from a pattern like: value='...'
    match = re.search(r"value='(.*?)'", content_str, re.DOTALL)
    if match:  # noqa: SIM108
        raw_text = match.group(1)
    else:
        raw_text = content_str

    # Remove file citation annotations like: 【4:0†source】
    cleaned_text = re.sub(r"【\d+:\d+†source】", "", raw_text)

    # Clean up extra whitespace and return
    return cleaned_text.strip()


# Load environment variables from .env
load_dotenv()

# Set your API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("API key is missing. Generate it from https://platform.openai.com/api-keys and set it in the .env file as OPENAI_API_KEY.")
# Replace with your actual assistant ID
assistant_id = "asst_2mNrwvHHnN8ZY2ngQ9jIA7Uu"

# Open the file and read its content into a variable
with open("utils/scripts/ssi_wizards/aws_assistant.txt", "r", encoding="utf-8") as file:
    run_instructions = file.read()  # Reads the entire file

# Create a conversation thread (without specifying the assistant here)
thread = openai.beta.threads.create()

welcome_message = Text("\n🚀 Welcome to the Onboarding System-Tests Assistant! 🎉\n", style="bold cyan")
welcome_message.append("\n🔹 Your interactive guide to smooth and efficient testing.\n", style="green")
welcome_message.append("🔹 Follow the steps carefully to set up your environment.\n", style="yellow")
welcome_message.append("🔹 Type 'exit' to quit! 💡\n", style="blue")

console.print(welcome_message)

while True:
    # Get user input
    user_input = input("\033[34mYou: ")
    if user_input.strip().lower() == "exit":
        print("Exiting conversation.")
        break
    elif user_input.strip() == "":
        continue

    openai.beta.threads.messages.create(thread_id=thread.id, role="user", content=user_input)

    # Trigger a run with your assistant
    run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id, instructions=run_instructions)

    # Poll until the run is completed
    first_time = True
    while True:
        run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if first_time:
            print("\033[95mThinking...", end="", flush=True)  # Print only once
            first_time = False
        else:
            print(".", end="", flush=True)  # Print dots on the same line
        if run_status.status == "requires_action":
            first_time = True
            tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
            try:
                tool_outputs = []
                for tool_call in tool_calls:
                    name = tool_call.function.name
                    arguments = ast.literal_eval(tool_call.function.arguments)
                    print(f"Tool: {name}")
                    print(f"Arguments: {arguments}")
                    if name == "run_aws_wizard":
                        # Run the script interactively
                        subprocess.run(["bash", "utils/scripts/ssi_wizards/aws_onboarding_wizard.sh"], check=True)
                        message = "The AWS onboarding wizard has been completed."

                    elif name == "create_new_virtual_machine":
                        add_virtual_machine(arguments)
                        message = "The virtual machine has been created."
                    else:
                        message = "I'm not sure what to do."
                    tool_outputs.append(
                        {
                            "tool_call_id": tool_call.id,
                            "output": message,
                        }
                    )
                run_status = openai.beta.threads.runs.submit_tool_outputs_and_poll(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
            except Exception as e:
                print(f"Error: {e}")

        elif run_status.status == "completed":
            # Fetch all messages in the thread
            first_time = True
            messages = openai.beta.threads.messages.list(thread_id=thread.id)
            print("\033[32mAssistant:")
            console.print(Markdown(messages.data[0].content[0].text.value))
            break
        else:
            time.sleep(1)
