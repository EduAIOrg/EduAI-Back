"""LLM factory for creating Hugging Face language model instances."""
import logging
from typing import Any, AsyncIterator, Iterator, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessageChunk, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from pydantic import Field
from huggingface_hub import AsyncInferenceClient, InferenceClient

from app.config import settings

logger = logging.getLogger(__name__)


class HuggingFaceLLM(BaseChatModel):
    """Custom LangChain ChatModel implementation for Hugging Face Inference API."""

    model_name: str = Field(default="Qwen/Qwen2.5-7B-Instruct")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=2048)
    hf_token: str = Field(default="")

    def _get_async_client(self) -> AsyncInferenceClient:
        return AsyncInferenceClient(
            model=self.model_name,
            token=self.hf_token if self.hf_token else None
        )

    def _get_sync_client(self) -> InferenceClient:
        return InferenceClient(
            model=self.model_name,
            token=self.hf_token if self.hf_token else None
        )

    @property
    def _llm_type(self) -> str:
        return "huggingface_chat"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        formatted = []
        for m in messages:
            if isinstance(m, SystemMessage):
                formatted.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                formatted.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                formatted.append({"role": "assistant", "content": m.content})
            else:
                role = getattr(m, "role", "user")
                formatted.append({"role": role, "content": m.content})
        return formatted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            client = self._get_sync_client()
            hf_messages = self._convert_messages(messages)
            
            response = client.chat_completion(
                messages=hf_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            content = response.choices[0].message.content or ""
            chat_generation = ChatGeneration(message=AIMessage(content=content))
            return ChatResult(generations=[chat_generation])
        except Exception as e:
            logger.error(f"Error in HuggingFaceLLM _generate: {e}")
            # Fallback to an empty message or propagation
            raise

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            client = self._get_async_client()
            hf_messages = self._convert_messages(messages)
            
            response = await client.chat_completion(
                messages=hf_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            content = response.choices[0].message.content or ""
            chat_generation = ChatGeneration(message=AIMessage(content=content))
            return ChatResult(generations=[chat_generation])
        except Exception as e:
            logger.error(f"Error in HuggingFaceLLM _agenerate: {e}")
            raise

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        try:
            client = self._get_sync_client()
            hf_messages = self._convert_messages(messages)
            
            response = client.chat_completion(
                messages=hf_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield ChatGenerationChunk(message=AIMessageChunk(content=delta))
        except Exception as e:
            logger.error(f"Error in HuggingFaceLLM _stream: {e}")
            yield ChatGenerationChunk(message=AIMessageChunk(content=f"\n[Erreur d'inférence API: {str(e)}]"))

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        logger.info(f"Starting HuggingFaceLLM _astream (Model: {self.model_name})")
        try:
            client = self._get_async_client()
            hf_messages = self._convert_messages(messages)
            
            logger.info("Sending chat completion request to Hugging Face Inference API (stream=True)")
            response = await client.chat_completion(
                messages=hf_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            chunk_count = 0
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    chunk_count += 1
                    logger.debug(f"HuggingFaceLLM _astream received chunk {chunk_count}: {repr(delta)}")
                    yield ChatGenerationChunk(message=AIMessageChunk(content=delta))
                    
            logger.info(f"HuggingFaceLLM _astream completed successfully. Total chunks received: {chunk_count}")
        except Exception as e:
            logger.error(f"Error in HuggingFaceLLM _astream: {e}", exc_info=True)
            yield ChatGenerationChunk(message=AIMessageChunk(content=f"\n[Erreur d'inférence API: {str(e)}]"))


class LLMFactory:
    """Factory for creating LLM instances using HuggingFaceLLM with automatic fallback."""

    ACTIVE_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"

    @classmethod
    async def validate_and_resolve_model(cls) -> str:
        """
        Validate settings.HF_LLM_MODEL and resolve the best available model on Hugging Face Inference API.
        Checks models in order of priority:
        1. settings.HF_LLM_MODEL (if set)
        2. Qwen/Qwen2.5-7B-Instruct
        3. Qwen/Qwen2.5-3B-Instruct
        4. mistralai/Mistral-7B-Instruct-v0.3
        5. HuggingFaceH4/zephyr-7b-beta
        """
        from huggingface_hub import AsyncInferenceClient
        
        candidates = []
        configured_model = settings.HF_LLM_MODEL
        if configured_model and configured_model not in candidates:
            # Clean up default reference to Qwen3 if it's there
            if "Qwen3" not in configured_model:
                candidates.append(configured_model)
                
        # Append priorities in order
        priorities = [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-3B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "HuggingFaceH4/zephyr-7b-beta"
        ]
        for p in priorities:
            if p not in candidates:
                candidates.append(p)
                
        logger.info(f"LLM validation: Configured model in settings is '{configured_model}'")
        logger.info(f"Candidates to test in order: {candidates}")
        
        resolved_model = None
        for model in candidates:
            logger.info(f"Testing model accessibility: '{model}'...")
            try:
                # Use AsyncInferenceClient to test
                client = AsyncInferenceClient(
                    model=model,
                    token=settings.HF_TOKEN if settings.HF_TOKEN else None
                )
                # Test chat completion with 1 token output
                response = await client.chat_completion(
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1
                )
                # If we get here, model is accessible and working!
                resolved_model = model
                logger.info(f"Successfully validated model: '{model}' (model actually loaded & available)")
                break
            except Exception as e:
                logger.warning(f"Model validation failed for '{model}': {e}")
                
        if not resolved_model:
            # Fallback to first priority if everything failed
            resolved_model = "Qwen/Qwen2.5-7B-Instruct"
            logger.error(
                f"All model validation tests failed. Falling back to default: '{resolved_model}'"
            )
        else:
            logger.info(f"Model validation resolved to: '{resolved_model}' (used after fallback checks)")
            
        cls.ACTIVE_MODEL = resolved_model
        return resolved_model

    @staticmethod
    def create_llm(
        temperature: float = 0.7
    ) -> HuggingFaceLLM:
        """Create a HuggingFaceLLM instance."""
        logger.info(f"Creating HuggingFaceLLM model: {LLMFactory.ACTIVE_MODEL} (from active model configuration)")
        return HuggingFaceLLM(
            model_name=LLMFactory.ACTIVE_MODEL,
            hf_token=settings.HF_TOKEN,
            temperature=temperature,
            max_tokens=2048
        )

    @staticmethod
    def create_chat_llm(streaming: bool = True) -> HuggingFaceLLM:
        return LLMFactory.create_llm(temperature=0.7)

    @staticmethod
    def create_quiz_llm() -> HuggingFaceLLM:
        return LLMFactory.create_llm(temperature=0.5)

    @staticmethod
    def create_evaluation_llm() -> HuggingFaceLLM:
        return LLMFactory.create_llm(temperature=0.3)

    @staticmethod
    def create_summary_llm() -> HuggingFaceLLM:
        return LLMFactory.create_llm(temperature=0.5)

    @staticmethod
    def create_translation_llm() -> HuggingFaceLLM:
        return LLMFactory.create_llm(temperature=0.3)