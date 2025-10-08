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
    tui.set_status("Listening... 🎙️")

    def loop(live, tui):
        print("Athena is online... 🎙️")
        try:
            for text, is_final in speech_recognizer.listen():
                # Update partial text in TUI
                if text:
                    if not is_final:
                        live.update(tui.render())

                if not is_final or not text.strip():
                    continue

                # Final recognized speech
                tui.add_message("You", text)

                if text.lower() in ["stop", "shutdown", "bye", "goodbye"]:
                    tui.add_message("Athena", "Goodbye!")
                    tui.set_status("Shutting down 👋")
                    live.update(tui.render())
                    tts_engine.speak("Goodbye!")
                    break

                tui.set_status("Thinking... 🤔")
                tui.set_thinking(True)
                live.update(tui.render())

                # Exit conditions


                # Generate response
                response = llm.generate_response(text)
                tui.set_thinking(False)
                tui.add_message("Athena", response)
                tui.set_status("Speaking... 🗣️")
                live.update(tui.render())

                # Speak the response
                try:
                    clean_response = re.sub(r"[^A-Za-z0-9\s\.,!]", "", response)
                except Exception:
                    clean_response = response
                speech_recognizer.pause()
                tts_engine.speak(clean_response)
                time.sleep(0.5)
                speech_recognizer.resume()

                # Back to listening
                tui.set_status("Listening... 🎙️")
                live.update(tui.render())

        except KeyboardInterrupt:
            tui.set_status("Shutting down gracefully 💤")
            live.update(tui.render())
        finally:
            speech_recognizer.stop()

    tui.run_live(loop)