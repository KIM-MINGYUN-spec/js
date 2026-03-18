from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from execution_scoring import build_candidate_context, build_execution_checklist, evaluate_execution
from intraday_data import build_intraday_snapshot
from market_context import classify_market_regime
from models import IntradaySnapshot
from reason_writer import (
    write_recommendation_reason,
    write_signal_summary,
    write_trade_guide,
    write_trader_comment,
    write_watch_message,
)
from risk_manager import build_trade_plan, summarize_trade_plan
from scanner import (
    ScannerConfig,
    build_watch_message,
    evaluate_market,
    select_recommendations,
    select_watch_candidates,
)


st.set_page_config(
    page_title="한국 주식 오전 단타 급등 후보 시스템",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_mobile_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1100px;
            padding-top: 1rem;
            padding-bottom: 3rem;
        }
        .mobile-note {
            background: #eef6ff;
            border: 1px solid #d4e5ff;
            color: #123b75;
            border-radius: 16px;
            padding: 0.9rem 1rem;
            margin: 0.5rem 0 1rem 0;
            font-size: 0.95rem;
        }
        .badge-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin: 0.35rem 0 0.75rem 0;
        }
        .app-badge {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
        }
        .badge-blue {
            background: #e8f1ff;
            color: #0f3e84;
        }
        .badge-red {
            background: #fff1f2;
            color: #a61b29;
        }
        .badge-slate {
            background: #f3f4f6;
            color: #374151;
        }
        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 0.75rem 0.9rem;
        }
        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.8rem;
                padding-right: 0.8rem;
            }
            h1 {
                font-size: 1.9rem !important;
                line-height: 1.25 !important;
            }
            h2 {
                font-size: 1.35rem !important;
            }
            h3 {
                font-size: 1.15rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_environment_warning() -> bool:
    current = sys.version_info
    if current < (3, 11) or current >= (3, 13):
        st.error(
            "현재 Python 환경은 이 앱의 국내 데이터 수집과 맞지 않습니다. "
            "Python 3.11 또는 3.12 환경에서 다시 실행해 주세요."
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
            f"현재 실행 버전: Python {current.major}.{current.minor}.{current.micro} | 권장 버전: Python 3.11 또는 3.12"
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


def _now_kst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _next_trading_session_label(reference_day: date) -> str:
    next_day = reference_day + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return f"{next_day.isoformat()} 오전 9:00~10:00"


def render_header_notice() -> None:
    now_kst = _now_kst()
    st.markdown(
        f"""
        <div class="mobile-note">
            <div class="badge-row">
                <span class="app-badge badge-blue">내일 오전장용</span>
                <span class="app-badge badge-red">장중 즉시 매수 아님</span>
                <span class="app-badge badge-slate">{now_kst.strftime("%Y-%m-%d %H:%M:%S")} KST 계산</span>
            </div>
            이 추천은 <b>지금 바로 매수</b>가 아니라 <b>다음 거래일 오전 9시~10시 장초반 후보</b>입니다.<br>
            시초 추격보다 첫 눌림, VWAP 회복, 첫 5분 고점 재돌파 확인 후 대응하는 구조로 해석하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_simple_summary(recommendations, watch_candidates, market_context, scan_result, target_day: date) -> None:
    now_kst = _now_kst()
    next_session = _next_trading_session_label(target_day)

    st.subheader("한줄 결론")
    if recommendations:
        top = recommendations[0]
        summary = (
            f"{next_session} 기준 1순위는 {top.stock.name}({top.stock.code})입니다. "
            f"장초반에는 시초 추격보다 첫 눌림 후 재돌파를 보는 쪽이 유리합니다."
        )
        st.success(summary)
    elif watch_candidates:
        top = watch_candidates[0]
        summary = (
            f"{next_session} 기준 정식 추천은 없고, {top.stock.name}({top.stock.code})를 관찰 후보로 보는 정도가 적절합니다."
        )
        st.warning(summary)
    else:
        st.warning("이번 분석에서는 무리한 진입보다 관망 쪽이 더 합리적입니다.")

    st.caption(
        f"실행 시각: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} KST | "
        f"적용 대상: {next_session} | "
        f"후보 수집: {scan_result.candidate_count}개 | 필터 통과: {scan_result.passed_count}개 | "
        f"시장 레짐: {market_context.regime}"
    )


def render_candidate_card(item, label: str, show_trade_plan: bool = True) -> None:
    with st.container(border=True):
        st.subheader(f"{item.stock.name} ({item.stock.code})")

        top1, top2, top3, top4 = st.columns(4)
        top1.metric("유형", label)
        top2.metric("총점", f"{item.breakdown.total_score:.1f}")
        top3.metric("급등 가능성", f"{item.breakdown.surge_score:.1f}")
        top4.metric("전일 종가", _format_won(item.stock.close_price))

        mid1, mid2, mid3, mid4 = st.columns(4)
        mid1.metric("거래대금 점수", f"{item.breakdown.liquidity_score:.1f}")
        mid2.metric("마감강도 점수", f"{item.breakdown.close_score:.1f}")
        mid3.metric("업종", item.stock.sector)
        if show_trade_plan:
            mid4.metric("감시 가격", _format_won(item.watch_price))
        else:
            mid4.metric("관찰 포인트", "장초반 흐름")

        st.write(write_trader_comment(item))

        if show_trade_plan:
            stop1, stop2, stop3 = st.columns(3)
            stop1.metric("손절 가격", _format_won(item.stop_price))
            stop2.metric("1차 목표가", _format_won(item.target1_price))
            stop3.metric("2차 목표가", _format_won(item.target2_price))

            with st.expander("자세히 보기", expanded=False):
                st.markdown("**상승 징조**")
                st.write(write_signal_summary(item))

                st.markdown("**선정 이유**")
                st.text(write_recommendation_reason(item))

                st.markdown("**매매 가이드**")
                st.write(write_trade_guide(item))

                candidate = build_candidate_context(item)
                st.markdown("**장초반 실행 체크리스트**")
                for line in build_execution_checklist(candidate):
                    st.write(f"- {line}")

                intraday_plan = build_trade_plan(
                    entry_price=item.watch_price or item.stock.close_price,
                    atr14=item.stock.atr14,
                    first_5m_low=None,
                )
                st.markdown("**리스크 관리 기준**")
                for line in summarize_trade_plan(intraday_plan):
                    st.write(f"- {line}")
        elif item.exclusion_reasons:
            with st.expander("왜 정식 추천은 아닌가", expanded=False):
                st.write(" / ".join(item.exclusion_reasons[:3]))


def render_market_context(target_day: date) -> None:
    context = load_market_context(target_day)
    st.subheader("미국장 / 글로벌 매크로")

    left, right = st.columns([1.0, 1.4])
    with left:
        st.metric("시장 레짐", context.regime)
        st.caption(context.summary)
    with right:
        col_a, col_b = st.columns(2)
        for index, asset in enumerate(context.assets):
            target = col_a if index % 2 == 0 else col_b
            target.write(f"- {asset.label}: {asset.change_pct:+.2f}%")

    st.info("\n".join(context.factors))


def render_execution_result(title: str, candidate, snapshot: IntradaySnapshot) -> None:
    result = evaluate_execution(candidate, snapshot)
    status_map = {
        "enter": ("진입 검토", "success"),
        "watch": ("관찰 유지", "warning"),
        "skip": ("패스 우선", "error"),
    }
    status_text, status_kind = status_map[result.action]
    headline = f"{title}: {status_text} | 최종 판단 {result.final_score:.1f}"

    if status_kind == "success":
        st.success(headline)
    elif status_kind == "warning":
        st.warning(headline)
    else:
        st.error(headline)

    st.caption("내부적으로 실행 점수, 전일 문맥 점수, 구조 점수, 손익비 점수를 함께 반영했습니다.")

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("시초 갭", f"{snapshot.gap_pct:+.2f}%")
    a2.metric("현재가", _format_won(snapshot.current_price))
    a3.metric("VWAP", _format_won(snapshot.vwap))
    a4.metric("거래량 배수", f"{snapshot.volume_ratio:.2f}")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("실행 점수", f"{result.execution_score:.1f}")
    b2.metric("문맥 점수", f"{result.context_score:.1f}")
    b3.metric("구조 점수", f"{result.structure_score:.1f}")
    b4.metric("손익비 점수", f"{result.risk_reward_score:.1f}")

    with st.expander(f"{title} 판단 근거 보기", expanded=False):
        for line in result.reasons:
            st.write(f"- {line}")


def render_manual_intraday_form(selected, candidate) -> None:
    base_price = float(selected.watch_price or selected.stock.close_price)
    base_high = float(selected.stock.high_price or base_price)
    base_low = float(selected.stock.low_price or base_price)

    c1, c2, c3 = st.columns(3)
    open_price = c1.number_input("시가", min_value=0.0, value=round(base_price, 2), step=100.0, key=f"open_{selected.stock.code}")
    current_price = c2.number_input("현재가", min_value=0.0, value=round(base_price, 2), step=100.0, key=f"current_{selected.stock.code}")
    vwap = c3.number_input("VWAP", min_value=0.0, value=round(base_price, 2), step=100.0, key=f"vwap_{selected.stock.code}")

    d1, d2, d3 = st.columns(3)
    first_5m_high = d1.number_input("첫 5분 고가", min_value=0.0, value=round(base_high, 2), step=100.0, key=f"high5_{selected.stock.code}")
    first_5m_low = d2.number_input("첫 5분 저가", min_value=0.0, value=round(base_low, 2), step=100.0, key=f"low5_{selected.stock.code}")
    volume_ratio = d3.number_input("거래량 배수", min_value=0.0, value=1.2, step=0.1, key=f"vol_{selected.stock.code}")

    breakout_confirmed = st.checkbox("첫 5분 고점 재돌파 확인", value=False, key=f"break_{selected.stock.code}")
    vwap_reclaimed = st.checkbox("VWAP 재회복 확인", value=current_price >= vwap if vwap > 0 else False, key=f"vwap_reclaim_{selected.stock.code}")

    gap_pct = ((open_price / base_price) - 1.0) * 100 if base_price > 0 else 0.0
    snapshot = IntradaySnapshot(
        open_price=open_price,
        current_price=current_price,
        gap_pct=gap_pct,
        first_1m_high=first_5m_high,
        first_1m_low=first_5m_low,
        first_5m_high=first_5m_high,
        first_5m_low=first_5m_low,
        vwap=vwap,
        volume_ratio=volume_ratio,
        breakout_confirmed=breakout_confirmed,
        vwap_reclaimed=vwap_reclaimed,
    )
    render_execution_result("수동 판단", candidate, snapshot)


def render_intraday_decision_tool(recommendations, watch_candidates) -> None:
    picked_codes = {item.stock.code for item in recommendations}
    candidates = list(recommendations) + [item for item in watch_candidates if item.stock.code not in picked_codes]
    if not candidates:
        return

    st.subheader("장초반 실행 판단")
    st.caption("가능하면 자동으로 분봉을 읽고, 안 되면 수동 입력으로 다시 계산합니다. 당신에게는 최종 결론만 짧게 먼저 보여줍니다.")

    with st.expander("장초반 자동 판단 도구", expanded=False):
        option_map = {f"{item.stock.name} ({item.stock.code})": item for item in candidates}
        selected_label = st.selectbox("판단할 종목", list(option_map.keys()), key="intraday_target")
        selected = option_map[selected_label]
        candidate = build_candidate_context(selected)

        auto_snapshot = build_intraday_snapshot(
            code=selected.stock.code,
            market=selected.stock.market,
            reference_price=float(selected.watch_price or selected.stock.close_price),
        )

        if auto_snapshot is not None:
            st.success("자동 분봉 데이터를 불러왔습니다.")
            render_execution_result("자동 판단", candidate, auto_snapshot)
            with st.expander("수동으로 다시 계산", expanded=False):
                st.caption("자동 값이 실제 시장 화면과 다르면 아래 숫자로 다시 판단할 수 있습니다.")
                render_manual_intraday_form(selected, candidate)
        else:
            st.warning("자동 분봉 데이터를 읽지 못했습니다. 아래 수동 입력으로 바로 판단할 수 있습니다.")
            render_manual_intraday_form(selected, candidate)


def render_recommendations(target_day: date, max_candidates: int) -> None:
    today = date.today()
    effective_day = min(target_day, today)
    if target_day > today:
        st.warning(f"선택한 날짜가 오늘({today.isoformat()})보다 뒤라서 오늘 기준으로 자동 조정했습니다.")

    try:
        with st.spinner("후보 종목과 점수를 계산하고 있습니다."):
            market_context, scan_result, all_decisions, decisions, recommendations, watch_candidates = load_scan_results(
                effective_day,
                max_candidates,
            )
    except Exception as error:  # pragma: no cover
        st.error("데이터를 불러오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        st.exception(error)
        return

    render_simple_summary(recommendations, watch_candidates, market_context, scan_result, effective_day)

    st.subheader("추천 결과")
    st.caption("전일 마감 기준으로 다음 거래일 오전장에 다시 시세가 붙을 가능성이 높은 후보만 보여줍니다.")
    st.write(
        f"- 요청 기준일: {scan_result.requested_day} | 실제 사용일: {_format_day(scan_result.resolved_day)} | "
        f"후보 수집: {scan_result.candidate_count}개 | 필터 통과: {scan_result.passed_count}개"
    )
    st.write(f"- 적용 대상 시간: {_next_trading_session_label(effective_day)}")
    st.write(f"- 분석 실행 시각: {_now_kst().strftime('%Y-%m-%d %H:%M:%S')} KST")

    if not recommendations:
        if scan_result.data_ready:
            st.warning(build_watch_message(recommendations, market_context))
        else:
            st.error("현재는 관망 판단 이전에 후보 데이터 수집이 충분하지 않습니다.")
        st.caption(scan_result.note)
        with st.expander("왜 추천이 없었는지 보기", expanded=False):
            rejected = [item for item in all_decisions if not item.passed][:10]
            if not rejected:
                st.write(scan_result.note)
            for item in rejected:
                reasons = " / ".join(item.exclusion_reasons[:3]) if item.exclusion_reasons else "탈락 사유 없음"
                st.write(f"- {item.stock.name} ({item.stock.code}) | 총점 {item.breakdown.total_score:.1f} | {reasons}")
        return

    for item in recommendations:
        render_candidate_card(item, item.profile, show_trade_plan=True)

    if watch_candidates:
        st.subheader("관찰 후보")
        st.caption("정식 추천에는 조금 못 미치지만, 장초반 흐름을 체크할 가치가 있는 후보입니다.")
        for item in watch_candidates:
            render_candidate_card(item, "관찰 후보", show_trade_plan=False)

    with st.expander("상위 후보 요약", expanded=False):
        st.write(f"품질 기준을 통과한 후보 수: {len(decisions)}개")
        for item in decisions[:10]:
            st.write(
                f"- {item.stock.name} ({item.stock.code}) | {item.stock.sector} | "
                f"총점 {item.breakdown.total_score:.1f} | 급등 가능성 {item.breakdown.surge_score:.1f} | "
                f"거래대금 {item.breakdown.liquidity_score:.1f} | 마감강도 {item.breakdown.close_score:.1f}"
            )

    with st.expander("상위 탈락 종목 보기", expanded=False):
        rejected = [item for item in all_decisions if not item.passed][:10]
        if not rejected:
            st.write("표시할 탈락 종목이 없습니다.")
        for item in rejected:
            reasons = " / ".join(item.exclusion_reasons[:3]) if item.exclusion_reasons else "탈락 사유 없음"
            st.write(f"- {item.stock.name} ({item.stock.code}) | 총점 {item.breakdown.total_score:.1f} | {reasons}")

    if market_context.regime == "Risk-off":
        st.info("Risk-off 구간에서는 추천 수를 줄이거나 관망 쪽을 우선하는 해석이 더 안전합니다.")

    render_intraday_decision_tool(recommendations, watch_candidates)


def main() -> None:
    inject_mobile_styles()

    st.title("한국 주식 오전 단타 급등 후보 시스템")
    st.caption("오늘 장 마감 데이터를 기준으로 내일 오전 9시~10시 단타 후보를 최대 2개까지 추립니다.")
    render_header_notice()

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
