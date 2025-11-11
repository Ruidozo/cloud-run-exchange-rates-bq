# app/converter.py
# Module for converting exchange rates from USD base to EUR base.
# This module provides a function to perform the conversion


import logging
import math
from typing import Any, Dict

logger = logging.getLogger(__name__)


def convert_usd_to_eur_base(oxr_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert USD-based rates to EUR-based rates.

    Open Exchange Rates returns rates with USD as base.
    This function converts all rates to have EUR as the base currency.

    Formula: rate_to_eur = rate_to_usd / eur_to_usd

    Args:
        oxr_data: Response from Open Exchange Rates API

    Returns:
        Dictionary of currency codes to EUR-based rates

    Raises:
        KeyError: If 'rates' key is missing from response
        ValueError: If EUR rate is missing or invalid
    """
    # Check for rates key
    if "rates" not in oxr_data:
        logger.error("Missing 'rates' key in API response")
        raise KeyError("Missing 'rates' key in API response")

    usd_rates = oxr_data["rates"]

    # Validate that rates is a dictionary
    if not isinstance(usd_rates, dict):
        logger.error("Invalid rates type: expected dict, got %s", type(usd_rates).__name__)
        raise TypeError(f"rates must be a dictionary, got {type(usd_rates).__name__}")

    # Check if rates is empty
    if not usd_rates:
        logger.error("Empty rates dictionary in API response")
        raise ValueError("EUR rate not found in API response")

    # Get EUR to USD rate
    if "EUR" not in usd_rates:
        logger.error("EUR rate not found in API response. Available currencies: %s",
                    list(usd_rates.keys()))
        raise ValueError("EUR rate not found in API response")

    usd_to_eur = usd_rates["EUR"]

    # Validate EUR rate is positive
    if usd_to_eur <= 0:
        logger.error("Invalid EUR rate: %s (must be positive)", usd_to_eur)
        raise ValueError(f"EUR rate must be greater than zero, got {usd_to_eur}")

    # Convert all rates from USD base to EUR base
    eur_rates = {}

    for currency, usd_rate in usd_rates.items():
        # Skip None values
        if usd_rate is None:
            logger.warning("Skipping %s: rate is None", currency)
            continue

        # Skip non-numeric values
        if not isinstance(usd_rate, (int, float)):
            logger.warning("Skipping %s: rate is not numeric (%s)", currency, type(usd_rate).__name__)
            continue

        # Skip NaN and infinity
        if math.isnan(usd_rate) or math.isinf(usd_rate):
            logger.warning("Skipping %s: invalid float value (NaN or Inf)", currency)
            continue

        if usd_rate <= 0:
            logger.warning("Skipping %s: invalid rate %s (must be positive)", currency, usd_rate)
            continue

        if currency == "EUR":
            eur_rates[currency] = 1.0  # EUR to EUR is always 1
        else:
            # Calculate rate relative to EUR
            eur_rates[currency] = usd_rate / usd_to_eur

    logger.info("Converted %d currencies to EUR base", len(eur_rates))

    return eur_rates