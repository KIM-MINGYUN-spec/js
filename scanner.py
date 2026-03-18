from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence

import pandas as pd
import yfinance as yf

from market_context import MarketContext
from scoring import EOK, ScoreBreakdown, StockSnapshot, score_stock


FALLBACK_UNIVERSE: List[Dict[str, object]] = [
    {"code": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "반도체", "market_cap": 430_000 * EOK},
    {"code": "000660", "name": "SK하이닉스", "market": "KOSPI", "sector": "반도체", "market_cap": 130_000 * EOK},
    {"code": "005380", "name": "현대차", "market": "KOSPI", "sector": "자동차", "market_cap": 55_000 * EOK},
    {"code": "000270", "name": "기아", "market": "KOSPI", "sector": "자동차", "market_cap": 40_000 * EOK},
    {"code": "012330", "name": "현대모비스", "market": "KOSPI", "sector": "자동차", "market_cap": 23_000 * EOK},
    {"code": "035420", "name": "NAVER", "market": "KOSPI", "sector": "인터넷", "market_cap": 33_000 * EOK},
    {"code": "035720", "name": "카카오", "market": "KOSPI", "sector": "인터넷", "market_cap": 18_000 * EOK},
    {"code": "068270", "name": "셀트리온", "market": "KOSPI", "sector": "바이오", "market_cap": 42_000 * EOK},
    {"code": "105560", "name": "KB금융", "market": "KOSPI", "sector": "금융", "market_cap": 31_000 * EOK},
    {"code": "055550", "name": "신한지주", "market": "KOSPI", "sector": "금융", "market_cap": 24_000 * EOK},
    {"code": "034020", "name": "두산에너빌리티", "market": "KOSPI", "sector": "기계", "market_cap": 15_000 * EOK},
    {"code": "096770", "name": "SK이노베이션", "market": "KOSPI", "sector": "에너지", "market_cap": 12_000 * EOK},
    {"code": "010140", "name": "삼성중공업", "market": "KOSPI", "sector": "조선", "market_cap": 9_000 * EOK},
    {"code": "329180", "name": "HD현대중공업", "market": "KOSPI", "sector": "조선", "market_cap": 12_000 * EOK},
    {"code": "009540", "name": "HD한국조선해양", "market": "KOSPI", "sector": "조선", "market_cap": 12_000 * EOK},
    {"code": "247540", "name": "에코프로비엠", "market": "KOSDAQ", "sector": "2차전지", "market_cap": 22_000 * EOK},
    {"code": "086520", "name": "에코프로", "market": "KOSDAQ", "sector": "2차전지", "market_cap": 14_000 * EOK},
    {"code": "066970", "name": "엘앤에프", "market": "KOSDAQ", "sector": "2차전지", "market_cap": 6_500 * EOK},
    {"code": "196170", "name": "알테오젠", "market": "KOSDAQ", "sector": "바이오", "market_cap": 18_000 * EOK},
    {"code": "028300", "name": "HLB", "market": "KOSDAQ", "sector": "바이오", "market_cap": 10_000 * EOK},
    {"code": "042700", "name": "한미반도체", "market": "KOSPI", "sector": "반도체와반도체장비", "market_cap": 14_000 * EOK},
    {"code": "003670", "name": "포스코퓨처엠", "market": "KOSPI", "sector": "2차전지", "market_cap": 20_000 * EOK},
    {"code": "009150", "name": "삼성전기", "market": "KOSPI", "sector": "전자부품", "market_cap": 11_000 * EOK},
    {"code": "051910", "name": "LG화학", "market": "KOSPI", "sector": "화학", "market_cap": 23_000 * EOK},
    {"code": "006400", "name": "삼성SDI", "market": "KOSPI", "sector": "2차전지", "market_cap": 24_000 * EOK},
]


@dataclass(slots=True)
class ScannerConfig:
    min_prev_trading_value: float = 80 * EOK
    min_avg20_trading_value: float = 20 * EOK
    min_market_cap: float = 1_500 * EOK
    max_candidates: int = 25
    min_total_score: float = 52.0
    min_closing_strength: float = 0.52
    strong_penalty_return_3d_pct: float = 9.0
    hard_exclude_return_3d_pct: float = 12.0
    hard_exclude_1d_gain_pct: float = 7.0
    max_volatility_3d_pct: float = 22.0


