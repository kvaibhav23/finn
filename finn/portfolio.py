"""The mock portfolio FINN watches: 20 NSE companies across sectors and sizes.

Prices, results and filings are read for every one of them each trading day (no model is called). Promise
ledgers are built on request, for any NSE company; the five built so far are the on-demand research demo.
"""
from __future__ import annotations

PORTFOLIO: dict[str, str] = {
    # IT services
    "TCS": "IT services", "INFY": "IT services", "KPITTECH": "IT services",
    # Banks and lenders: the banking XBRL taxonomy (total income, no EBITDA)
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "BAJFINANCE": "Lending",
    # Energy and telecom
    "RELIANCE": "Energy and retail", "BHARTIARTL": "Telecom",
    # Consumer
    "ITC": "Consumer goods", "ASIANPAINT": "Paints", "TITAN": "Jewellery and watches", "DMART": "Retail",
    # Auto and pharma
    "MARUTI": "Autos", "SUNPHARMA": "Pharma",
    # Capital goods and electronics manufacturing
    "LT": "Engineering", "POLYCAB": "Cables and wires", "DIXON": "Electronics manufacturing",
    # Mid-size and newer listings
    "SUPREMEIND": "Plastics", "COCHINSHIP": "Shipbuilding", "ETERNAL": "Food delivery and quick commerce",
}
