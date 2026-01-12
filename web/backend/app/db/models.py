from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from sqlmodel import Field, SQLModel

Market = Literal["KR", "US"]
FactorType = Literal["technical", "fundamental", "sentiment"]
NormalizeMethod = Literal["percentile"]


class Stock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market: str = Field(index=True)
    symbol: str = Field(index=True)
    name: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class PriceDaily(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(index=True)
    day: date = Field(index=True)
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class Fundamental(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(index=True)
    asof_date: date = Field(index=True)
    key: str = Field(index=True)
    value: float
    source: str


class NewsItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(index=True)
    published_at: datetime = Field(index=True)
    title: str
    source: Optional[str] = None
    url: str
    tone: Optional[float] = None


class FactorDefinition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None

    factor_type: str = Field(index=True)  # technical/fundamental/sentiment
    calculator: str = Field(index=True)  # e.g. momentum_120d

    weight: float = 0.0
    higher_is_better: bool = True
    normalize: str = "percentile"
    enabled: bool = True

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class FactorScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(index=True)
    day: date = Field(index=True)
    factor_id: int = Field(index=True)

    raw_value: Optional[float] = None
    score: Optional[float] = None  # 0~100


class Ranking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market: str = Field(index=True)
    day: date = Field(index=True)
    stock_id: int = Field(index=True)

    total_score: float = 0.0
    grade: str = Field(index=True)
    rank: int = Field(index=True)


class JobLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_name: str = Field(index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(index=True)  # running/success/failed
    message: Optional[str] = None


class WeightPreset(SQLModel, table=True):
    """
    Investment-style weight presets.
    config_json schema:
      {
        "mode": "strict",
        "weights": { "<factor_key>": <float>, ... },
        "enabled": { "<factor_key>": <bool>, ... }
      }
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None
    config_json: str

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

