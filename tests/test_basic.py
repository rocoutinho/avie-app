import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import Client, User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_landing_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Fabiana Montemor".encode() in response.data or "diagn".encode() in response.data.lower()


def test_diagnostic_form_creates_lead(app, client):
    response = client.post(
        "/diagnostico",
        data={
            "full_name": "Maria Teste",
            "email": "maria@example.com",
            "phone": "11999999999",
            "instagram": "",
            "source": "instagram",
            "objetivo_profissional": "Crescer na carreira",
            "momento_carreira": "Transição de área",
            "como_quer_ser_percebida": "Confiante e competente",
            "desafios_imagem": "Não sei combinar looks para reuniões",
            "ambiente_trabalho": "Corporativo",
            "estilo_atual": "Casual",
            "cores_preferidas": "Azul e branco",
            "referencias_estilo": "",
            "orcamento_faixa": "nao_sei",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        created = Client.query.filter_by(email="maria@example.com").first()
        assert created is not None
        assert created.status == "lead"
        assert created.profile is not None
        assert created.profile.objetivo_profissional == "Crescer na carreira"


def test_dashboard_requires_login(client):
    response = client.get("/painel/", follow_redirects=True)
    assert response.status_code == 200
    assert b"Entrar" in response.data or b"login" in response.data.lower()


def test_login_and_dashboard_access(app, client):
    with app.app_context():
        user = User(name="Fabiana", email="fabiana@example.com", role="owner")
        user.set_password("senha-forte-123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login",
        data={"email": "fabiana@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Painel".encode() in response.data
