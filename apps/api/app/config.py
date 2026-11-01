from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./data/app.db'
    data_dir: Path = Path('data')
    auth_mode: str = 'demo'
    oidc_issuer: str = ''
    oidc_audience: str = ''
    oidc_jwks_url: str = ''
    oidc_client_id: str = ''
    oidc_redirect_uri: str = 'http://127.0.0.1:8000/'
    oidc_scope: str = 'openid profile email'
    git_allowed_hosts: str = 'github.com,gitlab.com'
    local_repo_root: Path = Path('data/fixtures')
    model_mode: str = 'demo'
    model_base_url: str = ''
    model_api_key: str = ''
    model_name: str = ''
    embedding_model: str = ''
    embedding_dimensions: int = 1536
    worker_poll_seconds: float = 1


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
