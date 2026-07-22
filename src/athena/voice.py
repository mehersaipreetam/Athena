"""
Athena Voice I/O - Lean STT and TTS implementations.
Uses faster-whisper (CPU-friendly) and piper-tts (lightweight).
"""
import os
import sys
import logging
import queue
import threading
import time
from typing import Generator, Tuple, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ==================== STT Engines ====================

def create_stt(
    engine: str = "whisper",
    model_name: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8",
    **kwargs
) -> Callable[[], Generator[Tuple[str, bool], None, None]]:
    """Create an STT generator function based on engine."""
    if engine == "whisper":
        return _create_whisper_stt(model_name, device, compute_type)
    elif engine == "nemotron":
        return _create_nemotron_stt(model_name, **kwargs)
    elif engine == "default":
        return default_stt
    else:
        raise ValueError(f"Unknown STT engine: {engine}")


def _create_whisper_stt(
    model_name: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8"
) -> Callable[[], Generator[Tuple[str, bool], None, None]]:
    """Create faster-whisper STT generator."""
    try:
        from faster_whisper import WhisperModel
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        raise ImportError(f"faster-whisper or sounddevice not installed: {e}")

    # Load model
    logger.info(f"[STT] Loading faster-whisper model: {model_name} on {device}")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    logger.info("[STT] Model loaded")

    # Audio parameters
    SAMPLE_RATE = 16000
    BLOCK_SIZE = 512
    SILENCE_THRESHOLD = 0.002  # Lowered for better sensitivity
    SILENCE_DURATION = 1.5  # seconds of silence to end utterance
    MAX_UTTERANCE = 30.0  # max seconds per utterance

    def stt_generator() -> Generator[Tuple[str, bool], None, None]:
        audio_queue = queue.Queue()

        # Use mutable dict for state to avoid nonlocal issues
        state = {
            'recording': False,
            'buffer': [],
            'silence_blocks': 0,
            'utterance_start': 0.0,
        }

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"[STT] Audio status: {status}")
            # ALWAYS put audio in queue - main loop decides whether to record
            audio_queue.put(indata.copy())

        def process_audio():
            nonlocal state

            # Initialize state for each new utterance
            state = {
                'recording': False,
                'buffer': [],
                'silence_blocks': 0,
                'utterance_start': 0.0,
            }

            while True:
                if not state['recording']:
                    # Wait for voice activity
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    # Simple VAD: check RMS
                    rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                    if rms > SILENCE_THRESHOLD:
                        state['recording'] = True
                        state['buffer'] = [chunk]
                        state['silence_blocks'] = 0
                        state['utterance_start'] = time.time()
                else:
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                        state['buffer'].append(chunk)

                        # Check silence
                        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                        if rms < SILENCE_THRESHOLD:
                            state['silence_blocks'] += 1
                        else:
                            state['silence_blocks'] = 0

                        # Check end conditions
                        silence_time = state['silence_blocks'] * BLOCK_SIZE / SAMPLE_RATE
                        utterance_time = time.time() - state['utterance_start']

                        if silence_time >= SILENCE_DURATION or utterance_time >= MAX_UTTERANCE:
                            # Process utterance
                            state['recording'] = False
                            audio_data = np.concatenate(state['buffer']).flatten()
                            yield audio_data
                            state = {
                                'recording': False,
                                'buffer': [],
                                'silence_blocks': 0,
                                'utterance_start': 0.0,
                            }

                    except queue.Empty:
                        continue

        # Start audio stream
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype='float32',
            channels=1,
            callback=audio_callback
        ):
            logger.info("[STT] Listening... (Ctrl+C to stop)")
            for audio_data in process_audio():
                if len(audio_data) < SAMPLE_RATE * 0.5:  # Skip too short
                    continue

                # Transcribe
                segments, info = model.transcribe(
                    audio_data,
                    beam_size=1,
                    language="en",
                    vad_filter=True,
                )

                text = " ".join(s.text for s in segments).strip()
                if text:
                    yield text, True

    return stt_generator


