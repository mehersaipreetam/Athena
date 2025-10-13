# Athena - Your Personal Assistant

**Athena** is a modular, real-time voice assistant built in Python.  
It integrates offline speech recognition, generative AI, and local text-to-speech.

---

## Features (MVP)
- **Speech Recognition:** Offline STT using Vosk.
- **Text-to-Speech:** Piper TTS (streaming per sentence) with modular engine support.
- **LLM Integration:** Google Gemini for generating conversational responses.
- **Core Loop:** Continuous listening, response generation, and speech output. 
- **Exit Commands:** `stop`, `shutdown`, `goodbye`.

---

## Requirements
- Python ≥ 3.13  
- Dependencies: `vosk`, `piper-tts`, `google-generativeai`, `sounddevice`, `python-dotenv`

---

## Usage
```bash
python main.py
```

Athena listens, responds, and runs until you say stop or shutdown.
