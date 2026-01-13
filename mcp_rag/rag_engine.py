"""RAG engine with FAISS vector search and Ollama embeddings."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import httpx
import numpy as np

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "nomic-embed-text"
SIMILARITY_THRESHOLD = 0.65
RAG_TOP_K = 5


class OllamaError(Exception):
    """Exception for Ollama-related errors."""
    pass


class RAGEngine:
    """RAG engine for document retrieval and search."""

    def __init__(self, ollama_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        """
        Initialize RAG engine.

        Args:
            ollama_url: Ollama server URL
            model: Embedding model name
        """
        self.ollama_url = ollama_url
        self.model = model
        self.index = None
        self.metadata: List[Dict[str, str]] = []  # List of {text, filename}
        self._faiss = None

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
        Get embedding for text using Ollama.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
            except httpx.ConnectError:
                raise OllamaError(f"Cannot connect to Ollama at {self.ollama_url}")
            except httpx.HTTPStatusError as e:
                raise OllamaError(f"Ollama API error: {e.response.status_code}")
            except Exception as e:
                raise OllamaError(f"Embedding error: {e}")

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

        logger.info(f"Generating embeddings for {len(all_chunks)} chunks")

        embeddings = []
        for i, chunk in enumerate(all_chunks):
            try:
                emb = await self.get_embedding(chunk)
                embeddings.append(emb)
                if (i + 1) % 10 == 0:
                    logger.info(f"Embedded {i + 1}/{len(all_chunks)} chunks")
            except Exception as e:
                logger.error(f"Failed to embed chunk {i}: {e}")
                embeddings.append([0.0] * 768)

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

        logger.info(f"Built FAISS index with {len(all_chunks)} chunks")
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
            "file_names": list(unique_files)
        }

    def clear_index(self) -> None:
        """Clear the index."""
        self.index = None
        self.metadata = []
        logger.info("RAG index cleared")
