import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer

# Path to your downloaded Vosk model
MODEL_PATH = "/home/meher/Desktop/Personal Projects/Athena/test/vosk-model-small-en-us-0.15"

# Initialize model
print("Loading model...")
model = Model(MODEL_PATH, lang="")
recognizer = KaldiRecognizer(model, 16000)

# Audio queue
audio_q = queue.Queue()

def callback(indata, frames, time, status):
    """This callback is called for each audio block."""
    if status:
        print(status, flush=True)
    audio_q.put(bytes(indata))

# Stream setup
print("Listening... (press Ctrl+C to stop)")
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                       channels=1, callback=callback):
    try:
        while True:
            data = audio_q.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if result.get("text"):
                    print("You said:", result["text"])
            else:
                partial = json.loads(recognizer.PartialResult())
                if partial.get("partial"):
                    print("Partial:", partial["partial"], end="\r")
    except KeyboardInterrupt:
        print("\nStopped.")
