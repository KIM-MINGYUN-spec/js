from __future__ import annotations

from typing import List, Sequence

from scanner import ScanDecision


def _score_line(decision: ScanDecision) -> str:
    breakdown = decision.breakdown
    return (
        f"총점 {breakdown.total_score:.1f}점"
        f" | 급등가능성 {breakdown.surge_score:.1f}"
        f" | 거래대금 {breakdown.liquidity_score:.1f}"
        f" | 마감강도 {breakdown.close_score:.1f}"
        f" | 업종강도 {breakdown.sector_score:.1f}"
        f" | 차트전환 {breakdown.chart_score:.1f}"
    )


def write_recommendation_reason(decision: ScanDecision) -> str:
    stock_item = decision.stock
    lines: List[str] = [
        "전일 거래대금이 크게 집중되며 시장 관심이 확인됐습니다.",
        "종가가 고가권에서 마감해 장 막판까지 매수세가 유지됐습니다.",
    ]

    if stock_item.sector_turnover_rank_pct >= 0.8 or stock_item.sector_return_rank_pct >= 0.8:
        lines.append("같은 업종 안에서도 수급과 상대 수익률이 상위권이라 업종 상대강도가 좋습니다.")
    else:
        lines.append("업종 내 중상위권 흐름을 유지해 단타 관심이 붙기 쉬운 자리입니다.")

    if stock_item.ma20_breakout_recent or stock_item.ma5_above_ma20:
        lines.append("최근 1~2일 내 20일선 돌파 등 단기 추세 전환 신호가 확인됩니다.")
    else:
        lines.append("차트는 과도한 확장보다 재정비 후 재돌파 쪽에 가까운 모습입니다.")

    if stock_item.return_3d_pct < 9.0:
        lines.append("최근 급등 과열 구간은 아니어서 오전 눌림 후 재시세 가능성을 볼 수 있습니다.")
    else:
        lines.append("최근 상승 폭은 있었지만 거래대금과 마감 강도가 이를 일부 상쇄해 선별 관찰 가치가 있습니다.")

    lines.append("시초 급등 추격보다 첫 눌림 이후 재돌파를 보는 전략이 유리합니다.")
    lines.append(_score_line(decision))
    return "\n".join(lines)


def write_trade_guide(decision: ScanDecision) -> str:
    return (
        f"감시 가격 {decision.watch_price:,.0f}원 부근을 보되 시초 추격은 피하세요. "
        f"손절은 {decision.stop_price:,.0f}원 또는 시초 5분 저가 이탈 기준, "
        f"1차 목표 {decision.target1_price:,.0f}원, 2차 목표 {decision.target2_price:,.0f}원입니다. "
        "10시 전후까지 힘이 약하면 시간 손절을 우선하세요."
    )


def write_trader_comment(decision: ScanDecision) -> str:
    stock_item = decision.stock
    breakdown = decision.breakdown

    if breakdown.surge_score >= 80:
        base = "내일 아침 재수급이 붙을 가능성이 높은 상위권 후보입니다."
    elif breakdown.surge_score >= 68:
        base = "내일 오전 단타 관점에서 재시세 가능성을 볼 수 있는 후보입니다."
    else:
        base = "확률은 다소 보수적이지만 조건 대비 관찰 가치는 남아 있습니다."

    if stock_item.trading_value_ratio >= 2.0 and stock_item.closing_strength >= 0.85:
        detail = "전일 거래대금 급증과 고가권 마감이 동시에 나와 단타 세력의 흔적이 비교적 선명합니다."
    elif stock_item.sector_turnover_rank_pct >= 0.8:
        detail = "업종 내 수급 상위권이라 종목 단독보다는 섹터 흐름까지 같이 보는 편이 좋습니다."
    else:
        detail = "시초 급등 추격보다 눌림 이후 체결 회복 여부를 보고 대응하는 편이 안전합니다."

    return f"{base} {detail}"


def write_signal_summary(decision: ScanDecision) -> str:
    tags = decision.breakdown.tags[:5]
    if not tags:
        return "상승 징조 태그 없음"
    return " / ".join(tags)


def write_watch_message() -> str:
    return "오늘은 관망 우세입니다. 조건을 억지로 맞춘 종목보다 쉬는 날을 선택하는 편이 낫습니다."


def render_summary(recommendations: Sequence[ScanDecision]) -> List[str]:
    if not recommendations:
        return [write_watch_message()]
    return [f"{item.stock.name}({item.stock.code})\n{write_recommendation_reason(item)}" for item in recommendations]
