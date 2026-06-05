"""PostgreSQL pgvector vector store management."""
import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from langchain_core.documents import Document as LangChainDocument
import httpx
import os
import math
import numpy as np

from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.ai.embeddings import EmbeddingsFactory
from app.config import settings

logger = logging.getLogger(__name__)


from huggingface_hub import AsyncInferenceClient

class HuggingFaceReranker:
    """Reranker using Hugging Face Inference API for BAAI/bge-reranker-large (CrossEncoder format)."""
    
    def __init__(self, model_name: str, hf_token: str):
        self.model_name = model_name
        self.hf_token = hf_token
        # Reusable AsyncClient to prevent recreation
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def rerank(self, query: str, docs: List[str]) -> Optional[List[dict]]:
        """
        Rerank documents based on query using Hugging Face CrossEncoder.
        Returns a list of dicts: [{"index": int, "score": float}, ...]
        If API fails, returns None to fallback to vector scores cleanly.
        """
        import time
        import asyncio
        logger.info(
            f"RERANK DEBUG | received {len(docs) if docs is not None else 0} docs"
        )
        if docs is None or len(docs) == 0:
            logger.info(
                "RERANK DEBUG | returning 0 docs"
            )
            return []
            
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        # CrossEncoder expects a list of query-passage pairs
        payload = {
            "inputs": [
                [query, doc]
                for doc in docs
            ]
        }
        logger.info("RERANK PAYLOAD=%s", payload)
        
        retries = 3
        backoff = 1.0
        url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"
        
        for attempt in range(retries):
            start_time = time.time()
            try:
                logger.info(f"Reranking {len(docs)} documents using CrossEncoder model {self.model_name} (attempt {attempt + 1})")
                response = await self.client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                
                duration = (time.time() - start_time) * 1000
                logger.info(
                    f"RERANK Success | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1} | response_time={duration:.2f}ms | status={response.status_code}"
                )
                
                if response.status_code == 503:
                    logger.warning("Hugging Face Reranker is loading (503). Falling back to pgvector distance.")
                    if attempt == retries - 1:
                        return None
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                    
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    if isinstance(data, list):
                        for idx, item in enumerate(data):
                            if isinstance(item, list) and len(item) > 0 and "score" in item[0]:
                                score = float(item[0]["score"])
                            elif isinstance(item, dict) and "score" in item:
                                score = float(item["score"])
                            elif isinstance(item, float) or isinstance(item, int):
                                score = float(item)
                            else:
                                score = 0.0
                            results.append({"index": idx, "score": score})
                        logger.info(
                            f"RERANK DEBUG | returning {len(results)} docs"
                        )
                        return results
                else:
                    logger.warning(f"Reranker API returned status {response.status_code}: {response.text}")
                    if attempt == retries - 1:
                        return None
                    
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, 
                    httpx.ConnectTimeout, asyncio.TimeoutError) as err:
                duration = (time.time() - start_time) * 1000
                logger.warning(
                    f"RERANK API Error | model={self.model_name} | URL={url} | "
                    f"attempt={attempt + 1}/{retries} | error_type={type(err).__name__} | "
                    f"error={str(err)} | duration={duration:.2f}ms"
                )
                if attempt == retries - 1:
                    return None
                await asyncio.sleep(backoff)
                backoff *= 2
                
        return None


