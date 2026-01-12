import os


def env_str(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def env_int(name: str, default: int) -> int:
    v = env_str(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def env_bool(name: str, default: bool) -> bool:
    v = env_str(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")


class Settings:
    cors_origins: list[str]
    database_url: str

    # External data providers
    dart_api_key: str | None
    alpha_vantage_api_key: str | None

    # Admin auth (single admin)
    admin_username: str
    admin_password: str
    jwt_secret: str
    jwt_issuer: str

    # Job/scheduler
    enable_scheduler: bool
    scheduler_timezone: str
    universe_limit_kr: int
    universe_limit_us: int
    enable_news: bool
    enable_fundamentals: bool
    cookie_secure: bool
    benchmark_symbol_kr: str
    benchmark_symbol_us: str

    def __init__(self) -> None:
        cors = env_str("CORS_ORIGINS", "http://localhost:5173") or ""
        self.cors_origins = [o.strip() for o in cors.split(",") if o.strip()]

        # Use a file-based SQLite DB by default.
        self.database_url = env_str("DATABASE_URL", "sqlite:///./data/app.db") or "sqlite:///./data/app.db"

        self.dart_api_key = env_str("DART_API_KEY")
        self.alpha_vantage_api_key = env_str("ALPHAVANTAGE_API_KEY")

        self.admin_username = env_str("ADMIN_USERNAME", "admin") or "admin"
        self.admin_password = env_str("ADMIN_PASSWORD", "admin") or "admin"
        self.jwt_secret = env_str("JWT_SECRET", "dev-secret-change-me") or "dev-secret-change-me"
        self.jwt_issuer = env_str("JWT_ISSUER", "stock-ranking") or "stock-ranking"

        self.enable_scheduler = env_bool("ENABLE_SCHEDULER", False)
        self.scheduler_timezone = env_str("SCHEDULER_TIMEZONE", "Asia/Seoul") or "Asia/Seoul"

        # Default universe sizes:
        # - KR: KOSPI200
        # - US: NASDAQ100
        self.universe_limit_kr = env_int("UNIVERSE_LIMIT_KR", 200)
        self.universe_limit_us = env_int("UNIVERSE_LIMIT_US", 100)

        self.enable_news = env_bool("ENABLE_NEWS", True)
        self.enable_fundamentals = env_bool("ENABLE_FUNDAMENTALS", False)

        # Auth cookie flags
        # - dev: False (http://localhost)
        # - prod: True (https)
        self.cookie_secure = env_bool("COOKIE_SECURE", False)

        # Benchmarks for relative strength (RS) factors
        # - KR: KODEX 200 ETF (commonly available via FDR)
        # - US: QQQ ETF (NASDAQ-100 proxy)
        self.benchmark_symbol_kr = env_str("BENCHMARK_SYMBOL_KR", "069500") or "069500"
        self.benchmark_symbol_us = env_str("BENCHMARK_SYMBOL_US", "QQQ") or "QQQ"


settings = Settings()
