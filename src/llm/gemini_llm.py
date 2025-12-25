import google.generativeai as genai
from llm.base_llm import BaseLLM
from tools.mcp_client import get_default_client


class GeminiLLM(BaseLLM):
    SYSTEM_INSTRUCTIONS = """You are Athena, a friendly and articulate AI assistant. Assume your users are smart and well-informed. Your responses are spoken aloud, so use a natural, conversational tone. Avoid symbols, lists, or special characters. Keep answers concise and engaging - like you're talking to a person. If more detail is requested, expand thoughtfully and clearly.

You have access to tools. Use them when appropriate to provide accurate information."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        
        # Initialize MCP client and fetch tool declarations
        self.mcp_client = get_default_client()
        tool_declarations = self.mcp_client.get_tool_declarations()
        
        # Create tools configuration for Gemini function calling
        self.tools = [{"function_declarations": tool_declarations}]
        
        self.model = genai.GenerativeModel(
            model_name,
            system_instruction=self.SYSTEM_INSTRUCTIONS,
            tools=self.tools
        )
        self.chat = self.model.start_chat()
        print(f"[Gemini] Loaded model: {model_name} with {len(tool_declarations)} MCP tools")

    def _execute_function_call(self, function_call) -> str:
        """Execute a function call via MCP client."""
        func_name = function_call.name
        func_args = dict(function_call.args) if function_call.args else {}
        
        try:
            result = self.mcp_client.call_tool(func_name, func_args)
            return result
        except Exception as e:
            return f"Error executing {func_name}: {e}"

    def generate_response(self, prompt: str, **kwargs) -> str:
        try:
            response = self.chat.send_message(prompt, **kwargs)
            
            # Check if the model wants to call a function
            if response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute the function via MCP
                        func_result = self._execute_function_call(part.function_call)
                        
                        # Send the function result back to the model
                        response = self.chat.send_message(
                            genai.protos.Content(
                                parts=[genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=part.function_call.name,
                                        response={"result": func_result}
                                    )
                                )]
                            ),
                            **kwargs
                        )
                        break
            
            # Extract text response
            if hasattr(response, "text"):
                return response.text.strip()
            elif response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text.strip()
            else:
                return str(response)
                
        except Exception as e:
            return f"[Gemini Error] {e}"

    def stream_response(self, prompt: str, **kwargs):
        """
        Stream Gemini responses token by token (if supported).
        Note: Function calling may not work optimally with streaming.
        """
        try:
            stream = self.model.generate_content(prompt, stream=True, **kwargs)
            for chunk in stream:
                if chunk.candidates and chunk.candidates[0].content.parts:
                    yield chunk.candidates[0].content.parts[0].text
        except Exception as e:
            yield f"[Gemini Stream Error] {e}"
