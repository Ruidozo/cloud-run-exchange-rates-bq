"""Currency conversion for exchange rates."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def convert_usd_to_eur_base(oxr_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert USD-based rates to EUR-based rates.

    Args:
        oxr_data: Open Exchange Rates API response with USD base

    Returns:
        Dict of currency codes to EUR-based rates

    Example:
        If USD/EUR = 0.85, and USD/GBP = 0.73
        Then EUR/GBP = 0.73 / 0.85 = 0.858824
    """
    usd_rates = oxr_data.get("rates", {})

    if "EUR" not in usd_rates:
        raise ValueError("EUR rate not found in USD-based rates")

    usd_to_eur = usd_rates["EUR"]

    # Convert all rates from USD base to EUR base
    eur_rates = {}
    for currency, usd_rate in usd_rates.items():
        if currency == "EUR":
            eur_rates[currency] = 1.0  # EUR to EUR is always 1
        else:
            eur_rates[currency] = usd_rate / usd_to_eur

    logger.info("Converted %d rates from USD to EUR base", len(eur_rates))
    return eur_rates