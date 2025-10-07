from llm.base_llm import BaseLLM
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
import os

class Gemini(BaseLLM):
    def __init__(self):
        load_dotenv(find_dotenv())
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        genai.configure(api_key=api_key)        

    def ask_gemini(prompt):
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text
