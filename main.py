#!/usr/bin/env python3
"""
Athena - Lean Jarvis-like AI Assistant
Entry point for the new lean architecture.
"""
import os
import sys
import argparse
import logging

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from athena.config import config
from athena.core import AthenaAssistant
from athena.voice import create_stt, create_tts, default_stt, default_tts


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # Suppress verbose third-party logs
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Athena - Lean AI Assistant")
    parser.add_argument(
        "--headphones", action="store_true",
        help="Enable headphones mode (mic active during TTS)"
    )
    parser.add_argument(
        "--stt", choices=["whisper", "nemotron", "default"],
        default=config.stt_engine,
        help="Speech-to-text engine"
    )
    parser.add_argument(
        "--tts", choices=["piper", "kokoro", "edge", "default"],
        default=config.tts_engine,
        help="Text-to-speech engine"
    )
    parser.add_argument(
        "--stt-model", default=config.stt_model,
        help="STT model name"
    )
    parser.add_argument(
        "--tts-voice", default=config.tts_voice,
        help="TTS voice name"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--no-tui", action="store_true",
        help="Disable TUI (text-only mode)"
    )
    args = parser.parse_args()

    # Setup logging - minimal, no verbose logs
    setup_logging("WARNING" if not args.debug else "DEBUG")

    # Override config from args
    config.headphones_mode = args.headphones or config.headphones_mode
    config.stt_engine = args.stt
    config.tts_engine = args.tts

    # Initialize voice I/O
    try:
        if args.stt == "default":
            stt_fn = default_stt
        else:
            stt_fn = create_stt(
                engine=args.stt,
                model_name=args.stt_model,
                device=config.stt_device,
                compute_type=config.stt_compute_type,
            )
    except Exception as e:
        print(f"[WARN] STT engine '{args.stt}' failed: {e}")
        print("       Falling back to text input mode.")
        stt_fn = default_stt

    try:
        if args.tts == "default":
            tts_fn = default_tts
        else:
            tts_fn = create_tts(
                engine=args.tts,
                voice=args.tts_voice,
            )
    except Exception as e:
        print(f"[WARN] TTS engine '{args.tts}' failed: {e}")
        print("       Falling back to text output mode.")
        tts_fn = default_tts

    # Initialize TUI if available and not disabled
    tui = None
    if not args.no_tui:
        try:
            from src.tui.tui_manager import TUIManager
            tui = TUIManager()
            # No banner, no verbose output
        except ImportError:
            pass

    # Create and run Athena
    assistant = AthenaAssistant(
        stt_fn=stt_fn,
        tts_fn=tts_fn,
        tui=tui,
        headphones_mode=config.headphones_mode,
    )

    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\n\033[90mInterrupted.\033[0m")
    except Exception as e:
        logging.error(f"[FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()