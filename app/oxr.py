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
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True
)
def fetch_historical_rates(day: Date, app_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch historical exchange rates for a specific date.

    Args:
        day: Date for which to fetch rates
        app_id: Open Exchange Rates API key (defaults to OXR_APP_ID env var)

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

    url = f"https://openexchangerates.org/api/historical/{day.strftime('%Y-%m-%d')}.json?app_id={app_id}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()