from abc import ABC, abstractmethod

class BaseLLM(ABC):
    """
    Abstract base class for all Large Language Model (LLM) integrations.
    Defines a standard interface for text generation and chat-style interactions.
    """

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a text response given a prompt.

        Args:
            prompt (str): Input text prompt or user query.
            **kwargs: Optional parameters like temperature, max_tokens, etc.

        Returns:
            str: Generated text response.
        """
        pass

    def stream_response(self, prompt: str, **kwargs):
        """
        Optionally override to stream model responses (token by token).
        Default implementation yields nothing.
        """
        yield from ()
