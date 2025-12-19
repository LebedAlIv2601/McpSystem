"""API Ninjas Facts API integration."""

import os
import httpx
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from client/.env
env_path = Path(__file__).parent.parent / "client" / ".env"
load_dotenv(dotenv_path=env_path)

FACTS_API_BASE_URL = "https://api.api-ninjas.com/v1/facts"
FACTS_API_KEY = os.getenv("FACTS_API_KEY")

if not FACTS_API_KEY:
    raise ValueError("FACTS_API_KEY not found in .env file")

logger = logging.getLogger(__name__)


class FactsAPIError(Exception):
    """Raised when Facts API call fails."""
    pass


async def get_random_fact() -> str:
    """
    Fetch a random fact from API Ninjas Facts API.

    Returns:
        Single random fact as string

    Raises:
        FactsAPIError: If API call fails with error message
    """
    url = FACTS_API_BASE_URL
    headers = {
        "X-Api-Key": FACTS_API_KEY
    }

    logger.info("Fetching random fact from API Ninjas")
    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request headers: {{'X-Api-Key': '***masked***'}}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            logger.debug(f"Response data: {data}")

            if not isinstance(data, list):
                error_msg = f"Unexpected response format: expected list, got {type(data)}"
                logger.error(error_msg)
                raise FactsAPIError(error_msg)

            if len(data) == 0:
                error_msg = "No facts returned from API"
                logger.error(error_msg)
                raise FactsAPIError(error_msg)

            fact_obj = data[0]
            if not isinstance(fact_obj, dict):
                error_msg = f"Unexpected fact format: expected dict, got {type(fact_obj)}"
                logger.error(error_msg)
                raise FactsAPIError(error_msg)

            fact_text = fact_obj.get("fact")
            if not fact_text:
                error_msg = "Fact text not found in response"
                logger.error(error_msg)
                raise FactsAPIError(error_msg)

            logger.info(f"Successfully retrieved fact: {fact_text[:50]}...")
            return fact_text

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        error_msg = f"HTTP {e.response.status_code}: {error_detail}"
        logger.error(f"Facts API HTTP error: {error_msg}")
        raise FactsAPIError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Network error: {str(e)}"
        logger.error(f"Facts API network error: {error_msg}")
        raise FactsAPIError(error_msg)
    except FactsAPIError:
        raise
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Facts API unexpected error: {error_msg}", exc_info=True)
        raise FactsAPIError(error_msg)