def is_noise_chunk(content: str) -> bool:
    """
    Determine if a chunk is noise (table of contents, quasi-empty, too short, repetitive, etc.)
    and should be filtered out from the retrieved RAG context.
    """
    text = content.strip()
    
    # 1. Less than 50 characters
    if len(text) < 50:
        logger.info("Filtering chunk: too short (< 50 chars)")
        return True
        
    # 2. Table of contents / index / page de garde / sommaire detection
    text_lower = text.lower()
    toc_keywords = ["table des matières", "table des matieres", "sommaire", "table of contents", "t.o.c.", "index des matières", "plan du cours", "page de garde"]
    
    # Excessive dots or underscores (points de suite)
    dot_count = text.count(".")
    underscore_count = text.count("_")
    hyphen_count = text.count("-")
    total_fillers = dot_count + underscore_count + hyphen_count
    
    if total_fillers > 12:
        logger.info(f"Filtering chunk: excess filler characters (dots/underscores/hyphens={total_fillers}) indicative of Table of Contents")
        return True

    # Check for title lists / section numbers (e.g. 1.1, 1.2, etc.)
    import re
    section_patterns = re.findall(r'\b\d+(?:\.\d+)+\b', text)
    if len(section_patterns) > 5 and len(text) < 500:
        logger.info(f"Filtering chunk: high density of section numbers ({len(section_patterns)}) indicative of Table of Contents/Index")
        return True

    # Table of contents keywords check combined with numbers
    if any(kw in text_lower for kw in toc_keywords):
        digit_count = sum(1 for c in text if c.isdigit())
        digit_ratio = digit_count / len(text) if len(text) > 0 else 0
        if digit_ratio > 0.08 or total_fillers > 5:
            logger.info("Filtering chunk: Table of Contents keyword + high digit/filler ratio detected")
            return True
            
    # 3. OCR headers/footers or page numbers
    if text_lower.startswith("page ") and len(text) < 80:
        logger.info("Filtering chunk: OCR header/footer page number detected")
        return True
        
    # 4. Text density & Symbol/Alphanumeric ratio
    alnum_chars = [c for c in text if c.isalnum()]
    if not alnum_chars:
        logger.info("Filtering chunk: no alphanumeric characters")
        return True
    
    alnum_ratio = len(alnum_chars) / len(text)
    if alnum_ratio < 0.45:
        logger.info(f"Filtering chunk: mostly symbols/empty content detected (alnum ratio={alnum_ratio:.3f})")
        return True
        
    # 5. Repetitive contents detection
    words = text.split()
    if words:
        unique_words = set(words)
        word_repetition_ratio = len(unique_words) / len(words)
        if word_repetition_ratio < 0.35 and len(words) > 15:
            logger.info(f"Filtering chunk: highly repetitive content detected (ratio={word_repetition_ratio:.3f})")
            return True

    # 6. Title lists/short fragments ratio (lines that are short titles without actual paragraphs)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 3:
        short_lines_count = sum(1 for line in lines if len(line) < 60)
        short_line_ratio = short_lines_count / len(lines)
        if short_line_ratio > 0.75 and len(text) < 600:
            logger.info(f"Filtering chunk: list of titles/headers without actual content paragraphs (ratio={short_line_ratio:.3f})")
            return True
            
    return False


