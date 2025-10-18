import google.generativeai as genai
from llm.base_llm import BaseLLM

class GeminiLLM(BaseLLM):
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        print(f"[Gemini] Loaded model: {model_name}")

    def generate_response(self, prompt: str, **kwargs) -> str:
        try:
            system_instructions = "You are Athena, a friendly and articulate AI assistant. Assume your users are smart and well-informed. Your responses are spoken aloud, so use a natural, conversational tone. Avoid symbols, lists, or special characters. Keep answers concise and engaging - like you're talking to a person. If more detail is requested, expand thoughtfully and clearly"
            updated_prompt = f"{system_instructions}\n\nUser: {prompt}\nAthena:"
            response = self.model.generate_content(updated_prompt, **kwargs)
            return response.text.strip() if hasattr(response, "text") else str(response)
        except Exception as e:
            return f"[Gemini Error] {e}"

    def stream_response(self, prompt: str, **kwargs):
        """
        Stream Gemini responses token by token (if supported).
        """
        try:
            stream = self.model.generate_content(prompt, stream=True, **kwargs)
            for chunk in stream:
                if chunk.candidates and chunk.candidates[0].content.parts:
                    yield chunk.candidates[0].content.parts[0].text
        except Exception as e:
            yield f"[Gemini Stream Error] {e}"
