"""RAG engine with FAISS vector search and OpenRouter embeddings."""

import json
import logging
import os
from typing import Dict, List, Tuple
import httpx
import numpy as np

logger = logging.getLogger(__name__)

# OpenRouter embeddings configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_EMBEDDING_MODEL = "google/gemini-embedding-001"

SIMILARITY_THRESHOLD = 0.65
RAG_TOP_K = 5


class EmbeddingError(Exception):
    """Exception for embedding-related errors."""
    pass


class RAGEngine:
    """RAG engine for document retrieval and search using OpenRouter embeddings."""

    def __init__(self):
        """Initialize RAG engine with OpenRouter embeddings."""
        self.api_key = OPENROUTER_API_KEY
        self.embeddings_url = OPENROUTER_EMBEDDINGS_URL
        self.model = OPENROUTER_EMBEDDING_MODEL
        self.index = None
        self.metadata: List[Dict[str, str]] = []  # List of {text, filename}
        self._faiss = None
        self._embedding_dimension = None

    def _get_faiss(self):
        """Lazy load FAISS library."""
        if self._faiss is None:
            try:
                import faiss
                self._faiss = faiss
            except ImportError:
                raise RuntimeError("FAISS not installed. Run: pip install faiss-cpu")
        return self._faiss

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using OpenRouter API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if not self.api_key:
            raise EmbeddingError("OPENROUTER_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": text
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.embeddings_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                # OpenRouter returns embeddings in data[0].embedding format
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0].get("embedding", [])
                    if embedding:
                        # Cache dimension for later use
                        if self._embedding_dimension is None:
                            self._embedding_dimension = len(embedding)
                            logger.info(f"Embedding dimension: {self._embedding_dimension}")
                        return embedding

                raise EmbeddingError(f"Invalid embedding response: {data}")

            except httpx.ConnectError:
                raise EmbeddingError(f"Cannot connect to OpenRouter API")
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                logger.error(f"OpenRouter embedding error: {e.response.status_code} - {error_text}")
                raise EmbeddingError(f"OpenRouter API error: {e.response.status_code}")
            except Exception as e:
                raise EmbeddingError(f"Embedding error: {e}")

    def chunk_document(self, content: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split document into chunks by paragraphs.

        Args:
            content: Document content
            chunk_size: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of chunks
        """
        paragraphs = content.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [c for c in chunks if len(c) > 20]

    async def build_index(self, documents: List[Dict[str, str]]) -> int:
        """
        Build FAISS index from documents.

        Args:
            documents: List of {filename, content} dicts

        Returns:
            Number of indexed chunks
        """
        faiss = self._get_faiss()

        all_chunks = []
        all_metadata = []

        for doc in documents:
            chunks = self.chunk_document(doc["content"])
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadata.append({
                    "text": chunk,
                    "filename": doc["filename"]
                })

        if not all_chunks:
            logger.warning("No chunks to index")
            return 0

        logger.info(f"Generating embeddings for {len(all_chunks)} chunks using OpenRouter")

        embeddings = []
        for i, chunk in enumerate(all_chunks):
            try:
                emb = await self.get_embedding(chunk)
                embeddings.append(emb)
                if (i + 1) % 10 == 0:
                    logger.info(f"Embedded {i + 1}/{len(all_chunks)} chunks")
            except Exception as e:
                logger.error(f"Failed to embed chunk {i}: {e}")
                # Use zero vector as fallback
                dim = self._embedding_dimension or 768
                embeddings.append([0.0] * dim)

        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        norms[norms == 0] = 1
        embeddings_array = embeddings_array / norms

        # Create FAISS index
        dimension = embeddings_array.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings_array)
        self.metadata = all_metadata

        logger.info(f"Built FAISS index with {len(all_chunks)} chunks (dim={dimension})")
        return len(all_chunks)

    async def search(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> List[Tuple[str, float, str]]:
        """
        Search for similar chunks.

        Args:
            query: Search query
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (chunk_text, score, filename) tuples
        """
        if self.index is None or not self.metadata:
            logger.warning("No index built, returning empty results")
            return []

        query_embedding = await self.get_embedding(query)
        query_array = np.array([query_embedding], dtype=np.float32)

        # Normalize query
        norm = np.linalg.norm(query_array)
        if norm > 0:
            query_array = query_array / norm

        # Search
        scores, indices = self.index.search(query_array, min(top_k * 2, len(self.metadata)))

        # Log top scores for debugging
        top_scores = [f"{s:.3f}" for s in scores[0][:5] if s > 0]
        logger.info(f"Top similarity scores: {top_scores}, threshold: {threshold}")

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            if score >= threshold:
                chunk_data = self.metadata[idx]
                results.append((chunk_data["text"], float(score), chunk_data["filename"]))

        results = results[:top_k]
        logger.info(f"Found {len(results)} relevant chunks for query")
        return results

    def get_index_stats(self) -> Dict:
        """Get statistics about the index."""
        if self.index is None:
            return {"indexed": False, "chunks": 0, "files": 0}

        unique_files = set(m["filename"] for m in self.metadata)
        return {
            "indexed": True,
            "chunks": len(self.metadata),
            "files": len(unique_files),
            "file_names": list(unique_files),
            "embedding_model": self.model
        }

    def clear_index(self) -> None:
        """Clear the index."""
        self.index = None
        self.metadata = []
        logger.info("RAG index cleared")
