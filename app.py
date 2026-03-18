from __future__ import annotations

import sys
from datetime import date

import streamlit as st

from market_context import classify_market_regime
from reason_writer import (
    write_recommendation_reason,
    write_signal_summary,
    write_trade_guide,
    write_trader_comment,
    write_watch_message,
)
from scanner import (
    ScannerConfig,
    build_watch_message,
    evaluate_market,
    select_recommendations,
    select_watch_candidates,
)


st.set_page_config(page_title="한국 주식 오전 단타 추천", page_icon="📈", layout="wide")


def render_environment_warning() -> bool:
    current = sys.version_info
    if current < (3, 11) or current >= (3, 13):
        st.error(
            "현재 Python 환경은 이 앱의 국내 데이터 수집과 잘 맞지 않습니다. "
            "Python 3.11 또는 3.12 가상환경에서 다시 실행해 주세요."
        )
        st.code(
            "\n".join(
                [
                    "cd C:\\Users\\PC\\Desktop\\영웅",
                    "py -3.11 -m venv .venv311",
                    ".\\.venv311\\Scripts\\Activate.ps1",
                    "python -m pip install --upgrade pip",
                    "pip install -r requirements.txt",
                    "python -m streamlit run app.py",
                ]
            ),
            language="powershell",
        )
        st.caption(
            f"현재 실행 중인 버전: Python {current.major}.{current.minor}.{current.micro} "
            "| 권장 버전: Python 3.11"
        )
        return True
    return False


@st.cache_data(show_spinner=False, ttl=60 * 30)
def load_market_context(target_day: date):
    return classify_market_regime(target_day)


@st.cache_data(show_spinner=False, ttl=60 * 30)
def load_scan_results(target_day: date, max_candidates: int):
    config = ScannerConfig(max_candidates=max_candidates)
    market_context = classify_market_regime(target_day)
    scan_result = evaluate_market(target_day=target_day, market_context=market_context, config=config)
    all_decisions = scan_result.decisions
    passed = [item for item in all_decisions if item.passed]
    recommendations = select_recommendations(passed, market_context=market_context, max_picks=2)
    watch_candidates = select_watch_candidates(all_decisions, recommendations, max_watch=1)
    return market_context, scan_result, all_decisions, passed, recommendations, watch_candidates


def _format_won(value: float) -> str:
    return f"{value:,.0f}원"


def _format_day(day_text: str) -> str:
    if len(day_text) == 8 and day_text.isdigit():
        return f"{day_text[:4]}-{day_text[4:6]}-{day_text[6:]}"
    return day_text or "확인 실패"


def render_candidate_card(item, label: str, show_trade_plan: bool = True) -> None:
    with st.container(border=True):
        top_left, top_right = st.columns([1.2, 1.0])
        with top_left:
            st.markdown(f"### {item.stock.name} ({item.stock.code})")
            st.write(f"- 유형: {label}")
            st.write(f"- 전일 종가: {_format_won(item.stock.close_price)}")
            st.write(f"- 총점: {item.breakdown.total_score:.1f}점")
            st.write(f"- 급등 가능성 점수: {item.breakdown.surge_score:.1f}점")
            if show_trade_plan:
                st.write(f"- 감시 가격: {_format_won(item.watch_price)}")
        with top_right:
            st.write(f"- 업종: {item.stock.sector}")
            st.write(f"- 거래대금 점수: {item.breakdown.liquidity_score:.1f}")
            st.write(f"- 마감강도 점수: {item.breakdown.close_score:.1f}")
            if show_trade_plan:
                st.write(f"- 손절 가격: {_format_won(item.stop_price)}")
                st.write(f"- 1차 목표가: {_format_won(item.target1_price)}")
                st.write(f"- 2차 목표가: {_format_won(item.target2_price)}")

        st.markdown("**트레이더 코멘트**")
        st.write(write_trader_comment(item))

        st.markdown("**상승 징조**")
        st.write(write_signal_summary(item))

        if show_trade_plan:
            st.markdown("**진입 아이디어**")
            st.write(item.entry_idea)

            st.markdown("**선정 이유**")
            st.text(write_recommendation_reason(item))

            st.markdown("**매매 가이드**")
            st.write(write_trade_guide(item))
        elif item.exclusion_reasons:
            st.markdown("**왜 정식 추천은 아닌가**")
            st.write(" / ".join(item.exclusion_reasons[:3]))


def render_market_context(target_day: date) -> None:
    context = load_market_context(target_day)
    st.subheader("미국장 / 글로벌 매크로")
    col1, col2 = st.columns([1.2, 1.8])

    with col1:
        st.metric("시장 레짐", context.regime)
        st.caption(context.summary)

    with col2:
        for asset in context.assets:
            st.write(f"- {asset.label}: {asset.change_pct:+.2f}%")

    st.info("\n".join(context.factors))