class VectorStoreManager:
    """Manager for PostgreSQL pgvector vector store operations."""
    
    def __init__(self, embeddings=None, reranker=None):
        self.embeddings = embeddings or EmbeddingsFactory.create_embeddings()
        self.reranker = reranker or HuggingFaceReranker(
            model_name=settings.HF_RERANK_MODEL,
            hf_token=settings.HF_TOKEN
        )
    
    async def create_collection(
        self,
        db: AsyncSession,
        document_id: UUID,
        documents: List[str],
        metadatas: Optional[List[dict]] = None
    ) -> int:
        """
        Save document chunks and their embeddings into pgvector.
        
        Args:
            db: Database session
            document_id: Document UUID
            documents: List of text chunks
            metadatas: Optional list of metadata dicts
            
        Returns:
            int: Number of chunks created
        """
        try:
            logger.info(
                f"VECTOR DEBUG | create_collection | document_id={document_id} | "
                f"documents received count={len(documents)}"
            )
            # Generate embeddings in batch
            embeddings = await self.embeddings.aembed_documents(documents)
            
            # Confirm that embeddings are generated and check for zero-vector fallback
            zero_embeddings_count = sum(1 for emb in embeddings if all(val == 0.0 for val in emb))
            logger.info(
                f"VECTOR DEBUG | create_collection | document_id={document_id} | "
                f"embeddings generated count={len(embeddings)} | "
                f"number of zero-fallback embeddings={zero_embeddings_count}"
            )
            
            # Create DocumentChunk objects
            inserted_count = 0
            for idx, (text, emb) in enumerate(zip(documents, embeddings)):
                if emb is None:
                    raise ValueError(f"Embedding is None for chunk index {idx}")
                
                emb_arr = np.array(emb)
                norm_val = float(np.linalg.norm(emb_arr))
                zeros_count = int(np.sum(emb_arr == 0))
                
                logger.info(
                    "CHUNK EMBEDDING | chunk=%s | dim=%s | norm=%f | zeros=%s",
                    idx,
                    len(emb),
                    norm_val,
                    zeros_count
                )
                
                if norm_val == 0 or zeros_count == len(emb) or all(v == 0 for v in emb):
                    raise ValueError(f"Embedding is invalid (all zeros or norm is 0) for chunk index {idx}")
                
                meta = metadatas[idx] if metadatas is not None and idx < len(metadatas) else {}
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=idx,
                    content=text,
                    embedding=emb,
                    page_number=meta.get("page_number")
                )
                db.add(chunk)
                inserted_count += 1
                
            logger.info(
                f"VECTOR DEBUG | create_collection | document_id={document_id} | "
                f"chunks inserted count={inserted_count} | committing..."
            )
            await db.commit()
            logger.info(
                f"VECTOR DEBUG | create_collection | document_id={document_id} | commit successful!"
            )
            
            # Post-commit verification query
            from sqlalchemy import func
            count_stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
            count_res = await db.execute(count_stmt)
            db_count = count_res.scalar() or 0
            logger.info(
                f"VECTOR DEBUG | Verification after commit | document_id={document_id} | "
                f"SELECT COUNT(*) result={db_count}"
            )
            
            return len(documents)
        except Exception as e:
            logger.exception(
                f"VECTOR DEBUG | create_collection | document_id={document_id} | "
                f"commit failed! Error: {e}"
            )
            await db.rollback()
            raise
    
    async def similarity_search(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        k: int = 5
    ) -> List[LangChainDocument]:
        """
        Perform similarity search on document chunks using Cosine Distance and CrossEncoder Reranker.
        
        Args:
            db: Database session
            document_id: Document UUID
            query: Search query
            k: Number of results to return
            
        Returns:
            list: List of LangChain Document objects
        """
        try:
            logger.info(
                f"SIMILARITY SEARCH DEBUG | Entry | document_id received={document_id} | "
                f"query='{query}'"
            )
            
            # Query Document to get filename
            doc_stmt = select(Document).where(Document.id == document_id)
            doc_res = await db.execute(doc_stmt)
            doc_obj = doc_res.scalar_one_or_none()
            doc_name = os.path.basename(doc_obj.filename) if doc_obj else "Document"

            import time
            from app.services.observability_service import AIObservabilityService

            query_vector = None
            emb_latency = 0.0
            try:
                start_emb = time.time()
                query_vector = await self.embeddings.aembed_query(query)
                emb_latency = (time.time() - start_emb) * 1000
                logger.info(f"SIMILARITY SEARCH DEBUG | query embedding dim={len(query_vector)}")
                
                # Log embedding request
                try:
                    await AIObservabilityService.log_embedding_request(
                        db=db,
                        model=settings.HF_EMBEDDING_MODEL,
                        input_texts_count=1,
                        total_tokens=len(query.split()),
                        latency_ms=emb_latency,
                        status="success"
                    )
                except Exception as obs_err:
                    logger.exception(f"Non-blocking observability error (embedding): {obs_err}")
            except Exception as e:
                logger.warning(
                    f"SIMILARITY SEARCH | Embedding generation failed with {type(e).__name__}: {e}. "
                    f"Falling back to SQL ILIKE search to preserve service uptime."
                )
                query_vector = None

            if query_vector is None:
                logger.info("SIMILARITY SEARCH | Performing SQL ILIKE fallback search because embeddings are unavailable.")
                words = [w.strip() for w in query.split() if len(w.strip()) > 3]
                if not words:
                    words = [query]
                from sqlalchemy import or_
                conditions = [DocumentChunk.content.ilike(f"%{w}%") for w in words]
                stmt = (
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_id == document_id,
                        or_(*conditions)
                    )
                    .limit(k)
                )
                result = await db.execute(stmt)
                fallback_chunks = result.scalars().all()
                logger.info(f"SIMILARITY SEARCH | SQL ILIKE fallback search returned {len(fallback_chunks)} chunks.")
                
                return [
                    LangChainDocument(
                        page_content=chunk.content,
                        metadata={
                            "chunk_index": chunk.chunk_index,
                            "document_id": str(document_id),
                            "document_name": doc_name,
                            "page": chunk.page_number,
                            "score": 0.85,
                            "content": chunk.content
                        }
                    )
                    for chunk in fallback_chunks
                ]
            
            # Select DocumentChunk along with cosine distance expression
            distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)
            stmt = (
                select(DocumentChunk, distance_expr)
                .where(DocumentChunk.document_id == document_id)
                .order_by(distance_expr)
                .limit(k * 2) # Get double chunks to allow reranking room
            )
            
            # Log final SQL Query
            try:
                logger.info(f"SIMILARITY SEARCH DEBUG | final SQL query: {stmt}")
            except Exception as sql_err:
                logger.debug(f"Could not compile SQL query for logging: {sql_err}")
            
            result = await db.execute(stmt)
            rows = result.all()
            
            logger.info(f"SIMILARITY SEARCH DEBUG | total chunks found before filtering={len(rows) if rows is not None else 0}")
            
            if rows is not None and len(rows) > 0:
                logger.info(
                    f"SIMILARITY SEARCH DEBUG | Raw chunk IDs: {[str(row[0].id) for row in rows]}"
                )
            
            # Process results if we found chunks
            chunks = []
            scores = {}
            if rows is not None and len(rows) > 0:
                # Extract chunks and compute initial similarity scores (1 - distance)
                chunks = [row[0] for row in rows]
                # Handle potential NaN or math issues with cosine distance (e.g. zero vectors)
                for row in rows:
                    dist_val = row[1]
                    # Check if distance is NaN (float comparison with self is False for NaN)
                    if dist_val != dist_val or dist_val is None:
                        scores[row[0].id] = 0.0
                    else:
                        scores[row[0].id] = max(0.0, 1.0 - float(dist_val))
                
                # Apply Hugging Face Reranking if available
                reranked = False
                if settings.HF_RERANK_MODEL:
                    try:
                        start_rerank = time.time()
                        rerank_results = await self.reranker.rerank(
                            query=query,
                            docs=[c.content for c in chunks]
                        )
                        
                        if rerank_results is not None and len(rerank_results) > 0:
                            rerank_latency = (time.time() - start_rerank) * 1000
                            # Log reranking request
                            try:
                                await AIObservabilityService.log_reranking_request(
                                    db=db,
                                    model=settings.HF_RERANK_MODEL,
                                    documents_count=len(chunks),
                                    latency_ms=rerank_latency,
                                    status="success"
                                )
                            except Exception as obs_err:
                                logger.exception(f"Non-blocking observability error (reranking): {obs_err}")
                            
                            # Handle both formats: list of dicts (index/score) or list of tuples (doc/score)
                            first_item = rerank_results[0]
                            if isinstance(first_item, tuple):
                                final_chunks = []
                                for doc_content, score in rerank_results:
                                    for chunk in chunks:
                                        if chunk.content == doc_content:
                                            scores[chunk.id] = float(score)
                                            final_chunks.append(chunk)
                                            break
                                chunks = final_chunks
                            else:
                                sorted_items = sorted(rerank_results, key=lambda x: x["score"], reverse=True)
                                final_chunks = []
                                for item in sorted_items:
                                    chunk = chunks[item["index"]]
                                    scores[chunk.id] = float(item["score"])
                                    final_chunks.append(chunk)
                                chunks = final_chunks
                            
                            reranked = True
                            logger.info(f"SIMILARITY SEARCH DEBUG | Reranking completed for query: '{query}'")
                    except Exception as rerank_err:
                        logger.exception("Error calling Reranker: falling back to vector distance")
                
                # Apply relevance threshold and filter noise chunks
                MIN_RELEVANCE_SCORE = 0.80
                filtered_chunks = []
                for chunk in chunks:
                    score = scores[chunk.id]
                    
                    # Check for invalid embedding and extract stats
                    emb_val = chunk.embedding
                    if emb_val is not None:
                        dim = len(emb_val)
                        l2_norm = float(np.linalg.norm(emb_val))
                        zero_count = int(np.sum(emb_val == 0.0))
                        has_nan = bool(np.any(np.isnan(emb_val)))
                        
                        logger.info(
                            f"SIMILARITY SEARCH DEBUG | Evaluating chunk {chunk.id} (page={chunk.page_number}) | score={score:.3f} | "
                            f"dimension={dim} | L2 norm={l2_norm:.6f} | zeros={zero_count} | nan_present={has_nan}"
                        )
                        
                        is_null_vector = (zero_count == dim)
                        is_short = (dim < 100)
                    else:
                        logger.warning(f"SIMILARITY SEARCH DEBUG | Evaluating chunk {chunk.id} (page={chunk.page_number}) | score={score:.3f} | embedding is None!")
                        is_null_vector = True
                        has_nan = False
                        is_short = True
                    
                    if is_null_vector or has_nan or is_short:
                        reasons = []
                        if is_null_vector: reasons.append("embedding is all zeros (null vector)")
                        if has_nan: reasons.append("embedding contains NaN values")
                        if is_short: reasons.append("embedding dimension is too short")
                        logger.info(
                            f"SIMILARITY SEARCH DEBUG | Rejection | Chunk {chunk.id} (page={chunk.page_number}) | "
                            f"Reason: {', '.join(reasons)}"
                        )
                        continue
                    
                    if score < MIN_RELEVANCE_SCORE:
                        logger.info(
                            f"SIMILARITY SEARCH DEBUG | Rejection | Chunk {chunk.id} (page={chunk.page_number}) | "
                            f"Reason: score {score:.3f} is below threshold {MIN_RELEVANCE_SCORE}"
                        )
                        continue
                    if is_noise_chunk(chunk.content):
                        logger.info(
                            f"SIMILARITY SEARCH DEBUG | Rejection | Chunk {chunk.id} (page={chunk.page_number}) | "
                            f"Reason: noise chunk filter is_noise_chunk() returned True"
                        )
                        continue
                    
                    filtered_chunks.append(chunk)
                
                # Slice to top k
                chunks = filtered_chunks[:k]
            
            logger.info(f"SIMILARITY SEARCH DEBUG | results returned count={len(chunks) if chunks is not None else 0}")
            
            if chunks is not None and len(chunks) > 0:
                logger.info(
                    f"SIMILARITY SEARCH DEBUG | Final chunk IDs: {[str(c.id) for c in chunks]}"
                )
                # Log top 10 best chunks
                for idx, chunk in enumerate(chunks[:10]):
                    score = scores.get(chunk.id, 0.0)
                    logger.info(
                        f"SIMILARITY SEARCH DEBUG | Final Chunk score={score:.3f} page={chunk.page_number} preview={chunk.content[:120]}"
                    )
            
            if not chunks:
                logger.info("SIMILARITY SEARCH | No chunks retained from pgvector. Performing SQL ILIKE fallback search.")
                words = [w.strip() for w in query.split() if len(w.strip()) > 3]
                if not words:
                    words = [query]
                from sqlalchemy import or_
                conditions = [DocumentChunk.content.ilike(f"%{w}%") for w in words]
                stmt = (
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_id == document_id,
                        or_(*conditions)
                    )
                    .limit(k)
                )
                result = await db.execute(stmt)
                fallback_chunks = result.scalars().all()
                logger.info(f"SIMILARITY SEARCH | SQL ILIKE fallback search returned {len(fallback_chunks)} chunks.")
                
                return [
                    LangChainDocument(
                        page_content=chunk.content,
                        metadata={
                            "chunk_index": chunk.chunk_index,
                            "document_id": str(document_id),
                            "document_name": doc_name,
                            "page": chunk.page_number,
                            "score": 0.85,
                            "content": chunk.content
                        }
                    )
                    for chunk in fallback_chunks
                ]
                
            return [
                LangChainDocument(
                    page_content=chunk.content,
                    metadata={
                        "chunk_index": chunk.chunk_index,
                        "document_id": str(document_id),
                        "document_name": doc_name,
                        "page": chunk.page_number,
                        "score": round(scores.get(chunk.id, 0.0), 3),
                        "content": chunk.content
                    }
                )
                for chunk in chunks
            ]
        except Exception as e:
            logger.exception(f"Error performing similarity search: {e}")
            return []
    
    async def delete_collection(self, db: AsyncSession, document_id: UUID) -> bool:
        """
        Delete all chunks for a document.
        
        Args:
            db: Database session
            document_id: Document UUID
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            await db.commit()
            logger.info(f"Deleted chunks for document {document_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting chunks: {e}")
            await db.rollback()
            return False
    
    async def get_random_chunks(
        self,
        db: AsyncSession,
        document_id: UUID,
        n: int = 10
    ) -> List[str]:
        """
        Get random chunks from document for generating quiz questions.
        
        Args:
            db: Database session
            document_id: Document UUID
            n: Number of chunks to retrieve
            
        Returns:
            list: List of text chunks
        """
        try:
            stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(func.random())
                .limit(n)
            )
            result = await db.execute(stmt)
            chunks = result.scalars().all()
            return [c.content for c in chunks]
        except Exception as e:
            logger.exception(f"Error getting random chunks: {e}")
            return []


# Global vector store manager instance
vector_store_manager = VectorStoreManager()
