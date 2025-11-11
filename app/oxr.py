# app/oxr.py
# Module for fetching exchange rates from Open Exchange Rates API.
# This module provides a function to fetch historical rates with retry logic.

import logging
import os
import time
from datetime import date as Date
from typing import Any, Dict, Optional

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

logger = logging.getLogger(__name__)


def fetch_historical_rates(
    day: Date,
    app_id: Optional[str] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Fetch historical exchange rates for a specific date.

    Args:
        day: Date for which to fetch rates
        app_id: Open Exchange Rates API key (defaults to OXR_APP_ID env var)
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary containing exchange rate data

    Raises:
        ValueError: If API key is missing
        HTTPError: If API returns error status after retries
        RequestException: If network error occurs after retries
    """
    if app_id is None:
        app_id = os.getenv("OXR_APP_ID")

    if not app_id:
        raise ValueError("OXR_APP_ID environment variable not set")

    base_url = "https://openexchangerates.org/api/historical"
    date_str = day.strftime("%Y-%m-%d")
    url = f"{base_url}/{date_str}.json?app_id={app_id}"

    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Fetching rates for %s (attempt %d/%d)",
                day, attempt, max_retries
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()

        except HTTPError as e:
            last_exception = e
            # Don't retry on 4xx errors (client errors)
            if 400 <= e.response.status_code < 500:
                logger.error(
                    "Client error for %s: %s (status %d)",
                    day, e, e.response.status_code
                )
                raise
            # Retry on 5xx errors (server errors)
            logger.warning(
                "Server error for %s: %s (attempt %d/%d)",
                day, e, attempt, max_retries
            )

        except Timeout as e:
            last_exception = e
            logger.warning(
                "Timeout for %s (attempt %d/%d)",
                day, attempt, max_retries
            )

        except RequestException as e:
            last_exception = e
            logger.warning(
                "Network error for %s: %s (attempt %d/%d)",
                day, e, attempt, max_retries
            )

        if attempt < max_retries:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.info("Retrying in %d seconds...", wait_time)
            time.sleep(wait_time)

    logger.error("Failed to fetch rates for %s after %d attempts", day, max_retries)
    raise last_exception