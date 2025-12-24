"""
Reranker Module

Provides cross-encoder reranking using BGE reranker model via sentence-transformers.
Reranks chunks retrieved from FAISS to improve relevance ordering.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class OllamaReranker:
    """
    Cross-encoder reranker using BGE reranker model.

    Uses sentence-transformers library with bge-reranker-base model
    to compute relevance scores for query-document pairs.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        Initialize reranker

        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        self.model_name = model_name
        self.model = None
        self._initialized = False

    def _lazy_init(self):
        """
        Lazy initialization of the model.
        Only loads when first needed to avoid startup overhead.
        """
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {self.model_name}")
            self.model = CrossEncoder(self.model_name, max_length=512)
            self._initialized = True
            logger.info(f"Reranker model loaded successfully")
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise RuntimeError(
                "sentence-transformers required for reranking. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to load reranker model: {e}")

    async def rerank(
        self,
        query: str,
        chunks: List[str],
        top_k: int = 3
    ) -> List[str]:
        """
        Rerank chunks using cross-encoder model

        Args:
            query: User query
            chunks: List of text chunks to rerank
            top_k: Number of top chunks to return after reranking

        Returns:
            List of reranked chunks (top_k most relevant)

        Raises:
            RuntimeError: If model initialization fails
        """
        if not chunks:
            logger.warning("No chunks provided for reranking")
            return []

        # Lazy load model on first use
        self._lazy_init()

        if self.model is None:
            logger.error("Reranker model not available")
            raise RuntimeError("Reranker model not initialized")

        try:
            # Create query-document pairs
            pairs = [[query, chunk] for chunk in chunks]

            logger.info(f"\n{'─'*60}")
            logger.info(f"RERANKER: Starting cross-encoder scoring")
            logger.info(f"{'─'*60}")
            logger.info(f"RERANKER: Query: '{query}'")
            logger.info(f"RERANKER: Number of chunks to rerank: {len(chunks)}")
            logger.info(f"RERANKER: Model: {self.model_name}")
            logger.info(f"RERANKER: Creating {len(pairs)} query-document pairs...")

            logger.info(f"\nRERANKER: Input chunks (before reranking):")
            for i, chunk in enumerate(chunks, 1):
                chunk_preview = chunk[:100].replace('\n', ' ')
                logger.info(f"  Input[{i}]: {chunk_preview}...")

            # Predict relevance scores
            logger.info(f"\nRERANKER: Computing cross-encoder scores...")
            scores = self.model.predict(pairs)
            logger.info(f"RERANKER: ✓ Scores computed successfully")

            # Create (chunk, score) tuples and sort by score descending
            chunk_scores = list(zip(chunks, scores))
            chunk_scores.sort(key=lambda x: x[1], reverse=True)

            # Log all scores (before and after sorting)
            logger.info(f"\nRERANKER: Cross-encoder relevance scores (sorted by score):")
            logger.info(f"{'─'*60}")
            for i, (chunk, score) in enumerate(chunk_scores, 1):
                chunk_preview = chunk[:100].replace('\n', ' ')
                logger.info(f"\n  Rank {i}/{len(chunk_scores)}:")
                logger.info(f"    Score: {score:.6f}")
                logger.info(f"    Chunk Length: {len(chunk)} chars")
                logger.info(f"    Chunk Preview: \"{chunk_preview}...\"")

            # Extract top-k chunks
            reranked_chunks = [chunk for chunk, score in chunk_scores[:top_k]]

            logger.info(f"\n{'─'*60}")
            logger.info(f"RERANKER: Final selection (top-{top_k}):")
            logger.info(f"{'─'*60}")
            for i, (chunk, score) in enumerate(chunk_scores[:top_k], 1):
                chunk_preview = chunk[:150].replace('\n', ' ')
                logger.info(f"\n  Selected[{i}]:")
                logger.info(f"    Relevance Score: {score:.6f}")
                logger.info(f"    Chunk Text: \"{chunk_preview}...\"")

            logger.info(f"\n{'─'*60}")
            logger.info(f"RERANKER: ✓ Reranking complete")
            logger.info(f"RERANKER: Input: {len(chunks)} chunks")
            logger.info(f"RERANKER: Output: {len(reranked_chunks)} chunks")
            logger.info(f"RERANKER: Score range: [{min(scores):.6f}, {max(scores):.6f}]")
            logger.info(f"RERANKER: Mean score: {sum(scores)/len(scores):.6f}")
            logger.info(f"RERANKER: Top-{top_k} score threshold: {chunk_scores[top_k-1][1]:.6f}")
            logger.info(f"{'─'*60}\n")

            return reranked_chunks

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # Fallback: return original chunks (truncated to top_k)
            logger.warning("Falling back to original chunk order")
            return chunks[:top_k]
