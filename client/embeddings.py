"""
Embeddings generation module for processing markdown files and creating embeddings using Ollama.
"""

import os
import json
import logging
from typing import List, Dict
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Exception raised when Ollama API fails."""
    pass


def chunk_by_paragraphs(text: str) -> List[str]:
    """
    Split text into chunks by paragraphs (separated by double newlines).

    Args:
        text: The input text to chunk

    Returns:
        List of paragraph chunks with whitespace stripped
    """
    # Split by double newlines (paragraph separator)
    chunks = text.split('\n\n')

    # Filter out empty chunks and strip whitespace
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

    return chunks


async def get_ollama_embedding(text: str, ollama_url: str, model: str = "nomic-embed-text") -> List[float]:
    """
    Get embedding vector for text from Ollama API.

    Args:
        text: The text to embed
        ollama_url: Base URL for Ollama API (e.g., "http://localhost:11434")
        model: The embedding model to use

    Returns:
        Embedding vector as list of floats

    Raises:
        OllamaError: If API request fails
    """
    endpoint = f"{ollama_url}/api/embeddings"

    payload = {
        "model": model,
        "prompt": text
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()

            result = response.json()
            return result.get("embedding", [])

    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama API HTTP error: {e.response.status_code} - {e.response.text}")
        raise OllamaError(f"HTTP {e.response.status_code}: {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Ollama API request error: {str(e)}")
        raise OllamaError(f"Failed to connect to Ollama: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama API: {str(e)}")
        raise OllamaError(f"Unexpected error: {str(e)}")


async def process_docs_folder(docs_path: str, ollama_url: str, model: str = "nomic-embed-text") -> List[Dict]:
    """
    Process all markdown files in docs folder and generate embeddings.

    Args:
        docs_path: Path to docs directory
        ollama_url: Base URL for Ollama API
        model: The embedding model to use

    Returns:
        List of dictionaries with 'text' and 'embedding' keys

    Raises:
        FileNotFoundError: If no markdown files found
        OllamaError: If Ollama API fails
    """
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"Directory not found: {docs_path}")

    # Find all .md files in top-level docs directory (no recursion)
    md_files = [f for f in os.listdir(docs_path) if f.endswith('.md')]

    if not md_files:
        raise FileNotFoundError(f"No markdown files found in {docs_path}")

    logger.info(f"Found {len(md_files)} markdown files in {docs_path}")

    all_embeddings = []

    for filename in md_files:
        file_path = os.path.join(docs_path, filename)

        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Chunk by paragraphs
        chunks = chunk_by_paragraphs(content)
        logger.info(f"Processing {filename}: {len(chunks)} chunks")

        # Process each chunk
        for idx, chunk in enumerate(chunks, 1):
            # Log first 50 characters of chunk
            preview = chunk[:50].replace('\n', ' ')
            logger.debug(f"Chunk {idx}/{len(chunks)}: {preview}...")

            try:
                # Get embedding from Ollama
                embedding = await get_ollama_embedding(chunk, ollama_url, model)

                # Add to results
                all_embeddings.append({
                    "text": chunk,
                    "embedding": embedding
                })

            except OllamaError as e:
                logger.error(f"Failed to get embedding for chunk {idx} in {filename}: {str(e)}")
                raise

    logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
    return all_embeddings


def save_embeddings_json(embeddings: List[Dict], output_dir: str) -> str:
    """
    Save embeddings to JSON file with timestamp.

    Args:
        embeddings: List of embedding dictionaries
        output_dir: Directory to save the file

    Returns:
        Full path to saved JSON file
    """
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"embeddings_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    # Save to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(embeddings, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved embeddings to {filepath}")
    return filepath
