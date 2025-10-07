import os
import speech_recognition as sr
import google.generativeai as genai
import pyttsx3
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())  # Load environment variables from .env file
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
engine = pyttsx3.init()
recognizer = sr.Recognizer()
mic = sr.Microphone()

def speak(text):
    engine.say(text)
    engine.runAndWait()


print("Athena is online... 🎙️")

while True:
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        query = recognizer.recognize_whisper(audio)  # or recognize_google if online
        print(f"You: {query}")
        if query.lower() in ["stop", "shutdown", "goodbye"]:
            speak("Goodbye!")
            break
        answer = ask_gemini(query)
        print(f"Jarvis: {answer}")
        speak(answer)
    except Exception as e:
        print("Error:", e)
