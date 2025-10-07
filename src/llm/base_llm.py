class BaseLLM:
    def generate_response(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError("Subclasses must implement this method.")
    