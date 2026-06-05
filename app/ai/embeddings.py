"""Embeddings factory for creating Hugging Face embedding model instances."""
import logging
import math
import time
import asyncio
import httpx
from typing import Any, List
from langchain_core.embeddings import Embeddings
from huggingface_hub import AsyncInferenceClient, InferenceClient

from app.config import settings

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddings(Embeddings):
    """Custom LangChain Embeddings implementation for Hugging Face Inference API."""

    def __init__(self, model_name: str, hf_token: str):
        self.model_name = model_name
        self.hf_token = hf_token
        self.client = InferenceClient(
            model=model_name,
            token=hf_token if hf_token else None
        )
        self.async_client = AsyncInferenceClient(
            model=model_name,
            token=hf_token if hf_token else None
        )

    async def _request_with_retry_and_timeout(self, func, *args, **kwargs) -> Any:
        """Helper to run async HuggingFace hub calls with timeout and retries."""
        retries = 3
        timeout = 60.0
        backoff = 1.0
        url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"

        for attempt in range(retries):
            start_time = time.time()
            try:
                # Wrap the function call in wait_for to enforce 60s timeout
                res = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                duration = (time.time() - start_time) * 1000
                logger.info(
                    f"HF API Success | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1} | response_time={duration:.2f}ms"
                )
                return res
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, 
                    httpx.ConnectTimeout, asyncio.TimeoutError) as err:
                duration = (time.time() - start_time) * 1000
                logger.warning(
                    f"HF API Error | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1}/{retries} | error_type={type(err).__name__} | "
                    f"error={str(err)} | duration={duration:.2f}ms"
                )
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

    def _request_sync_with_retry_and_timeout(self, func, *args, **kwargs) -> Any:
        """Helper to run sync HuggingFace hub calls with timeout and retries."""
        retries = 3
        backoff = 1.0
        url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"

        for attempt in range(retries):
            start_time = time.time()
            try:
                res = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                logger.info(
                    f"HF API Success (Sync) | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1} | response_time={duration:.2f}ms"
                )
                return res
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, 
                    httpx.ConnectTimeout) as err:
                duration = (time.time() - start_time) * 1000
                logger.warning(
                    f"HF API Error (Sync) | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1}/{retries} | error_type={type(err).__name__} | "
                    f"error={str(err)} | duration={duration:.2f}ms"
                )
                if attempt == retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2

    def _to_1d_list(self, val: Any) -> List[float]:
        """Convert any list/numpy output format from HF feature extraction into a 1D float list."""
        if hasattr(val, "tolist"):
            val = val.tolist()
        # Recursively extract first element if nested list
        while isinstance(val, list) and len(val) > 0 and isinstance(val[0], list):
            val = val[0]
        return [float(x) for x in val]

    def _log_and_validate(self, embedding_any: Any, text: str) -> List[float]:
        """Convert, compute statistics, log and strictly validate embedding vector."""
        embedding = self._to_1d_list(embedding_any)
        dim = len(embedding)
        
        # Calculate stats
        zero_count = sum(1 for x in embedding if x == 0.0)
        nan_present = any(math.isnan(x) for x in embedding)
        
        if dim > 0:
            mean_val = sum(embedding) / dim
            min_val = min(embedding)
            max_val = max(embedding)
            l2_norm = math.sqrt(sum(x * x for x in embedding))
        else:
            mean_val = 0.0
            min_val = 0.0
            max_val = 0.0
            l2_norm = 0.0
            
        logger.info(
            f"Embedding Stats | text_length={len(text)} | dimension={dim} | L2 norm={l2_norm:.6f} | "
            f"mean={mean_val:.6f} | min={min_val:.6f} | max={max_val:.6f} | "
            f"zeros={zero_count} | nan_present={nan_present}"
        )
        
        # Strict validations
        if dim < 100:
            raise ValueError(f"Embedding dimension is too short: {dim} (expected >= 100)")
            
        if all(v == 0.0 for v in embedding):
            raise ValueError("Embedding is invalid: all values are 0.0 (null vector)")
            
        if nan_present:
            raise ValueError("Embedding contains NaN values")
            
        return embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed list of texts (passages)."""
        prefixed = [f"passage: {t}" for t in texts]
        embeddings = []
        for orig_text, text in zip(texts, prefixed):
            try:
                emb = self._request_sync_with_retry_and_timeout(
                    self.client.feature_extraction,
                    text
                )
                validated = self._log_and_validate(emb, orig_text)
                embeddings.append(validated)
            except Exception as e:
                logger.error(f"Error calling Hugging Face embed_documents for text: '{orig_text[:50]}...': {e}")
                raise
        return embeddings

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed list of texts asynchronously."""
        prefixed = [f"passage: {t}" for t in texts]
        embeddings = []
        for orig_text, text in zip(texts, prefixed):
            try:
                emb = await self._request_with_retry_and_timeout(
                    self.async_client.feature_extraction,
                    text
                )
                validated = self._log_and_validate(emb, orig_text)
                embeddings.append(validated)
            except Exception as e:
                logger.error(f"Error calling Hugging Face aembed_documents for text: '{orig_text[:50]}...': {e}")
                raise
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        prefixed = f"query: {text}"
        try:
            emb = self._request_sync_with_retry_and_timeout(
                self.client.feature_extraction,
                prefixed
            )
            return self._log_and_validate(emb, text)
        except Exception as e:
            logger.error(f"Error calling Hugging Face embed_query for text: '{text[:50]}...': {e}")
            raise

    async def aembed_query(self, text: str) -> List[float]:
        """Embed a single query asynchronously."""
        prefixed = f"query: {text}"
        try:
            emb = await self._request_with_retry_and_timeout(
                self.async_client.feature_extraction,
                prefixed
            )
            return self._log_and_validate(emb, text)
        except Exception as e:
            logger.error(f"Error calling Hugging Face aembed_query for text: '{text[:50]}...': {e}")
            raise


class EmbeddingsFactory:
    """Factory for creating embedding model instances."""

    @staticmethod
    def create_embeddings() -> HuggingFaceEmbeddings:
        """Create a HuggingFaceEmbeddings instance."""
        logger.info(f"Creating HuggingFaceEmbeddings: {settings.HF_EMBEDDING_MODEL}")
        return HuggingFaceEmbeddings(
            model_name=settings.HF_EMBEDDING_MODEL,
            hf_token=settings.HF_TOKEN
        )