import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer
from src.voice.recognition.base_voice import BaseVoiceRecognizer

class VoskRecognizer(BaseVoiceRecognizer):
    def __init__(self, model_path: str, samplerate: int = 16000, blocksize: int = 8000):
        self.model_path = model_path
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.audio_q = queue.Queue()
        self._running = False

        print("[VOSK] Loading model...")
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, samplerate)
        print("[VOSK] Model loaded successfully.")
        self.listening = True

    def _callback(self, indata, frames, time, status):
        if self.listening:
            if status:
                print(f"[VOSK] Status: {status}", flush=True)
            self.audio_q.put(bytes(indata))

    def listen(self):
        """
        Generator that yields recognized text in real time.
        Yields (text, is_final)
        """
        self._running = True
        print("[VOSK] Listening... (Ctrl+C to stop)")

        with sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback
        ):
            try:
                while self._running:
                    data = self.audio_q.get()
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        if result.get("text"):
                            yield result["text"], True
                    else:
                        partial = json.loads(self.recognizer.PartialResult())
                        if partial.get("partial"):
                            yield partial["partial"], False
            except KeyboardInterrupt:
                print("\n[VOSK] Stopped by user.")
                self._running = False

    def pause(self):
        self.listening = False

    def resume(self):
        self.listening = True

    def stop(self):
        self._running = False
        print("[VOSK] Recognition stopped.")
