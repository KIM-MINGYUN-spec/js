from __future__ import annotations

from typing import List

from models import CandidateContext, ExecutionDecision, IntradaySnapshot


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def build_candidate_context(decision) -> CandidateContext:
    stock = decision.stock
    return CandidateContext(
        code=stock.code,
        name=stock.name,
        sector=stock.sector,
        prev_close=stock.close_price,
        pre_market_score=decision.breakdown.total_score,
        surge_score=decision.breakdown.surge_score,
        watch_price=decision.watch_price,
        atr14=stock.atr14,
        notes=list(getattr(stock, "notes", [])),
    )


def score_gap(snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    gap_pct = snapshot.gap_pct

    if gap_pct >= 4.0:
        reasons.append(f"시초 갭 {gap_pct:.1f}%로 과열 구간입니다.")
        return 0.0, reasons
    if gap_pct >= 2.5:
        reasons.append(f"시초 갭 {gap_pct:.1f}%로 높아 추격 매수는 보수적으로 봅니다.")
        return 12.0, reasons
    if gap_pct >= 0.0:
        reasons.append(f"시초 갭 {gap_pct:.1f}%로 무난한 범위입니다.")
        return 24.0, reasons

    reasons.append(f"갭이 {gap_pct:.1f}%로 약하게 출발해 반등 확인이 필요합니다.")
    return 16.0, reasons


def score_vwap(snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    if snapshot.current_price >= snapshot.vwap and snapshot.vwap_reclaimed:
        reasons.append("VWAP 회복이 확인되어 눌림 이후 재시세 가능성이 있습니다.")
        return 25.0, reasons
    if snapshot.current_price >= snapshot.vwap:
        reasons.append("현재가가 VWAP 위지만 회복 신호는 더 확인이 필요합니다.")
        return 16.0, reasons
    reasons.append("VWAP 아래에 머물러 아직은 매수 우위로 보기 어렵습니다.")
    return 4.0, reasons


def score_breakout(snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    if snapshot.breakout_confirmed:
        reasons.append("첫 5분 고점 재돌파가 확인되었습니다.")
        return 25.0, reasons
    if snapshot.current_price >= snapshot.first_5m_high * 0.995:
        reasons.append("첫 5분 고점 부근까지 회복했지만 돌파 확인은 아직입니다.")
        return 14.0, reasons
    reasons.append("첫 5분 고점 돌파가 아직 확인되지 않았습니다.")
    return 5.0, reasons


def score_volume(snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    ratio = snapshot.volume_ratio
    if ratio >= 2.0:
        reasons.append(f"장초반 거래량이 평균 대비 {ratio:.1f}배로 충분합니다.")
        return 20.0, reasons
    if ratio >= 1.2:
        reasons.append(f"장초반 거래량이 평균 대비 {ratio:.1f}배로 무난합니다.")
        return 12.0, reasons
    reasons.append(f"장초반 거래량이 평균 대비 {ratio:.1f}배로 약합니다.")
    return 4.0, reasons


def score_context(candidate: CandidateContext) -> tuple[float, List[str]]:
    reasons: List[str] = []
    score = 0.0

    if candidate.pre_market_score >= 68:
        score += 10.0
        reasons.append(f"전일 총점 {candidate.pre_market_score:.1f}점으로 후보 질이 좋습니다.")
    elif candidate.pre_market_score >= 58:
        score += 6.0
        reasons.append(f"전일 총점 {candidate.pre_market_score:.1f}점으로 관찰 가치는 있습니다.")
    else:
        score += 2.0
        reasons.append(f"전일 총점 {candidate.pre_market_score:.1f}점으로 보수적 접근이 필요합니다.")

    if candidate.surge_score >= 55:
        score += 5.0
        reasons.append("급등 잠재력 점수가 높아 장초반 탄력 가능성이 있습니다.")
    elif candidate.surge_score >= 45:
        score += 3.0
    else:
        reasons.append("전일 후보는 통과했지만 탄력 자체는 강하지 않을 수 있습니다.")

    return _clamp(score, 0.0, 15.0), reasons


def score_structure(snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    score = 0.0

    if snapshot.current_price >= snapshot.open_price:
        score += 6.0
        reasons.append("현재가가 시가 위에 있어 장초반 매수 우위가 유지되고 있습니다.")
    else:
        reasons.append("현재가가 시가 아래라 장초반 힘이 다소 약합니다.")

    if snapshot.current_price >= snapshot.first_5m_low:
        score += 4.0
    if snapshot.current_price >= snapshot.first_5m_high * 0.995:
        score += 5.0

    return _clamp(score, 0.0, 15.0), reasons


def score_risk_reward(candidate: CandidateContext, snapshot: IntradaySnapshot) -> tuple[float, List[str]]:
    reasons: List[str] = []
    entry_price = max(snapshot.current_price, candidate.watch_price or snapshot.current_price)
    stop_price = min(snapshot.first_5m_low, entry_price - max(candidate.atr14 * 0.7, entry_price * 0.01))
    target1 = max(entry_price * 1.015, entry_price + candidate.atr14 * 0.8)

    risk = max(entry_price - stop_price, 0.01)
    reward = max(target1 - entry_price, 0.0)
    rr = reward / risk

    if rr >= 1.5:
        reasons.append(f"예상 1차 손익비가 {rr:.2f}로 양호합니다.")
        return 10.0, reasons
    if rr >= 1.1:
        reasons.append(f"예상 1차 손익비가 {rr:.2f}로 무난합니다.")
        return 6.0, reasons

    reasons.append(f"예상 1차 손익비가 {rr:.2f}로 낮아 진입 매력이 떨어집니다.")
    return 2.0, reasons


def evaluate_execution(candidate: CandidateContext, snapshot: IntradaySnapshot) -> ExecutionDecision:
    reasons: List[str] = []

    gap_score, gap_reasons = score_gap(snapshot)
    vwap_score, vwap_reasons = score_vwap(snapshot)
    breakout_score, breakout_reasons = score_breakout(snapshot)
    volume_score, volume_reasons = score_volume(snapshot)
    context_score, context_reasons = score_context(candidate)
    structure_score, structure_reasons = score_structure(snapshot)
    risk_reward_score, risk_reward_reasons = score_risk_reward(candidate, snapshot)

    reasons.extend(gap_reasons)
    reasons.extend(vwap_reasons)
    reasons.extend(breakout_reasons)
    reasons.extend(volume_reasons)
    reasons.extend(context_reasons)
    reasons.extend(structure_reasons)
    reasons.extend(risk_reward_reasons)

    if snapshot.current_price < snapshot.first_5m_low:
        reasons.append("첫 5분 저가를 이탈해 보수적으로 접근해야 합니다.")

    execution_score = gap_score + vwap_score + breakout_score + volume_score
    execution_score = _clamp(execution_score, 0.0, 100.0)
    final_score = execution_score * 0.7 + (context_score + structure_score + risk_reward_score) * 0.3

    if snapshot.current_price < snapshot.first_5m_low or snapshot.gap_pct >= 4.0:
        action = "skip"
    elif final_score >= 70.0:
        action = "enter"
    elif final_score >= 52.0:
        action = "watch"
    else:
        action = "skip"

    return ExecutionDecision(
        action=action,
        execution_score=execution_score,
        final_score=final_score,
        gap_score=gap_score,
        vwap_score=vwap_score,
        breakout_score=breakout_score,
        volume_score=volume_score,
        context_score=context_score,
        structure_score=structure_score,
        risk_reward_score=risk_reward_score,
        reasons=reasons,
    )


def build_execution_checklist(candidate: CandidateContext) -> List[str]:
    return [
        f"{candidate.name}은 전일 점수 {candidate.pre_market_score:.1f}점, 급등 가능성 {candidate.surge_score:.1f}점입니다.",
        f"시초가가 전일 종가 대비 +4% 이상이면 추격 매수보다 관망을 우선합니다.",
        f"감시 가격 {candidate.watch_price:,.0f}원 부근에서 첫 눌림 후 VWAP 회복 여부를 확인합니다.",
        "첫 5분 고점 재돌파와 거래량 재증가가 같이 나오면 진입 검토 강도가 올라갑니다.",
        "첫 5분 저점 이탈 또는 VWAP 회복 실패가 나오면 진입보다 패스를 우선합니다.",
    ]
