import time
from voice.recognition.vosk_recognizer import VoskRecognizer
from voice.synthesis.piper import Piper
from llm.gemini_llm import GeminiLLM
from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())

VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH")
PIPER_VOICE_PATH = os.getenv("PIPER_VOICE_PATH")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

speech_recognizer = VoskRecognizer(model_path=VOSK_MODEL_PATH)
tts_engine = Piper(voice_path=PIPER_VOICE_PATH)
llm = GeminiLLM(api_key=GEMINI_API_KEY)


# --- Core assistant loop ---
def run_assistant():
    print("Athena is online... 🎙️")
    try:
        for text, is_final in speech_recognizer.listen():
            if not text:
                continue

            if is_final:
                print(f"\nYou said: {text}")

                # Exit conditions
                if text.lower() in ["stop", "shutdown", "bye"]:
                    tts_engine.speak("Goodbye!")
                    break

                # Generate LLM response
                response = llm.generate_response(text)
                print(f"Athena: {response}")
                speech_recognizer.pause()
                tts_engine.speak(response)
                time.sleep(1)
                speech_recognizer.resume()

    except KeyboardInterrupt:
        print("\n[Athena] Shutting down gracefully.")
    finally:
        speech_recognizer.stop()
