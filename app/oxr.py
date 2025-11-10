"""Open Exchange Rates API client."""

import logging
import os
import time
from datetime import date as Date
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def fetch_historical_rates(
    day: Date,
    app_id: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 2,
) -> Dict[str, Any]:
    """
    Fetch historical exchange rates from Open Exchange Rates API (USD base).

    Args:
        day: Python date object.
        app_id: Open Exchange Rates API key. If not provided, uses OXR_APP_ID env var.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay between retries in seconds.

    Returns:
        Dict containing the JSON response from Open Exchange Rates.

    Raises:
        httpx.HTTPError: If the request fails after all retries.
        ValueError: If no API key is configured.
    """
    if not app_id:
        app_id = os.getenv("OXR_APP_ID")
        if not app_id:
            raise ValueError("OXR_APP_ID environment variable is not set")

    url = f"https://openexchangerates.org/api/historical/{day.isoformat()}.json"
    params = {"app_id": app_id}

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching rates for %s (attempt %d/%d)", day, attempt, max_retries)
            response = httpx.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            logger.info("Successfully fetched %d rates for %s", len(data.get("rates", {})), day)
            return data
        except httpx.HTTPError as e:
            logger.warning("Attempt %d failed for %s: %s", attempt, day, e)
            if attempt < max_retries:
                logger.info("Retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
            else:
                logger.error("All %d attempts failed for %s", max_retries, day)
                raise

    # Should never reach here:
    raise RuntimeError("Unexpected error in fetch_historical_rates")