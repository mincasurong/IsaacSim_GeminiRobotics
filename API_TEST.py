from google import genai
import os
from dotenv import load_dotenv

# Use absolute path relative to the script directory to find backend/.env
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, "private", ".env"), override=True)


# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=os.getenv("LLM_API_KEY"))

response = client.models.generate_content(
    model="gemini-robotics-er-2-preview", contents="Explain your capability"
)
print(response.text)