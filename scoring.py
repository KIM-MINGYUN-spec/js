from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List


if TYPE_CHECKING:
    from market_context import MarketContext


EOK = 100_000_000
EPSILON = 0.01


@dataclass(slots=True)
class StockSnapshot:
    code: str
    name: str
    market: str
    sector: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    prev_trading_value: float
    avg20_trading_value: float
    volume_ratio_20d: float
    market_cap: float
    return_1d_pct: float
    return_3d_pct: float
    volatility_3d_pct: float
    ma5: float
    ma20: float
    atr14: float
    rsi14: float
    rsi_crossed_50: bool
    macd: float
    macd_signal: float
    box_breakout_ready: bool
    ma20_breakout_recent: bool
    ma5_above_ma20: bool
    sector_turnover_rank_pct: float
    sector_return_rank_pct: float
    sector_close_rank_pct: float
    bullish_candle: bool
    body_ratio: float
    consecutive_long_bullish_2d: bool
    long_upper_wick: bool
    near_limit_up: bool
    halted_like: bool
    managed_issue: bool
    investment_warning: bool
    operator_style_risk: bool
    theme_spike_risk: bool
    notes: List[str] = field(default_factory=list)

    @property
    def candle_range(self) -> float:
        return max(self.high_price - self.low_price, EPSILON)

    @property
    def closing_strength(self) -> float:
        return (self.close_price - self.low_price) / self.candle_range

    @property
    def upper_wick_ratio(self) -> float:
        return max(self.high_price - self.close_price, 0.0) / self.candle_range

    @property
    def trading_value_ratio(self) -> float:
        return self.prev_trading_value / max(self.avg20_trading_value, EPSILON)


@dataclass(slots=True)
class ScoreBreakdown:
    liquidity_score: float
    close_score: float
    sector_score: float
    chart_score: float
    macro_score: float
    penalty_score: float
    total_score: float
    surge_score: float
    conviction: str
    tags: List[str] = field(default_factory=list)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def score_liquidity(stock: StockSnapshot) -> float:
    absolute_turnover = _clamp(stock.prev_trading_value / (1_200 * EOK), 0.0, 1.0) * 16.0
    turnover_ratio = _clamp((stock.trading_value_ratio - 1.0) / 2.5, 0.0, 1.0) * 12.0
    volume_ratio = _clamp((stock.volume_ratio_20d - 1.0) / 3.0, 0.0, 1.0) * 4.0
    baseline_liquidity = _clamp(stock.avg20_trading_value / (200 * EOK), 0.0, 1.0) * 3.0

    score = absolute_turnover + turnover_ratio + volume_ratio + baseline_liquidity

    if stock.prev_trading_value >= 300 * EOK:
        score += 2.0
    if stock.trading_value_ratio >= 2.0:
        score += 1.5

    return _clamp(score, 0.0, 35.0)


def score_close_strength(stock: StockSnapshot) -> float:
    score = _clamp(stock.closing_strength, 0.0, 1.0) * 14.0

    if stock.closing_strength >= 0.75:
        score += 4.0
    if stock.closing_strength >= 0.85:
        score += 3.0

    if stock.upper_wick_ratio <= 0.15:
        score += 2.0
    elif stock.upper_wick_ratio >= 0.30:
        score -= 2.5

    if stock.bullish_candle and stock.body_ratio >= 0.45:
        score += 2.5
    elif stock.bullish_candle:
        score += 1.0

    if stock.long_upper_wick:
        score -= 3.0

    return _clamp(score, 0.0, 25.0)


def score_sector_strength(stock: StockSnapshot) -> float:
    turnover = _clamp(stock.sector_turnover_rank_pct, 0.0, 1.0) * 6.0
    returns = _clamp(stock.sector_return_rank_pct, 0.0, 1.0) * 5.0
    close_rank = _clamp(stock.sector_close_rank_pct, 0.0, 1.0) * 4.0
    return _clamp(turnover + returns + close_rank, 0.0, 15.0)


def score_chart(stock: StockSnapshot) -> float:
    score = 0.0

    if stock.ma20_breakout_recent:
        score += 5.0
    elif stock.close_price >= stock.ma20:
        score += 2.5

    if stock.ma5_above_ma20:
        score += 3.5

    if stock.rsi_crossed_50:
        score += 2.0
    elif stock.rsi14 >= 50:
        score += 1.0

    if stock.macd >= stock.macd_signal:
        score += 2.0
        if stock.macd > 0:
            score += 0.8

    if stock.box_breakout_ready:
        score += 1.7

    return _clamp(score, 0.0, 15.0)


def score_macro(stock: StockSnapshot, market_context: "MarketContext | None") -> float:
    if market_context is None:
        return 2.5

    score = market_context.macro_score_5
    sector_boost = market_context.sector_bias.get(stock.sector, 0.0)

    if market_context.regime == "Risk-off" and stock.market_cap < 5_000 * EOK:
        score -= 1.2

    return _clamp(score + sector_boost, 0.0, 5.0)


