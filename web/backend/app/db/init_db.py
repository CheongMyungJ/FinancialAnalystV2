from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, SQLModel, select
from sqlalchemy.exc import OperationalError

import json

from app.db.models import FactorDefinition, WeightPreset
from app.db.session import engine


def init_db() -> None:
    try:
        SQLModel.metadata.create_all(engine)
    except OperationalError as e:
        # In dev with auto-reload, concurrent startup can race on CREATE TABLE.
        if "already exists" in str(e).lower():
            return
        raise


def seed_default_factors(session: Session) -> None:
    now = datetime.utcnow()
    defaults = [
        FactorDefinition(
            key="momentum_120d",
            name="모멘텀(120일 수익률)",
            description="최근 120거래일 종가 기준 수익률",
            factor_type="technical",
            calculator="momentum_120d",
            weight=0.35,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="volatility_20d",
            name="변동성(20일)",
            description="최근 20거래일 일간 수익률 표준편차(낮을수록 좋음)",
            factor_type="technical",
            calculator="volatility_20d",
            weight=0.15,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="gdelt_tone",
            name="뉴스 톤(GDELT)",
            description="최근 관련 기사 tone 평균(높을수록 긍정)",
            factor_type="sentiment",
            calculator="gdelt_tone",
            weight=0.10,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="roe_ttm",
            name="ROE(TTM)",
            description="(US 우선) Return on Equity TTM (높을수록 좋음)",
            factor_type="fundamental",
            calculator="roe_ttm",
            weight=0.20,
            higher_is_better=True,
            normalize="percentile",
            enabled=False,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="pe_ratio",
            name="PER",
            description="(US 우선) Price/Earnings (낮을수록 좋음)",
            factor_type="fundamental",
            calculator="pe_ratio",
            weight=0.20,
            higher_is_better=False,
            normalize="percentile",
            enabled=False,
            created_at=now,
            updated_at=now,
        ),
        # --- Technical (priority 1) ---
        FactorDefinition(
            key="rsi_14",
            name="RSI(14)",
            description="RSI(14) (낮을수록 과열 아님; 0~100)",
            factor_type="technical",
            calculator="rsi_14",
            weight=0.05,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="macd_hist",
            name="MACD 히스토그램",
            description="MACD(12,26,9) histogram (모멘텀 변화; 높을수록 좋음)",
            factor_type="technical",
            calculator="macd_hist",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="dist_to_52w_high",
            name="52주 고점 거리",
            description="최근 종가가 52주 고점 대비 얼마나 근접한지 (0에 가까울수록 좋음)",
            factor_type="technical",
            calculator="dist_to_52w_high",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="rs_6m_vs_benchmark",
            name="상대강도(6M, 벤치마크 대비)",
            description="최근 6개월 수익률이 벤치마크(US: QQQ, KR: 069500) 대비 얼마나 강한지",
            factor_type="technical",
            calculator="rs_6m_vs_benchmark",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="atr_14p",
            name="ATR(14) %",
            description="ATR(14)/종가 (변동성 위험; 낮을수록 좋음)",
            factor_type="technical",
            calculator="atr_14p",
            weight=0.05,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        # --- Sentiment/News (priority 2) ---
        FactorDefinition(
            key="news_volume_14d",
            name="뉴스량(14일)",
            description="최근 14일 뉴스(캐시) 기사 수",
            factor_type="sentiment",
            calculator="news_volume_14d",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="news_tone_change",
            name="뉴스 톤 변화(3일-14일)",
            description="최근 3일 평균 톤 - 14일 평균 톤 (반전/개선 탐지)",
            factor_type="sentiment",
            calculator="news_tone_change",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="news_neg_risk_14d",
            name="부정 키워드 리스크(14일)",
            description="최근 14일 뉴스 제목의 부정 키워드 매칭 횟수(낮을수록 좋음)",
            factor_type="sentiment",
            calculator="news_neg_risk_14d",
            weight=0.05,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        # --- Fundamentals (priority 3) ---
        FactorDefinition(
            key="ev_to_ebitda",
            name="EV/EBITDA",
            description="Enterprise Value / EBITDA (낮을수록 좋음)",
            factor_type="fundamental",
            calculator="ev_to_ebitda",
            weight=0.05,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="fcf_yield",
            name="FCF 수익률",
            description="Free Cash Flow / Market Cap (높을수록 좋음)",
            factor_type="fundamental",
            calculator="fcf_yield",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="debt_to_ebitda",
            name="부채/EBITDA",
            description="Total Debt / EBITDA (낮을수록 좋음)",
            factor_type="fundamental",
            calculator="debt_to_ebitda",
            weight=0.05,
            higher_is_better=False,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="revenue_growth_yoy",
            name="매출 성장률(YoY)",
            description="Revenue Growth (YoY; 높을수록 좋음)",
            factor_type="fundamental",
            calculator="revenue_growth_yoy",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        FactorDefinition(
            key="earnings_growth_yoy",
            name="이익 성장률(YoY)",
            description="Earnings Growth (YoY; 높을수록 좋음)",
            factor_type="fundamental",
            calculator="earnings_growth_yoy",
            weight=0.05,
            higher_is_better=True,
            normalize="percentile",
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
    ]

    existing_keys = set(session.exec(select(FactorDefinition.key)).all())
    for f in defaults:
        if f.key in existing_keys:
            continue
        session.add(f)
    session.commit()


def seed_default_weight_presets(session: Session) -> None:
    now = datetime.utcnow()
    existing = set(session.exec(select(WeightPreset.key)).all())

    def add(*, key: str, name: str, description: str, weights: dict[str, float], enabled: dict[str, bool] | None = None) -> None:
        if key in existing:
            return
        cfg = {
            "mode": "strict",
            "weights": weights,
            "enabled": enabled or {k: True for k in weights.keys()},
        }
        session.add(
            WeightPreset(
                key=key,
                name=name,
                description=description,
                config_json=json.dumps(cfg, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    # 1) Technical-heavy
    add(
        key="tech_focus",
        name="기술적 분석 중심",
        description="추세/모멘텀/상대강도/리스크(ATR) 위주. 재무는 보조.",
        weights={
            "momentum_120d": 0.16,
            "rs_6m_vs_benchmark": 0.14,
            "macd_hist": 0.10,
            "rsi_14": 0.08,
            "dist_to_52w_high": 0.08,
            "atr_14p": 0.10,
            "volatility_20d": 0.06,
            "gdelt_tone": 0.06,
            "news_tone_change": 0.06,
            "ev_to_ebitda": 0.06,
            "fcf_yield": 0.05,
            "debt_to_ebitda": 0.05,
        },
    )

    # 2) Value investing
    add(
        key="value_focus",
        name="가치투자 중심",
        description="밸류/현금흐름/퀄리티(ROE) + 재무건전성(부채) 중심. 가격 모멘텀은 보조.",
        weights={
            "fcf_yield": 0.18,
            "ev_to_ebitda": 0.18,
            "pe_ratio": 0.10,
            "roe_ttm": 0.12,
            "debt_to_ebitda": 0.10,
            "revenue_growth_yoy": 0.08,
            "earnings_growth_yoy": 0.08,
            "atr_14p": 0.06,
            "rs_6m_vs_benchmark": 0.05,
            "momentum_120d": 0.05,
            "gdelt_tone": 0.05,
            "news_neg_risk_14d": 0.05,
        },
    )

    # 3) Momentum + news/issues
    add(
        key="momentum_news",
        name="모멘텀/이슈 중심",
        description="가격 모멘텀 + 뉴스(톤/변화/이슈) 중심. 리스크(ATR)로 과열을 일부 제어.",
        weights={
            "momentum_120d": 0.16,
            "rs_6m_vs_benchmark": 0.14,
            "macd_hist": 0.10,
            "dist_to_52w_high": 0.08,
            "rsi_14": 0.06,
            "gdelt_tone": 0.10,
            "news_tone_change": 0.10,
            "news_volume_14d": 0.06,
            "news_neg_risk_14d": 0.06,
            "atr_14p": 0.08,
            "ev_to_ebitda": 0.03,
            "fcf_yield": 0.03,
        },
    )

    # 4) Balanced (core multi-factor)
    add(
        key="balanced",
        name="밸런스형(균형)",
        description="기술/재무/뉴스를 균형 있게(중장기 기본형). 극단적 쏠림을 줄이고 커버리지/안정성을 우선.",
        weights={
            # Technical
            "momentum_120d": 0.10,
            "rs_6m_vs_benchmark": 0.10,
            "macd_hist": 0.06,
            "rsi_14": 0.05,
            "dist_to_52w_high": 0.05,
            "atr_14p": 0.07,
            "volatility_20d": 0.05,
            # Sentiment
            "gdelt_tone": 0.08,
            "news_tone_change": 0.08,
            "news_volume_14d": 0.05,
            "news_neg_risk_14d": 0.05,
            # Fundamentals
            "fcf_yield": 0.10,
            "ev_to_ebitda": 0.10,
            "pe_ratio": 0.05,
            "roe_ttm": 0.06,
            "debt_to_ebitda": 0.05,
            "revenue_growth_yoy": 0.03,
            "earnings_growth_yoy": 0.04,
        },
    )

    # 5) Low-vol / Defensive
    add(
        key="defensive_lowvol",
        name="저변동/방어형",
        description="변동성/리스크/레버리지(부채) 비중을 높여 방어적으로 구성. 뉴스 리스크도 일부 반영.",
        weights={
            # Risk first
            "atr_14p": 0.16,
            "volatility_20d": 0.12,
            "debt_to_ebitda": 0.12,
            "news_neg_risk_14d": 0.10,
            # Quality / stability
            "roe_ttm": 0.10,
            "fcf_yield": 0.08,
            "ev_to_ebitda": 0.06,
            # Mild trend filter
            "rs_6m_vs_benchmark": 0.08,
            "momentum_120d": 0.05,
            "rsi_14": 0.05,
            # News (avoid surprise)
            "gdelt_tone": 0.04,
            "news_tone_change": 0.04,
        },
    )

    # 6) Quality growth (long-term core)
    add(
        key="quality_growth",
        name="퀄리티 성장형",
        description="ROE/성장/재무건전성 중심의 중장기 코어. 밸류는 보조로만 반영.",
        weights={
            "roe_ttm": 0.18,
            "revenue_growth_yoy": 0.14,
            "earnings_growth_yoy": 0.16,
            "debt_to_ebitda": 0.12,
            "fcf_yield": 0.08,
            "ev_to_ebitda": 0.06,
            # Risk + trend as guardrails
            "atr_14p": 0.06,
            "rs_6m_vs_benchmark": 0.06,
            "momentum_120d": 0.05,
            # Sentiment light
            "news_neg_risk_14d": 0.05,
            "news_tone_change": 0.04,
        },
    )

    # 7) News risk avoidance
    add(
        key="news_risk_averse",
        name="뉴스 리스크 회피형",
        description="부정 이슈(소송/리콜/규제 등) 회피에 초점. 뉴스 부정 리스크와 변동성/부채를 강하게 반영.",
        weights={
            "news_neg_risk_14d": 0.20,
            "atr_14p": 0.12,
            "volatility_20d": 0.10,
            "debt_to_ebitda": 0.12,
            # Quality/Value baseline
            "roe_ttm": 0.10,
            "fcf_yield": 0.08,
            "ev_to_ebitda": 0.06,
            # Trend filter
            "rs_6m_vs_benchmark": 0.06,
            "momentum_120d": 0.05,
            # News positive as secondary (avoid overreacting)
            "gdelt_tone": 0.05,
            "news_tone_change": 0.06,
        },
    )

    session.commit()

