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


def _normalize_database_url(url):
    # Render, Heroku e Railway entregam a connection string do Postgres com
    # o esquema antigo "postgres://" — o SQLAlchemy 2.x só aceita
    # "postgresql://". Sem isso, a conexão falha em produção mesmo com a
    # URL "certa" copiada do provedor.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = _secret_key
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get(
            "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'avie.db')}"
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies de sessão: HttpOnly sempre; Secure (só via HTTPS) em produção.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    RATELIMIT_ENABLED = True

    # E-mail transacional (confirmação de diagnóstico). Se MAIL_SERVER não
    # estiver configurado, o sistema apenas registra a mensagem no log em
    # vez de falhar — assim o formulário público funciona mesmo antes de
    # alguém configurar um provedor de e-mail.
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "contato@fabianamontemor.com.br")

    # URL pública do site, usada para gerar links absolutos (og:url, og:image)
    # nos cartões de compartilhamento no Instagram, LinkedIn, WhatsApp etc.
    # Sem isso definido, cai para o host da própria requisição (funciona bem
    # localmente; configure a URL real assim que o site tiver um domínio).
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

    # Tags de mensuração opcionais — só são inseridas se configuradas.
    # Ativar rastreamento de terceiros (cookies de conversão/retargeting)
    # deve vir acompanhado de uma atualização da Política de Privacidade.
    GA4_MEASUREMENT_ID = os.environ.get("GA4_MEASUREMENT_ID")
    META_PIXEL_ID = os.environ.get("META_PIXEL_ID")
    LINKEDIN_PARTNER_ID = os.environ.get("LINKEDIN_PARTNER_ID")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False
