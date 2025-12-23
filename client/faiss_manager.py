"""
FAISS Manager

Manages FAISS vector index for RAG (Retrieval Augmented Generation).
Uses IndexFlatIP with normalized vectors for cosine similarity search.
"""

import json
import logging
import faiss
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class FaissManager:
    """Manages FAISS index for semantic search"""

    def __init__(
        self,
        index_file: str = "faiss_index.bin",
        metadata_file: str = "faiss_metadata.json"
    ):
        """
        Initialize FAISS manager

        Args:
            index_file: Path to FAISS index binary file
            metadata_file: Path to JSON file with chunk texts
        """
        self.index_path = Path(__file__).parent / index_file
        self.metadata_path = Path(__file__).parent / metadata_file
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[dict] = []

    def normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """
        Normalize vectors to unit length (L2 normalization)

        This converts inner product to cosine similarity:
        cos(a, b) = (a · b) / (||a|| * ||b||)
        When ||a|| = ||b|| = 1, cos(a, b) = a · b

        Args:
            vectors: Array of shape (n_vectors, dimension)

        Returns:
            Normalized vectors of same shape
        """
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    def create_index(self, embeddings: List[List[float]], texts: List[str]) -> None:
        """
        Create FAISS index from embeddings and save to disk

        Args:
            embeddings: List of embedding vectors
            texts: List of corresponding chunk texts

        Raises:
            ValueError: If embeddings and texts have different lengths
        """
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Embeddings count ({len(embeddings)}) must match texts count ({len(texts)})"
            )

        if len(embeddings) == 0:
            raise ValueError("Cannot create index from empty embeddings")

        # Convert to numpy array
        vectors = np.array(embeddings, dtype=np.float32)
        dimension = vectors.shape[1]

        logger.info(f"Creating FAISS index with {len(embeddings)} vectors, dimension={dimension}")

        # Normalize vectors for cosine similarity
        vectors_normalized = self.normalize_vectors(vectors)

        # Create IndexFlatIP (Inner Product)
        # With normalized vectors, inner product = cosine similarity
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors_normalized)

        # Save index
        faiss.write_index(index, str(self.index_path))
        logger.info(f"Saved FAISS index to {self.index_path}")

        # Save metadata
        metadata = [{"text": text} for text in texts]
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved metadata to {self.metadata_path}")

        # Keep in memory
        self.index = index
        self.metadata = metadata

        logger.info(f"Created FAISS index with {len(texts)} chunks")

    def load_index(self) -> Tuple[faiss.IndexFlatIP, List[dict]]:
        """
        Load FAISS index and metadata from disk

        Returns:
            Tuple of (index, metadata)

        Raises:
            FileNotFoundError: If index or metadata file doesn't exist
        """
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {self.index_path}")

        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found at {self.metadata_path}")

        # Load index
        index = faiss.read_index(str(self.index_path))
        logger.info(f"Loaded FAISS index from {self.index_path}")

        # Load metadata
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logger.info(f"Loaded {len(metadata)} metadata entries")

        # Keep in memory
        self.index = index
        self.metadata = metadata

        return index, metadata

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 3
    ) -> List[str]:
        """
        Search for top-k most similar chunks

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of chunk texts ordered by similarity (most similar first)

        Raises:
            RuntimeError: If index not loaded
        """
        # Load index if not in memory
        if self.index is None or not self.metadata:
            try:
                self.load_index()
            except FileNotFoundError as e:
                raise RuntimeError(f"FAISS index not available: {e}")

        # Convert to numpy and normalize
        query_vector = np.array([query_embedding], dtype=np.float32)
        query_vector_normalized = self.normalize_vectors(query_vector)

        # Search index
        # Returns: distances (cosine similarities), indices
        distances, indices = self.index.search(query_vector_normalized, top_k)

        # Extract texts
        results = []
        for i, (idx, score) in enumerate(zip(indices[0], distances[0])):
            if idx < len(self.metadata):
                text = self.metadata[idx]["text"]
                results.append(text)
                logger.debug(
                    f"Chunk {i+1}/{top_k}: score={score:.4f}, "
                    f"text={text[:50]}..."
                )

        logger.info(f"Retrieved {len(results)} similar chunks (top-{top_k})")
        return results

    def index_exists(self) -> bool:
        """
        Check if FAISS index and metadata files exist

        Returns:
            True if both files exist, False otherwise
        """
        return self.index_path.exists() and self.metadata_path.exists()
