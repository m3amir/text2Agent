from imports import *

class LocalLM:
    def __init__(self, model_name: str = "deepseek-r1:latest"):
        """
        Initialize the LocalLM with Ollama
        Args:
            model_name: Name of the Ollama model to use (default: "deepseek-r1:latest")
        """
        self.model_name = model_name
        self.client = AsyncClient(host='http://localhost:11434')
        
    async def _verify_model(self) -> None:
        """Verify that Ollama is running and the model is available"""
        try:
            models = await self.get_available_models()
            if self.model_name not in models:
                print(f"Model {self.model_name} not found. Available models: {models}")
                print(f"Attempting to pull model {self.model_name}...")
                await self.pull_model(self.model_name)
        except ResponseError as e:
            if e.status_code == 404:
                print(f"Model {self.model_name} not found. Pulling it now...")
                await self.pull_model(self.model_name)
            else:
                raise ConnectionError(f"Failed to connect to Ollama: {str(e)}")

    async def generate_text(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate text using the Ollama model
        Args:
            prompt: The prompt to generate text from
            system_prompt: Optional system prompt to guide the model's behavior
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1) 
            max_tokens: Maximum number of tokens to generate
            stop: Optional list of strings to stop generation at
            stream: Whether to stream the response
        Returns:
            Generated text as string or async generator if streaming
        """
        try:
            await self._verify_model()
            
            response = await self.client.generate(
                model=self.model_name,
                prompt=prompt,
                system=system_prompt,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                    "stop": stop or []
                },
                stream=stream
            )
            
            if stream:
                async def response_generator():
                    async for chunk in response:
                        yield chunk['response']
                return response_generator()
            else:
                return response['response']
            
        except Exception as e:
            print(f"Error generating text: {str(e)}")
            return "" if not stream else (s async for s in [])
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Have a chat conversation using the Ollama model
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            max_tokens: Maximum number of tokens to generate
            stop: Optional list of strings to stop generation at
            stream: Whether to stream the response
        Returns:
            Model's response as string or async generator if streaming
        """
        try:
            await self._verify_model()
            
            response = await self.client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                    "stop": stop or []
                },
                stream=stream
            )
            
            if stream:
                async def response_generator():
                    async for chunk in response:
                        yield chunk['message']['content']
                return response_generator()
            else:
                return response['message']['content']
            
        except Exception as e:
            print(f"Error in chat: {str(e)}")
            return "" if not stream else (s async for s in [])

    async def get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            response = await self.client.list()
            return [model.model for model in response['models']]
        except Exception as e:
            print(f"Error getting models: {str(e)}")
            return []
            
    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama
        Args:
            model_name: Name of the model to pull
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.pull(model_name)
            return True
        except Exception as e:
            print(f"Error pulling model: {str(e)}")
            return False
            
    async def embed(
        self, 
        input: Union[str, List[str]]
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text input
        Args:
            input: String or list of strings to generate embeddings for
        Returns:
            List of embeddings or list of lists for batch input
        """
        try:
            await self._verify_model()
            response = await self.client.embeddings(
                model=self.model_name,
                prompt=input
            )
            return response['embedding']
        except Exception as e:
            print(f"Error generating embeddings: {str(e)}")
            return [] if isinstance(input, str) else [[]]