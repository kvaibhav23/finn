"""NSE symbol master: symbol -> name, series, ISIN (spike 01). Mainboard only; SME isn't in EQUITY_L."""
from __future__ import annotations

import io

import pandas as pd

from . import http

EQUITY_L = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def parse_equity_list(content: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content))
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip() if s.dtype == object else s)


def load_master(client: http.Client | None = None) -> pd.DataFrame:
    c = client or http.client()
    return parse_equity_list(c.get(EQUITY_L, policy="daily").raise_for_status().content)


def resolve_symbol(nse_symbol: str, master: pd.DataFrame | None = None) -> dict:
    """-> {"symbol", "name", "series", "isin", "listed"}; KeyError if not a listed NSE mainboard equity."""
    m = master if master is not None else load_master()
    row = m.loc[m["SYMBOL"] == nse_symbol.strip().upper()]
    if row.empty:
        raise KeyError(nse_symbol)
    r = row.iloc[0]
    return {"symbol": r["SYMBOL"], "name": r["NAME OF COMPANY"], "series": r["SERIES"],
            "isin": r["ISIN NUMBER"], "listed": r["DATE OF LISTING"]}
