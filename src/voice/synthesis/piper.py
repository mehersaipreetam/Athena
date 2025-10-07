from voice.synthesis.base_voice import BaseVoice
from pathlib import Path
from piper import PiperVoice
import sounddevice as sd

class Piper(BaseVoice):
    def __init__(self, voice_path: str):
        self.voice = PiperVoice.load(model_path=voice_path)

    def speak(self, text: str):
        for chunk in self.voice.synthesize(text=text):
            sd.play(chunk.audio_float_array, samplerate=chunk.sample_rate)
            sd.wait()  # wait until this chunk finishes playing
        