def render_recommendations(target_day: date, max_candidates: int) -> None:
    today = date.today()
    effective_day = min(target_day, today)
    if target_day > today:
        st.warning(f"선택한 날짜가 오늘({today.isoformat()})보다 뒤라서 오늘 기준으로 자동 조정했습니다.")

    try:
        with st.spinner("한국장 후보 종목과 점수를 계산하는 중입니다."):
            market_context, scan_result, all_decisions, decisions, recommendations, watch_candidates = load_scan_results(
                effective_day,
                max_candidates,
            )
    except Exception as error:  # pragma: no cover
        st.error("데이터를 불러오는 중 문제가 발생했습니다. 네트워크 상태 또는 데이터 제공처 상태를 확인해 주세요.")
        st.exception(error)
        return

    st.subheader("추천 결과")
    st.caption("내일 아침 재수급 가능성이 높은 상위 후보만 최대 2개까지 선별합니다.")
    st.write(
        f"- 요청 기준일: {scan_result.requested_day} | 실제 사용일: {_format_day(scan_result.resolved_day)} | "
        f"후보 수집: {scan_result.candidate_count}개 | 필터 통과: {scan_result.passed_count}개"
    )

    if not recommendations:
        if scan_result.data_ready:
            st.warning(build_watch_message(recommendations, market_context))
        else:
            st.error("현재는 관망 판단 이전에 후보 데이터 수집이 충분하지 않습니다.")
        st.caption(scan_result.note)
        with st.expander("왜 추천이 없었는지 보기"):
            rejected = [item for item in all_decisions if not item.passed][:10]
            if not rejected:
                st.write(scan_result.note)
            for item in rejected:
                reasons = " / ".join(item.exclusion_reasons[:3]) if item.exclusion_reasons else "세부 사유 없음"
                st.write(
                    f"- {item.stock.name} ({item.stock.code}) | 총점 {item.breakdown.total_score:.1f}점 | {reasons}"
                )
        return

    for item in recommendations:
        render_candidate_card(item, item.profile, show_trade_plan=True)

    if watch_candidates:
        st.subheader("관찰 후보")
        st.caption("품질 기준은 살짝 모자라지만, 내일 장초반 흐름을 함께 볼 만한 후보입니다.")
        for item in watch_candidates:
            render_candidate_card(item, "관찰 후보", show_trade_plan=False)

    with st.expander("후보군 개요 보기"):
        st.write(f"품질 기준을 통과한 후보 수: {len(decisions)}개")
        for item in decisions[:10]:
            st.write(
                f"- {item.stock.name} ({item.stock.code}) | {item.stock.sector} | "
                f"총점 {item.breakdown.total_score:.1f}점 | 급등가능성 {item.breakdown.surge_score:.1f} | "
                f"거래대금 {item.breakdown.liquidity_score:.1f} | 마감강도 {item.breakdown.close_score:.1f}"
            )

    with st.expander("상위 탈락 종목 보기"):
        rejected = [item for item in all_decisions if not item.passed][:10]
        if not rejected:
            st.write("표시할 탈락 종목이 없습니다.")
        for item in rejected:
            reasons = " / ".join(item.exclusion_reasons[:3]) if item.exclusion_reasons else "세부 사유 없음"
            st.write(
                f"- {item.stock.name} ({item.stock.code}) | 총점 {item.breakdown.total_score:.1f}점 | {reasons}"
            )

    if market_context.regime == "Risk-off":
        st.info("Risk-off 장세에서는 추천 수를 1개까지 줄이고, 조건이 애매하면 쉬는 쪽을 우선합니다.")


def main() -> None:
    st.title("한국 주식 오전 단타 급등 후보 시스템")
    st.caption("오늘 한국시장 마감 기준으로 내일 오전 재수급 가능성이 큰 종목을 최대 2개까지 선별합니다.")

    if render_environment_warning():
        return

    with st.sidebar:
        st.header("설정")
        target_day = st.date_input("분석 기준일", value=date.today())
        max_candidates = st.slider("사전 스캔 종목 수", min_value=40, max_value=200, value=120, step=20)
        st.write("기본 필터")
        st.write("- 전일 거래대금 300억 이상 우선")
        st.write("- 최근 20일 평균 거래대금 50억 이상")
        st.write("- 최근 3일 +12% 이상 원칙적 제외")
        st.write("- Risk-off면 추천 축소")

    render_market_context(target_day)
    render_recommendations(target_day, max_candidates)

    st.divider()
    st.caption(write_watch_message())


if __name__ == "__main__":
    main()
