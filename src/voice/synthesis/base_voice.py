from abc import ABC, abstractmethod

class BaseVoice(ABC):
    @abstractmethod
    def speak(self, text: str):
        """
        Convert text to speech and play it.
        """
        pass
