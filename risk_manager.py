from __future__ import annotations

from models import TradePlan


def _safe_ratio(reward: float, risk: float) -> float | None:
    if risk <= 0:
        return None
    return round(reward / risk, 2)


def build_trade_plan(
    entry_price: float,
    atr14: float,
    first_5m_low: float | None = None,
    risk_buffer_pct: float = 0.01,
) -> TradePlan:
    atr_buffer = max(atr14 * 0.7, entry_price * risk_buffer_pct)
    candidate_stop = entry_price - atr_buffer

    if first_5m_low is not None and first_5m_low > 0:
        stop_price = min(candidate_stop, first_5m_low)
    else:
        stop_price = candidate_stop

    target1_price = max(entry_price * 1.015, entry_price + atr14 * 0.8)
    target2_price = max(entry_price * 1.028, entry_price + atr14 * 1.5)

    risk = entry_price - stop_price
    reward1 = target1_price - entry_price
    reward2 = target2_price - entry_price

    return TradePlan(
        entry_price=round(entry_price, 2),
        stop_price=round(stop_price, 2),
        target1_price=round(target1_price, 2),
        target2_price=round(target2_price, 2),
        time_exit_rule="10시 전후까지 VWAP 아래에서 힘이 약하면 시간 손절 우선",
        risk_reward_ratio_1=_safe_ratio(reward1, risk),
        risk_reward_ratio_2=_safe_ratio(reward2, risk),
    )


def summarize_trade_plan(plan: TradePlan) -> list[str]:
    lines = [
        f"예상 진입가 {plan.entry_price:,.0f}원 기준 손절 {plan.stop_price:,.0f}원",
        f"1차 목표 {plan.target1_price:,.0f}원 / 2차 목표 {plan.target2_price:,.0f}원",
        plan.time_exit_rule,
    ]
    if plan.risk_reward_ratio_1 is not None:
        lines.append(f"1차 손익비 {plan.risk_reward_ratio_1:.2f} / 2차 손익비 {plan.risk_reward_ratio_2:.2f}")
    return lines
