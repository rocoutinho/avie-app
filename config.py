import os

from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

ENV = os.environ.get("AVIE_ENV", "development")
IS_PRODUCTION = ENV == "production"

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY não definido. Configure a variável de ambiente SECRET_KEY "
            "com um valor aleatório antes de rodar com AVIE_ENV=production."
        )
    _secret_key = "dev-chave-insegura-troque-em-producao"


class Config:
    SECRET_KEY = _secret_key
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'avie.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies de sessão: HttpOnly sempre; Secure (só via HTTPS) em produção.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    RATELIMIT_ENABLED = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False
