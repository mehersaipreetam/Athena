from abc import ABC, abstractmethod

class BaseVoiceRecognizer(ABC):
    """
    Abstract base class for all speech recognizers.
    """

    @abstractmethod
    def listen(self):
        """
        Continuously listen and yield recognized text chunks.
        Should be a generator that yields (final_text, is_final) tuples.
        """
        pass

    @abstractmethod
    def pause(self):
        """Pause the recognizer."""
        pass

    @abstractmethod
    def resume(self):
        """Resume feeding audio to recognizer"""
        pass

    @abstractmethod
    def stop(self):
        """Gracefully stop the recognizer."""
        pass