def _create_nemotron_stt(model_name: str = "nvidia/nemotron-speech-streaming-en-0.6b", **kwargs):
    """Create Nemotron STT (requires NeMo)."""
    try:
        import nemo.collections.asr as nemo_asr
        import torch
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        raise ImportError(f"Nemotron requirements not met: {e}")

    logger.info(f"[STT] Loading Nemotron model: {model_name}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name, map_location=device)
    asr_model = asr_model.to(device)
    asr_model.eval()
    logger.info(f"[STT] Nemotron loaded on {device}")

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 8192

    def stt_generator() -> Generator[Tuple[str, bool], None, None]:
        audio_queue = queue.Queue()
        text_queue = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())

        def process_worker():
            buffer = []
            silence_chunks = 0
            MAX_SILENCE = 2

            while True:
                data = audio_queue.get()
                if data is None:
                    break

                audio_chunk = data.flatten()

                # Simple VAD (could use Silero here)
                rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
                if rms > 0.01:
                    buffer.append(audio_chunk)
                    silence_chunks = 0
                elif buffer:
                    silence_chunks += 1

                if buffer and silence_chunks >= MAX_SILENCE:
                    full_audio = np.concatenate(buffer)
                    buffer = []
                    silence_chunks = 0

                    audio_tensor = torch.tensor(
                        full_audio, dtype=torch.float32, device=device
                    ).unsqueeze(0)
                    audio_len = torch.tensor([audio_tensor.shape[1]], device=device)

                    with torch.no_grad():
                        processed_signal, processed_signal_length = asr_model.preprocessor(
                            input_signal=audio_tensor, length=audio_len
                        )
                        encoded, encoded_len = asr_model.encoder(
                            audio_signal=processed_signal, length=processed_signal_length
                        )
                        best_hyps = asr_model.decoding.rnnt_decoder_predictions_tensor(
                            encoder_output=encoded, encoded_lengths=encoded_len
                        )
                        text = best_hyps[0].text

                    if text.strip():
                        text_queue.put((text.strip(), True))

        # Start worker
        worker = threading.Thread(target=process_worker, daemon=True)
        worker.start()

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype='float32',
            channels=1,
            callback=audio_callback
        ):
            logger.info("[STT] Nemotron listening...")
            while True:
                try:
                    text, is_final = text_queue.get(timeout=0.5)
                    yield text, is_final
                except queue.Empty:
                    continue

    return stt_generator


# ==================== TTS Engines ====================

def create_tts(
    engine: str = "piper",
    voice: str = "en_US-lessac-medium",
    **kwargs
) -> Callable[[str], None]:
    """Create a TTS function based on engine."""
    if engine == "piper":
        return _create_piper_tts(voice)
    elif engine == "kokoro":
        return _create_kokoro_tts(voice, **kwargs)
    elif engine == "edge":
        return _create_edge_tts(voice)
    elif engine == "default":
        return default_tts
    else:
        raise ValueError(f"Unknown TTS engine: {engine}")


def _create_piper_tts(voice: str = "en_US-lessac-medium") -> Callable[[str], None]:
    """Create Piper TTS function."""
    try:
        from piper import PiperVoice
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        raise ImportError(f"piper-tts or sounddevice not installed: {e}")

    # Find voice model - handle both directory and direct file layouts
    voice_path = Path(voice)

    # Determine ONNX and config paths
    if voice_path.is_dir():
        # Directory layout: voice/en_US-lessac-medium.onnx
        onnx_path = voice_path / f"{voice_path.name}.onnx"
        config_path = voice_path / f"{voice_path.name}.onnx.json"
    elif voice_path.suffix == ".onnx":
        # Direct ONNX file path
        onnx_path = voice_path
        config_path = voice_path.with_suffix(".onnx.json")
    else:
        # Try common locations
        search_paths = [
            Path.home() / ".local" / "share" / "piper" / "voices" / f"{voice}.onnx",
            Path("/usr/share/piper/voices") / f"{voice}.onnx",
            Path(sys.prefix) / "share" / "piper" / "voices" / f"{voice}.onnx",
        ]

        onnx_path = None
        config_path = None

        for p in search_paths:
            if p.exists():
                onnx_path = p
                config_candidate = p.with_suffix(".onnx.json")
                if config_candidate.exists():
                    config_path = config_candidate
                break

        if onnx_path is None:
            # Try directory-based layout
            for p in [
                Path.home() / ".local" / "share" / "piper" / "voices" / voice,
                Path("/usr/share/piper/voices") / voice,
                Path(sys.prefix) / "share" / "piper" / "voices" / voice,
            ]:
                if p.is_dir():
                    test_onnx = p / f"{voice}.onnx"
                    test_config = p / f"{voice}.onnx.json"
                    if test_onnx.exists() and test_config.exists():
                        onnx_path = test_onnx
                        config_path = test_config
                        break

    if onnx_path is None or not onnx_path.exists():
        raise FileNotFoundError(f"Piper voice ONNX not found for: {voice}")

    if config_path is None or not config_path.exists():
        raise FileNotFoundError(f"Piper voice config not found for: {voice}")

    logger.info(f"[TTS] Loading Piper voice: {onnx_path}")
    piper_voice = PiperVoice.load(onnx_path, config_path)

    def tts(text: str):
        if not text.strip():
            return

        # Generate audio
        audio_chunks = []
        for chunk in piper_voice.synthesize(text):
            # chunk is an AudioChunk with .audio_float_array or .audio_int16_array
            if hasattr(chunk, 'audio_int16_array'):
                audio_chunks.append(chunk.audio_int16_array)
            elif hasattr(chunk, 'audio_float_array'):
                # Convert float to int16
                audio_chunks.append((chunk.audio_float_array * 32767).astype(np.int16))
            else:
                # Fallback - try to convert
                audio_chunks.append(np.frombuffer(chunk, dtype=np.int16))

        if audio_chunks:
            audio = np.concatenate(audio_chunks)
            # Normalize and play
            audio = audio.astype(np.float32) / 32768.0
            sd.play(audio, samplerate=piper_voice.config.sample_rate)
            sd.wait()

    return tts


