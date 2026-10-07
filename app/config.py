from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase (operational datastore)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Supabase (separate training-data datastore)
    training_supabase_url: str = ""
    training_supabase_service_role_key: str = ""

    # Provider API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    google_search_engine_id: str = ""
    cohere_api_key: str = ""
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""
    perplexity_api_key: str = ""
    grok_api_key: str = ""
    tavily_api_key: str = ""

    # Stripe (narrow scope: cost-paywall pre-auth + metered charge only)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Rate limiting (confirmed by Brian)
    daily_query_limit: int = 25
    burst_limit_per_minute: int = 5

    # Spending guard for the free detector: ceiling on checks per day across all visitors,
    # and the longest message accepted.
    global_daily_limit: int = 1000
    max_message_chars: int = 6000

    # Cost paywall (cost_cap_usd is a placeholder until Phase 3/4 measured data calibrates it)
    cost_cap_usd: float = 2.00
    preauth_multiplier: float = 1.5

    # Primary answering model (confirmed by Brian)
    primary_model_provider: str = "anthropic"
    primary_model_name: str = "claude-haiku-4-5-20251001"

    test_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
