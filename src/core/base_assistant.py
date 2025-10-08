import time
import os
import re
from dotenv import load_dotenv, find_dotenv
from voice.recognition.vosk_recognizer import VoskRecognizer
from voice.synthesis.piper import Piper
from llm.gemini_llm import GeminiLLM
from tui.tui_manager import TUIManager

load_dotenv(find_dotenv())

VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH")
PIPER_VOICE_PATH = os.getenv("PIPER_VOICE_PATH")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

speech_recognizer = VoskRecognizer(model_path=VOSK_MODEL_PATH)
tts_engine = Piper(voice_path=PIPER_VOICE_PATH)
llm = GeminiLLM(api_key=GEMINI_API_KEY)

def run_assistant():
    tui = TUIManager()
    tui.update_status("Listening... 🎙️")

    def loop(live, tui):
        print("Athena is online... 🎙️")

        try:
            for text, is_final in speech_recognizer.listen():
                # Update partial text in TUI
                if text:
                    tui.update_partial(text)
                    live.update(tui.render())

                # Skip empty partials
                if not is_final or not text.strip():
                    continue

                # Final recognized speech
                tui.update_final(text)
                tui.update_status("Thinking... 🤔")
                live.update(tui.render())

                # Exit conditions
                if text.lower() in ["stop", "shutdown", "bye", "goodbye"]:
                    tts_engine.speak("Goodbye!")
                    tui.update_status("Shutting down 👋")
                    live.update(tui.render())
                    break

                # Generate response
                response = llm.generate_response(text)
                tui.update_response(response)
                tui.update_status("Speaking... 🗣️")
                live.update(tui.render())

                # Pause recognition while speaking
                speech_recognizer.pause()
                try:
                    updated_response = re.sub(r"[^A-Za-z0-9\s\.,!]", "", response)
                except Exception:
                    # Fallback to original response if regex fails for any reason
                    updated_response = response
                tts_engine.speak(updated_response)
                time.sleep(0.5)
                speech_recognizer.resume()

                # Back to listening
                tui.update_status("Listening... 🎙️")
                live.update(tui.render())

        except KeyboardInterrupt:
            tui.update_status("Shutting down gracefully 💤")
            live.update(tui.render())
        finally:
            speech_recognizer.stop()

    tui.run_live(loop)