def _create_kokoro_tts(voice: str = "af_heart", **kwargs) -> Callable[[str], None]:
    """Create Kokoro TTS function (ONNX version)."""
    try:
        import kokoro_onnx
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        raise ImportError(f"kokoro-onnx or sounddevice not installed: {e}")

    model_path = Path(kwargs.get("model_path", "kokoro-v1.0.onnx"))
    voices_path = Path(kwargs.get("voices_path", "voices.json"))

    if not model_path.exists():
        raise FileNotFoundError(f"Kokoro model not found: {model_path}")

    logger.info(f"[TTS] Loading Kokoro: {model_path}")
    tts = kokoro_onnx.Kokoro(str(model_path), str(voices_path))

    def tts_func(text: str):
        if not text.strip():
            return

        samples, sample_rate = tts.create(text, voice=voice, speed=1.0)
        sd.play(samples, samplerate=sample_rate)
        sd.wait()

    return tts_func


def _create_edge_tts(voice: str = "en-US-AriaNeural") -> Callable[[str], None]:
    """Create Edge TTS function (cloud-based)."""
    try:
        import edge_tts
        import asyncio
        import sounddevice as sd
        import numpy as np
        from io import BytesIO
    except ImportError as e:
        raise ImportError(f"edge-tts or sounddevice not installed: {e}")

    async def _synthesize(text: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    def tts(text: str):
        if not text.strip():
            return

        loop = asyncio.new_event_loop()
        audio_data = loop.run_until_complete(_synthesize(text))
        loop.close()

        # Parse MP3 (simplified - use pydub for real implementation)
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            mp3_path = f.name

        # Convert to WAV for sounddevice
        wav_path = mp3_path.replace(".mp3", ".wav")
        subprocess.run(["ffmpeg", "-y", "-i", mp3_path, wav_path], capture_output=True)

        try:
            import soundfile as sf
            data, sr = sf.read(wav_path)
            sd.play(data, samplerate=sr)
            sd.wait()
        finally:
            os.unlink(mp3_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)

    return tts


# ==================== Default Fallbacks ====================

class ShutdownRequested(Exception):
    """Signal that user requested shutdown."""
    pass

def default_stt() -> Generator[Tuple[str, bool], None, None]:
    """Fallback STT using text input."""
    print("Type your input (or 'quit' to exit):")
    while True:
        try:
            text = input("You: ").strip()
            if text.lower() in ("quit", "exit", "q"):
                raise ShutdownRequested()
            if text:
                yield text, True
        except (EOFError, KeyboardInterrupt):
            raise ShutdownRequested()


def default_tts(text: str):
    """Fallback TTS using print."""
    print(f"Athena: {text}")


# ==================== Voice Manager (for advanced use) ====================

@dataclass
class VoiceConfig:
    stt_engine: str = "whisper"
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    tts_engine: str = "piper"
    tts_voice: str = "en_US-lessac-medium"
    sample_rate: int = 16000
    headphones_mode: bool = False


class VoiceManager:
    """Manages STT/TTS lifecycle for advanced use cases."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self.stt_fn = None
        self.tts_fn = None
        self._stt_thread = None
        self._running = False

    def initialize(self):
        """Initialize STT and TTS engines."""
        logger.info(f"[VOICE] Initializing STT: {self.config.stt_engine}")
        self.stt_fn = create_stt(
            self.config.stt_engine,
            self.config.stt_model,
            self.config.stt_device,
            self.config.stt_compute_type,
        )

        logger.info(f"[VOICE] Initializing TTS: {self.config.tts_engine}")
        self.tts_fn = create_tts(self.config.tts_engine, self.config.tts_voice)

    def listen(self) -> Generator[Tuple[str, bool], None, None]:
        """Start listening for speech."""
        if not self.stt_fn:
            self.initialize()
        self._running = True
        yield from self.stt_fn()

    def speak(self, text: str):
        """Speak text."""
        if not self.tts_fn:
            self.initialize()
        self.tts_fn(text)

    def stop(self):
        """Stop listening."""
        self._running = False