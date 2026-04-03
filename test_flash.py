import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_gemini_direct_flash():
    key = os.getenv("GEMINI_API_KEY")
    print(f"Key from env: {key[:5]}...")
    genai.configure(api_key=key)
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Say hello")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Direct error: {e}")

if __name__ == "__main__":
    test_gemini_direct_flash()
