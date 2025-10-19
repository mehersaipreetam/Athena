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

## Demo

> Here's a quick demonstration of how it works:

<p align="center">
  <img src="assets/demo.gif" width="700"/>
</p>
Athena listens, responds, and runs until you say stop or shutdown.

---

## Contributing

Contributions, feature ideas, and improvements are welcome!

- **Found a bug?** → Open an **Issue**
- **Have a feature idea?** → Start a **Discussion** or create an **Enhancement Issue**
- **Want to contribute code?**
  1. Fork the repository
  2. Create a new branch: `feature/<your-idea>`
  3. Commit your changes and push
  4. Submit a **Pull Request**

Please keep contributions modular and follow the existing code structure under `src/`.

---
