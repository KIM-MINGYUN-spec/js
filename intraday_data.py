from __future__ import annotations

from typing import Optional

import pandas as pd
import yfinance as yf

from models import IntradaySnapshot


def _ticker_for_krx(code: str, market: str) -> str:
    suffix = ".KS" if market.upper() == "KOSPI" else ".KQ"
    return f"{code}{suffix}"


def _prepare_intraday_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    history = frame.copy()
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = [col[0] for col in history.columns]

    history = history.reset_index()
    time_col = "Datetime" if "Datetime" in history.columns else "Date"
    history = history.rename(
        columns={
            time_col: "Datetime",
            "Open": "Open",
            "High": "High",
            "Low": "Low",
            "Close": "Close",
            "Volume": "Volume",
        }
    )
    history["Datetime"] = pd.to_datetime(history["Datetime"], errors="coerce")
    history = history.dropna(subset=["Datetime", "Open", "High", "Low", "Close", "Volume"])
    history["Open"] = pd.to_numeric(history["Open"], errors="coerce")
    history["High"] = pd.to_numeric(history["High"], errors="coerce")
    history["Low"] = pd.to_numeric(history["Low"], errors="coerce")
    history["Close"] = pd.to_numeric(history["Close"], errors="coerce")
    history["Volume"] = pd.to_numeric(history["Volume"], errors="coerce")
    history = history.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    history = history.sort_values("Datetime").reset_index(drop=True)
    return history


def _fetch_intraday_history(ticker: str) -> pd.DataFrame:
    intervals = ["1m", "2m", "5m"]
    periods = ["1d", "2d"]

    for interval in intervals:
        for period in periods:
            try:
                frame = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            except Exception:
                continue
            prepared = _prepare_intraday_frame(frame)
            if not prepared.empty:
                return prepared

    return pd.DataFrame()


def build_intraday_snapshot(
    code: str,
    market: str,
    reference_price: float,
    avg_volume_ratio_baseline: float = 1.0,
) -> Optional[IntradaySnapshot]:
    ticker = _ticker_for_krx(code, market)
    history = _fetch_intraday_history(ticker)
    if history.empty:
        return None

    session_date = history["Datetime"].dt.date.max()
    session = history[history["Datetime"].dt.date == session_date].copy()
    if session.empty:
        return None

    first_5 = session.head(5)
    if first_5.empty:
        return None

    open_price = float(session.iloc[0]["Open"])
    current_price = float(session.iloc[-1]["Close"])
    first_1m_high = float(session.iloc[0]["High"])
    first_1m_low = float(session.iloc[0]["Low"])
    first_5m_high = float(first_5["High"].max())
    first_5m_low = float(first_5["Low"].min())

    cumulative_turnover = (session["Close"] * session["Volume"]).cumsum()
    cumulative_volume = session["Volume"].cumsum().replace(0, pd.NA)
    vwap_series = (cumulative_turnover / cumulative_volume).fillna(method="bfill").fillna(method="ffill")
    vwap = float(vwap_series.iloc[-1]) if not vwap_series.empty else current_price

    avg_intraday_volume = float(session["Volume"].mean()) if not session.empty else 0.0
    last_volume = float(session.iloc[-1]["Volume"])
    volume_ratio = last_volume / max(avg_intraday_volume * avg_volume_ratio_baseline, 1.0)

    gap_pct = ((open_price / max(reference_price, 0.01)) - 1.0) * 100
    breakout_confirmed = current_price >= first_5m_high
    vwap_reclaimed = current_price >= vwap and float(session["Low"].min()) <= vwap

    return IntradaySnapshot(
        open_price=open_price,
        current_price=current_price,
        gap_pct=gap_pct,
        first_1m_high=first_1m_high,
        first_1m_low=first_1m_low,
        first_5m_high=first_5m_high,
        first_5m_low=first_5m_low,
        vwap=vwap,
        volume_ratio=max(volume_ratio, 0.0),
        breakout_confirmed=breakout_confirmed,
        vwap_reclaimed=vwap_reclaimed,
    )
