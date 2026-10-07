import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def ask_ai(prompt, uploaded_file):
    print("AI Manager Uploaded File: ", uploaded_file.name)
    print("FILE TYPE:", uploaded_file.content_type)
    print("FILE SIZE:", uploaded_file.size)
    #response = client.chat.completions.create(
    #    model="openrouter/free",
    #    messages=[
    #        {
    #            "role": "user",
    #            "content": prompt
    #        }
    #    ]
    #)
    # debug if API key is not set
    print(os.getenv("OPENROUTER_API_KEY") is not None)
    return "PDF received"