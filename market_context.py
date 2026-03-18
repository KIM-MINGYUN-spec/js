from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List

import pandas as pd
import yfinance as yf


@dataclass(slots=True)
class AssetMove:
    label: str
    ticker: str
    close: float
    change_pct: float


@dataclass(slots=True)
class MarketContext:
    regime: str
    summary: str
    macro_score_5: float
    factors: List[str] = field(default_factory=list)
    assets: List[AssetMove] = field(default_factory=list)
    sector_bias: Dict[str, float] = field(default_factory=dict)


MACRO_TICKERS: Dict[str, str] = {
    "S&P500": "^GSPC",
    "Nasdaq": "^IXIC",
    "SOXX": "SOXX",
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "DXY": "UUP",
    "US10Y": "^TNX",
}


def _fetch_history(ticker: str) -> pd.DataFrame:
    try:
        frame = yf.Ticker(ticker).history(period="10d", interval="1d", auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    if frame.empty:
        return frame
    return frame.dropna()


def _close_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "Close" not in frame.columns:
        return pd.Series(dtype="float64")

    close = frame["Close"]
    if isinstance(close, pd.DataFrame):
        if close.shape[1] == 0:
            return pd.Series(dtype="float64")
        close = close.iloc[:, 0]
    return pd.to_numeric(close, errors="coerce").dropna()


def _change_pct(frame: pd.DataFrame) -> float:
    close = _close_series(frame)
    if len(close) < 2:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-2] - 1.0) * 100)


def _latest_close(frame: pd.DataFrame) -> float:
    close = _close_series(frame)
    if close.empty:
        return 0.0
    return float(close.iloc[-1])


def _build_sector_bias(soxx_change: float, oil_change: float, dxy_change: float, regime: str) -> Dict[str, float]:
    bias: Dict[str, float] = {}

    if soxx_change > 1.0:
        for sector_name in ["반도체", "반도체 제조업", "전자부품", "반도체와반도체장비"]:
            bias[sector_name] = bias.get(sector_name, 0.0) + 1.0
    if oil_change > 1.5:
        for sector_name in ["에너지", "조선", "방위산업", "석유와가스", "기계"]:
            bias[sector_name] = bias.get(sector_name, 0.0) + 0.7
    if dxy_change > 0.7:
        for sector_name in ["항공", "화장품", "2차전지", "소프트웨어"]:
            bias[sector_name] = bias.get(sector_name, 0.0) - 0.5
    if regime == "Risk-off":
        for sector_name in ["기타", "코스닥", "바이오"]:
            bias[sector_name] = bias.get(sector_name, 0.0) - 0.6

    return bias


def classify_market_regime(target_day: date | None = None) -> MarketContext:
    _ = target_day or date.today()

    assets: List[AssetMove] = []
    changes: Dict[str, float] = {}

    for label, ticker in MACRO_TICKERS.items():
        history = _fetch_history(ticker)
        change = _change_pct(history)
        changes[label] = change
        assets.append(
            AssetMove(
                label=label,
                ticker=ticker,
                close=_latest_close(history),
                change_pct=change,
            )
        )

    score = 0
    if changes.get("S&P500", 0.0) > 0.3:
        score += 1
    if changes.get("Nasdaq", 0.0) > 0.5:
        score += 1
    if changes.get("SOXX", 0.0) > 1.0:
        score += 1
    if changes.get("WTI", 0.0) > 1.0 or changes.get("Brent", 0.0) > 1.0:
        score += 1
    if changes.get("DXY", 0.0) < 0.5:
        score += 1
    if changes.get("US10Y", 0.0) < 0.8:
        score += 1

    if score >= 5:
        regime = "Risk-on"
        macro_score = 4.5
    elif score >= 3:
        regime = "Mixed"
        macro_score = 3.0
    else:
        regime = "Risk-off"
        macro_score = 1.5

    factors: List[str] = []
    if changes.get("SOXX", 0.0) > 1.0:
        factors.append("미국 반도체가 강해 국내 반도체·장비 업종에 우호적입니다.")
    if changes.get("WTI", 0.0) > 1.0 or changes.get("Brent", 0.0) > 1.0:
        factors.append("유가가 강해 조선·에너지 관련 수급에 보조 신호가 있습니다.")
    if changes.get("DXY", 0.0) > 0.7:
        factors.append("달러 강세가 커서 소형 성장주에는 부담이 될 수 있습니다.")
    if changes.get("US10Y", 0.0) > 1.0:
        factors.append("미국 10년물 금리 상승이 커서 고밸류 성장주에는 보수적으로 접근하는 편이 좋습니다.")
    if not factors:
        factors.append("글로벌 변수는 중립에 가깝고, 전일 한국장 수급이 더 중요합니다.")

    summary = {
        "Risk-on": "미국장과 매크로가 우호적이지만, 국내 종목 추천은 전일 거래대금과 고가권 마감 강도를 우선합니다.",
        "Mixed": "글로벌 분위기는 혼조입니다. 국내 수급이 강한 종목만 선별적으로 접근하는 편이 좋습니다.",
        "Risk-off": "글로벌 환경이 조심스러워 추천 수를 줄이거나 관망하는 편이 유리합니다.",
    }[regime]

    return MarketContext(
        regime=regime,
        summary=summary,
        macro_score_5=macro_score,
        factors=factors,
        assets=assets,
        sector_bias=_build_sector_bias(
            soxx_change=changes.get("SOXX", 0.0),
            oil_change=max(changes.get("WTI", 0.0), changes.get("Brent", 0.0)),
            dxy_change=changes.get("DXY", 0.0),
            regime=regime,
        ),
    )
