import os
import base64
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def ask_ai(prompt, uploaded_file):
    pdf_bytes = uploaded_file.file.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "file",
                        "file": {
                            "filename": uploaded_file.name,
                            "file_data": "data:application/pdf;base64," + pdf_base64
                        }
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content