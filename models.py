from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(slots=True)
class CandidateContext:
    code: str
    name: str
    sector: str
    prev_close: float
    pre_market_score: float
    surge_score: float
    watch_price: float
    atr14: float
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class IntradaySnapshot:
    open_price: float
    current_price: float
    gap_pct: float
    first_1m_high: float
    first_1m_low: float
    first_5m_high: float
    first_5m_low: float
    vwap: float
    volume_ratio: float
    breakout_confirmed: bool
    vwap_reclaimed: bool


@dataclass(slots=True)
class ExecutionDecision:
    action: str
    execution_score: float
    final_score: float
    gap_score: float
    vwap_score: float
    breakout_score: float
    volume_score: float
    context_score: float
    structure_score: float
    risk_reward_score: float
    reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class TradePlan:
    entry_price: float
    stop_price: float
    target1_price: float
    target2_price: float
    time_exit_rule: str
    risk_reward_ratio_1: Optional[float] = None
    risk_reward_ratio_2: Optional[float] = None