def compute_penalty(stock: StockSnapshot) -> float:
    penalty = 0.0

    if stock.return_3d_pct >= 12.0:
        penalty += 25.0
    elif stock.return_3d_pct >= 9.0:
        penalty += 10.0

    if stock.consecutive_long_bullish_2d:
        penalty += 4.0
    if stock.long_upper_wick and stock.return_1d_pct >= 7.0:
        penalty += 10.0
    if stock.near_limit_up:
        penalty += 12.0
    if stock.theme_spike_risk:
        penalty += 8.0
    if stock.operator_style_risk:
        penalty += 6.0

    return penalty


def classify_conviction(stock: StockSnapshot, total_score: float) -> str:
    if (
        stock.prev_trading_value >= 300 * EOK
        and stock.trading_value_ratio >= 2.0
        and stock.closing_strength >= 0.85
        and stock.bullish_candle
    ):
        return "핵심 후보"
    if total_score >= 76:
        return "상위 후보"
    if total_score >= 68:
        return "관찰 후보"
    return "보류"


def score_surge_potential(stock: StockSnapshot, market_context: "MarketContext | None" = None) -> float:
    score = 0.0

    if stock.prev_trading_value >= 300 * EOK:
        score += 18.0
    elif stock.prev_trading_value >= 200 * EOK:
        score += 12.0

    if stock.trading_value_ratio >= 2.0:
        score += 16.0
    elif stock.trading_value_ratio >= 1.5:
        score += 8.0

    if stock.closing_strength >= 0.85:
        score += 16.0
    elif stock.closing_strength >= 0.75:
        score += 10.0

    if stock.upper_wick_ratio <= 0.15:
        score += 6.0
    elif stock.upper_wick_ratio >= 0.30:
        score -= 8.0

    if stock.sector_turnover_rank_pct >= 0.8:
        score += 8.0
    if stock.sector_return_rank_pct >= 0.8:
        score += 6.0
    if stock.ma20_breakout_recent:
        score += 7.0
    if stock.ma5_above_ma20:
        score += 5.0
    if stock.rsi_crossed_50:
        score += 4.0
    if stock.macd >= stock.macd_signal:
        score += 4.0
    if stock.box_breakout_ready:
        score += 5.0

    if stock.return_3d_pct >= 12.0:
        score -= 20.0
    elif stock.return_3d_pct >= 9.0:
        score -= 10.0

    if stock.long_upper_wick and stock.return_1d_pct >= 7.0:
        score -= 12.0
    if stock.near_limit_up:
        score -= 15.0
    if stock.consecutive_long_bullish_2d:
        score -= 6.0

    if market_context is not None and market_context.regime == "Risk-off":
        score -= 8.0

    return _clamp(score, 0.0, 100.0)


def score_stock(stock: StockSnapshot, market_context: "MarketContext | None" = None) -> ScoreBreakdown:
    liquidity_score = score_liquidity(stock)
    close_score = score_close_strength(stock)
    sector_score = score_sector_strength(stock)
    chart_score = score_chart(stock)
    macro_score = score_macro(stock, market_context)
    penalty_score = compute_penalty(stock)
    surge_score = score_surge_potential(stock, market_context)
    total_score = _clamp(
        liquidity_score + close_score + sector_score + chart_score + macro_score - penalty_score,
        0.0,
        100.0,
    )

    tags: List[str] = []
    if stock.prev_trading_value >= 300 * EOK:
        tags.append("전일 거래대금 우수")
    if stock.trading_value_ratio >= 2.0:
        tags.append("거래대금 급증")
    if stock.closing_strength >= 0.85:
        tags.append("매우 강한 고가권 마감")
    elif stock.closing_strength >= 0.75:
        tags.append("강한 고가권 마감")
    if stock.ma20_breakout_recent:
        tags.append("20일선 돌파")
    if stock.sector_turnover_rank_pct >= 0.8:
        tags.append("업종 수급 상위")
    if stock.upper_wick_ratio <= 0.15:
        tags.append("윗꼬리 짧음")
    if stock.rsi_crossed_50:
        tags.append("RSI 50 상향")
    if stock.macd >= stock.macd_signal:
        tags.append("MACD 우위")
    if stock.box_breakout_ready:
        tags.append("박스권 돌파 임박")

    return ScoreBreakdown(
        liquidity_score=liquidity_score,
        close_score=close_score,
        sector_score=sector_score,
        chart_score=chart_score,
        macro_score=macro_score,
        penalty_score=penalty_score,
        total_score=total_score,
        surge_score=surge_score,
        conviction=classify_conviction(stock, total_score),
        tags=tags,
    )