@dataclass(slots=True)
class ScanDecision:
    stock: StockSnapshot
    breakdown: ScoreBreakdown
    passed: bool
    exclusion_reasons: List[str] = field(default_factory=list)
    profile: str = "보류"
    watch_price: float = 0.0
    stop_price: float = 0.0
    target1_price: float = 0.0
    target2_price: float = 0.0
    entry_idea: str = ""


@dataclass(slots=True)
class MarketScanResult:
    requested_day: str
    resolved_day: str
    candidate_count: int
    passed_count: int
    data_ready: bool
    note: str
    decisions: List[ScanDecision] = field(default_factory=list)


def _safe_float(value: object) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _prepare_yfinance_history(frame: pd.DataFrame) -> pd.DataFrame:
    history = frame.copy()
    if history.empty:
        return history
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = [column[0] for column in history.columns]
    history = history.reset_index().rename(
        columns={
            "Date": "Date",
            "Open": "시가",
            "High": "고가",
            "Low": "저가",
            "Close": "종가",
            "Volume": "거래량",
        }
    )
    history["Date"] = pd.to_datetime(history["Date"])
    for column in ["시가", "고가", "저가", "종가", "거래량"]:
        history[column] = pd.to_numeric(history[column], errors="coerce")
    history = history.dropna(subset=["시가", "고가", "저가", "종가", "거래량"])
    history["거래대금"] = history["종가"] * history["거래량"]
    history = history.sort_values("Date").reset_index(drop=True)
    history["등락률"] = history["종가"].pct_change().fillna(0.0) * 100
    history["ma5"] = history["종가"].rolling(5).mean()
    history["ma20"] = history["종가"].rolling(20).mean()
    history["avg20_turnover"] = history["거래대금"].rolling(20).mean()
    history["avg20_volume"] = history["거래량"].rolling(20).mean()

    delta = history["종가"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    history["rsi14"] = (100 - (100 / (1 + rs))).fillna(50)

    ema12 = history["종가"].ewm(span=12, adjust=False).mean()
    ema26 = history["종가"].ewm(span=26, adjust=False).mean()
    history["macd"] = ema12 - ema26
    history["macd_signal"] = history["macd"].ewm(span=9, adjust=False).mean()

    prev_close = history["종가"].shift(1)
    tr = pd.concat(
        [
            history["고가"] - history["저가"],
            (history["고가"] - prev_close).abs(),
            (history["저가"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    history["atr14"] = tr.rolling(14, min_periods=14).mean().bfill()

    spread = (history["고가"] - history["저가"]).replace(0, 0.01)
    history["body_ratio"] = (history["종가"] - history["시가"]).abs() / spread
    history["upper_wick_ratio"] = (history["고가"] - history["종가"]) / spread
    return history


def _fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    try:
        frame = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    return _prepare_yfinance_history(frame)


def _box_breakout_ready(history: pd.DataFrame) -> bool:
    if len(history) < 25:
        return False
    recent = history.iloc[-1]
    prior_high = history.iloc[-25:-5]["고가"].max()
    return _safe_float(recent["종가"]) >= _safe_float(prior_high) * 0.985


def _consecutive_long_bullish(history: pd.DataFrame) -> bool:
    recent = history.tail(2)
    if len(recent) < 2:
        return False
    bullish = recent["종가"] > recent["시가"]
    body = recent["body_ratio"] >= 0.55
    gains = recent["등락률"] >= 3.0
    return bool((bullish & body & gains).all())


def _build_snapshot(item: Dict[str, object], history: pd.DataFrame) -> Optional[StockSnapshot]:
    if len(history) < 25:
        return None

    last_row = history.iloc[-1]
    prev_row = history.iloc[-2]
    last3 = history.tail(3)

    close_price = _safe_float(last_row["종가"])
    prev_close = _safe_float(prev_row["종가"])
    avg20_turnover = _safe_float(last_row["avg20_turnover"])
    avg20_volume = _safe_float(last_row["avg20_volume"])
    volume = _safe_float(last_row["거래량"])
    turnover = _safe_float(last_row["거래대금"])
    volume_ratio = volume / max(avg20_volume, 1.0)
    return_3d = ((close_price / max(_safe_float(last3.iloc[0]["종가"]), 0.01)) - 1.0) * 100
    volatility_3d = (last3["고가"].max() - last3["저가"].min()) / max(_safe_float(last3["저가"].min()), 1.0) * 100

    return StockSnapshot(
        code=str(item["code"]),
        name=str(item["name"]),
        market=str(item["market"]),
        sector=str(item["sector"]),
        open_price=_safe_float(last_row["시가"]),
        high_price=_safe_float(last_row["고가"]),
        low_price=_safe_float(last_row["저가"]),
        close_price=close_price,
        volume=volume,
        prev_trading_value=turnover,
        avg20_trading_value=avg20_turnover,
        volume_ratio_20d=volume_ratio,
        market_cap=float(item["market_cap"]),
        return_1d_pct=((close_price / max(prev_close, 0.01)) - 1.0) * 100,
        return_3d_pct=return_3d,
        volatility_3d_pct=volatility_3d,
        ma5=_safe_float(last_row["ma5"]),
        ma20=_safe_float(last_row["ma20"]),
        atr14=_safe_float(last_row["atr14"]),
        rsi14=_safe_float(last_row["rsi14"]),
        rsi_crossed_50=_safe_float(prev_row["rsi14"]) < 50 <= _safe_float(last_row["rsi14"]),
        macd=_safe_float(last_row["macd"]),
        macd_signal=_safe_float(last_row["macd_signal"]),
        box_breakout_ready=_box_breakout_ready(history),
        ma20_breakout_recent=prev_close < max(_safe_float(prev_row["ma20"]), 0.01) and close_price >= max(_safe_float(last_row["ma20"]), 0.01),
        ma5_above_ma20=_safe_float(last_row["ma5"]) >= _safe_float(last_row["ma20"]) > 0,
        sector_turnover_rank_pct=0.0,
        sector_return_rank_pct=0.0,
        sector_close_rank_pct=0.0,
        bullish_candle=close_price > _safe_float(last_row["시가"]),
        body_ratio=_safe_float(last_row["body_ratio"]),
        consecutive_long_bullish_2d=_consecutive_long_bullish(history),
        long_upper_wick=_safe_float(last_row["upper_wick_ratio"]) >= 0.28,
        near_limit_up=((close_price / max(prev_close, 0.01)) - 1.0) * 100 >= 13.0,
        halted_like=False,
        managed_issue=False,
        investment_warning=False,
        operator_style_risk=avg20_turnover < 10 * EOK,
        theme_spike_risk=False,
    )


def _apply_sector_ranks(snapshots: List[StockSnapshot]) -> None:
    if not snapshots:
        return
    frame = pd.DataFrame(
        {
            "code": [item.code for item in snapshots],
            "sector": [item.sector for item in snapshots],
            "turnover": [item.prev_trading_value for item in snapshots],
            "return_1d": [item.return_1d_pct for item in snapshots],
            "closing_strength": [item.closing_strength for item in snapshots],
        }
    )
    frame["turnover_rank"] = frame.groupby("sector")["turnover"].rank(pct=True)
    frame["return_rank"] = frame.groupby("sector")["return_1d"].rank(pct=True)
    frame["close_rank"] = frame.groupby("sector")["closing_strength"].rank(pct=True)
    rank_map = frame.set_index("code")[["turnover_rank", "return_rank", "close_rank"]].to_dict("index")
    for item in snapshots:
        ranks = rank_map.get(item.code, {})
        item.sector_turnover_rank_pct = _safe_float(ranks.get("turnover_rank"))
        item.sector_return_rank_pct = _safe_float(ranks.get("return_rank"))
        item.sector_close_rank_pct = _safe_float(ranks.get("close_rank"))


def fetch_candidates(target_day: Optional[date] = None, config: Optional[ScannerConfig] = None) -> tuple[List[StockSnapshot], str]:
    config = config or ScannerConfig()
    requested_day = (target_day or date.today()).strftime("%Y-%m-%d")
    snapshots: List[StockSnapshot] = []
    resolved_day = ""

    for item in FALLBACK_UNIVERSE:
        if item["code"] == "066970":
            # Yahoo 응답이 불안정한 종목은 기본 유니버스에서 건너뜁니다.
            continue
        suffix = ".KS" if item["market"] == "KOSPI" else ".KQ"
        ticker = f"{item['code']}{suffix}"
        prepared = _fetch_price_history(ticker, period="8mo")
        snapshot = _build_snapshot(item, prepared)
        if snapshot is None:
            continue
        if snapshot.market_cap < config.min_market_cap:
            continue
        if snapshot.prev_trading_value < config.min_prev_trading_value:
            continue
        if snapshot.avg20_trading_value < config.min_avg20_trading_value:
            continue
        if not resolved_day and not prepared.empty:
            resolved_day = prepared.iloc[-1]["Date"].strftime("%Y-%m-%d")
        snapshots.append(snapshot)

    snapshots.sort(key=lambda item: item.prev_trading_value, reverse=True)
    snapshots = snapshots[: config.max_candidates]
    _apply_sector_ranks(snapshots)
    return snapshots, resolved_day or "fallback-yfinance"


def _hard_filter_reasons(stock_item: StockSnapshot, config: ScannerConfig) -> List[str]:
    reasons: List[str] = []
    if stock_item.market_cap < config.min_market_cap:
        reasons.append("시가총액이 1500억 미만입니다.")
    if stock_item.prev_trading_value < config.min_prev_trading_value:
        reasons.append("전일 거래대금이 기준보다 작습니다.")
    if stock_item.avg20_trading_value < config.min_avg20_trading_value:
        reasons.append("최근 20일 평균 거래대금이 기준보다 작습니다.")
    if stock_item.return_3d_pct >= config.hard_exclude_return_3d_pct:
        reasons.append("최근 3거래일 상승률이 12% 이상입니다.")
    if stock_item.return_1d_pct >= config.hard_exclude_1d_gain_pct and stock_item.long_upper_wick:
        reasons.append("전일 급등 후 윗꼬리가 길어 추격 리스크가 큽니다.")
    if stock_item.volatility_3d_pct > config.max_volatility_3d_pct:
        reasons.append("최근 3일 변동성이 과도합니다.")
    return reasons


def _classify_profile(stock_item: StockSnapshot, breakdown: ScoreBreakdown) -> str:
    if stock_item.market_cap >= 20_000 * EOK and breakdown.close_score >= 16 and stock_item.volatility_3d_pct <= 12:
        return "안정형"
    return "탄력형"


def _build_trade_plan(stock_item: StockSnapshot, profile: str) -> Dict[str, float | str]:
    watch_price = max(stock_item.close_price, stock_item.high_price * (0.998 if profile == "안정형" else 0.995))
    atr_buffer = max(stock_item.atr14 * 0.7, watch_price * 0.01)
    stop_price = min(watch_price * 0.99, watch_price - atr_buffer)
    target1 = max(watch_price * 1.015, watch_price + stock_item.atr14 * 0.8)
    target2 = max(watch_price * 1.028, watch_price + stock_item.atr14 * 1.5)
    return {
        "watch_price": round(watch_price, 2),
        "stop_price": round(stop_price, 2),
        "target1_price": round(target1, 2),
        "target2_price": round(target2, 2),
        "entry_idea": "시초 추격 대신 첫 5분봉 눌림 후 VWAP 회복과 재돌파 여부를 확인하세요.",
    }


def evaluate_stock(
    stock_item: StockSnapshot,
    market_context: Optional[MarketContext] = None,
    config: Optional[ScannerConfig] = None,
) -> ScanDecision:
    config = config or ScannerConfig()
    reasons = _hard_filter_reasons(stock_item, config)
    breakdown = score_stock(stock_item, market_context)

    if stock_item.closing_strength < config.min_closing_strength:
        reasons.append("고가권 마감 강도가 약합니다.")
    if stock_item.return_3d_pct >= config.strong_penalty_return_3d_pct and breakdown.total_score < 66:
        reasons.append("최근 3일 상승폭이 높습니다.")
    if breakdown.total_score < config.min_total_score:
        reasons.append("총점이 품질 기준에 미달합니다.")

    passed = not reasons
    profile = _classify_profile(stock_item, breakdown) if passed else "보류"
    plan = _build_trade_plan(stock_item, profile) if passed else {
        "watch_price": 0.0,
        "stop_price": 0.0,
        "target1_price": 0.0,
        "target2_price": 0.0,
        "entry_idea": "",
    }
    return ScanDecision(
        stock=stock_item,
        breakdown=breakdown,
        passed=passed,
        exclusion_reasons=reasons,
        profile=profile,
        watch_price=float(plan["watch_price"]),
        stop_price=float(plan["stop_price"]),
        target1_price=float(plan["target1_price"]),
        target2_price=float(plan["target2_price"]),
        entry_idea=str(plan["entry_idea"]),
    )


def evaluate_market(
    target_day: Optional[date] = None,
    market_context: Optional[MarketContext] = None,
    config: Optional[ScannerConfig] = None,
) -> MarketScanResult:
    config = config or ScannerConfig()
    snapshots, resolved_day = fetch_candidates(target_day=target_day, config=config)
    decisions = [evaluate_stock(item, market_context=market_context, config=config) for item in snapshots]
    decisions.sort(
        key=lambda item: (
            item.breakdown.surge_score,
            item.breakdown.total_score,
            item.breakdown.liquidity_score,
            item.breakdown.close_score,
        ),
        reverse=True,
    )
    passed = [item for item in decisions if item.passed]
    requested_day = (target_day or date.today()).strftime("%Y-%m-%d")

    if not decisions:
        return MarketScanResult(
            requested_day=requested_day,
            resolved_day=resolved_day,
            candidate_count=0,
            passed_count=0,
            data_ready=False,
            note="대표 유동성 종목 유니버스에서도 후보를 만들지 못했습니다. 데이터 응답 또는 기준값을 다시 확인해 주세요.",
            decisions=[],
        )

    note = "대표 유동성 종목 유니버스 기준으로 후보를 생성했습니다."
    if not passed:
        note = "후보는 생성됐지만 현재 기준을 통과한 종목이 없습니다. 상위 후보를 관찰용으로 확인해 보세요."

    return MarketScanResult(
        requested_day=requested_day,
        resolved_day=resolved_day,
        candidate_count=len(decisions),
        passed_count=len(passed),
        data_ready=True,
        note=note,
        decisions=decisions,
    )


def select_recommendations(
    decisions: Sequence[ScanDecision],
    market_context: Optional[MarketContext] = None,
    max_picks: int = 2,
) -> List[ScanDecision]:
    if not decisions:
        return []
    allowed_picks = 1 if market_context and market_context.regime == "Risk-off" else max_picks
    selected: List[ScanDecision] = []
    used_sectors: set[str] = set()

    stable = next((item for item in decisions if item.profile == "안정형"), None)
    if stable is not None:
        selected.append(stable)
        used_sectors.add(stable.stock.sector)

    for candidate in decisions:
        if len(selected) >= allowed_picks:
            break
        if candidate in selected:
            continue
        if candidate.stock.sector in used_sectors and len(selected) >= 1:
            continue
        selected.append(candidate)
        used_sectors.add(candidate.stock.sector)

    if not selected and decisions:
        selected.append(decisions[0])
    return selected[:allowed_picks]


def select_watch_candidates(
    all_decisions: Sequence[ScanDecision],
    recommendations: Sequence[ScanDecision],
    max_watch: int = 1,
) -> List[ScanDecision]:
    if max_watch <= 0:
        return []

    picked_codes = {item.stock.code for item in recommendations}
    watch_list: List[ScanDecision] = []
    seen_codes: set[str] = set()

    for decision in all_decisions:
        if decision.stock.code in picked_codes:
            continue
        if decision.stock.code in seen_codes:
            continue
        if decision.breakdown.total_score < 45:
            continue
        if decision.stock.prev_trading_value < 60 * EOK:
            continue
        if "최근 3거래일 상승률이 12% 이상입니다." in decision.exclusion_reasons:
            continue
        watch_list.append(decision)
        seen_codes.add(decision.stock.code)
        if len(watch_list) >= max_watch:
            break

    return watch_list


def build_watch_message(
    recommendations: Sequence[ScanDecision],
    market_context: Optional[MarketContext] = None,
) -> str:
    if recommendations:
        return ""
    if market_context and market_context.regime == "Risk-off":
        return "오늘은 관망 우세입니다. 글로벌 환경이 Risk-off에 가까워 추천 수를 줄였습니다."
    return "오늘은 관망 우세입니다. 대표 유동성 종목 안에서도 강한 마감과 거래대금을 동시에 만족한 종목이 부족합니다."
