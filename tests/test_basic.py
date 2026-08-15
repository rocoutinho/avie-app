import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import Client, Consultation, Payment, StyleProfile, StyleReport, User


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


@pytest.fixture
def logged_in_client(app, client):
    with app.app_context():
        user = User(name="Fabiana", email="staff@example.com", role="owner")
        user.set_password("senha-forte-123")
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "staff@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )
    return client


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
            "consent": "y",
            "website": "",
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
        assert created.profile.consent_at is not None


def _diagnostic_payload(**overrides):
    payload = {
        "full_name": "Ana Teste",
        "email": "ana@example.com",
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
        "consent": "y",
        "website": "",
    }
    payload.update(overrides)
    return payload


def test_diagnostic_form_requires_consent(app, client):
    payload = _diagnostic_payload()
    del payload["consent"]
    response = client.post("/diagnostico", data=payload)
    assert response.status_code == 200  # re-renders the form with an error

    with app.app_context():
        assert Client.query.filter_by(email="ana@example.com").first() is None


def test_diagnostic_form_rejects_honeypot(app, client):
    payload = _diagnostic_payload(website="http://spam.example.com")
    response = client.post("/diagnostico", data=payload)
    assert response.status_code == 200

    with app.app_context():
        assert Client.query.filter_by(email="ana@example.com").first() is None


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


def test_client_status_updates_and_consultation_advances_pipeline(app, logged_in_client):
    response = logged_in_client.post(
        "/painel/clientes/novo",
        data={
            "full_name": "Beatriz Lima",
            "email": "beatriz@example.com",
            "phone": "11977776666",
            "instagram": "",
            "source": "indicacao",
            "status": "lead",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        created = Client.query.filter_by(email="beatriz@example.com").first()
        assert created is not None
        assert created.status == "lead"
        client_id = created.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/status",
        data={"status": "contatado"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Client, client_id).status == "contatado"

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/consultas/nova",
        data={
            "tipo": "diagnostico_gratuito",
            "scheduled_at": "2026-09-01T14:00",
            "duration_minutes": "60",
            "status": "agendada",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        client_obj = db.session.get(Client, client_id)
        # agendar uma consulta avança o cliente no funil automaticamente
        assert client_obj.status == "diagnostico_agendado"
        assert Consultation.query.filter_by(client_id=client_id).count() == 1


def test_report_draft_prefills_from_profile_and_send_advances_pipeline(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Carla Nunes", email="carla@example.com", status="diagnostico_concluido")
        db.session.add(c)
        db.session.flush()
        profile = StyleProfile(
            client_id=c.id,
            objetivo_profissional="Virar sócia",
            momento_carreira="Consolidando autoridade no mercado",
            como_quer_ser_percebida="Estratégica e acessível",
            desafios_imagem="Guarda-roupa não combina com o novo cargo",
        )
        db.session.add(profile)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.get(f"/painel/clientes/{client_id}/relatorios/novo")
    assert response.status_code == 200
    assert "Consolidando autoridade no mercado".encode() in response.data

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/relatorios/novo",
        data={
            "title": "Diagnóstico — Carla Nunes",
            "content": "Conteúdo final revisado pela consultora.",
            "status": "enviado",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        report = StyleReport.query.filter_by(client_id=client_id).first()
        assert report is not None
        assert report.status == "enviado"
        assert report.sent_at is not None
        assert db.session.get(Client, client_id).status == "proposta_enviada"


def test_utm_attribution_prefills_source_and_survives_redirect(app, client):
    client.get("/?utm_source=instagram&utm_medium=paid_social&utm_campaign=lancamento_agosto")
    response = client.get("/diagnostico")
    html = response.get_data(as_text=True)
    assert '<option selected value="instagram">' in html
    assert "lancamento_agosto" in html


def test_gclid_and_fbclid_infer_source_without_explicit_utm(app):
    with app.test_client() as google_client:
        google_client.get("/diagnostico?gclid=abc123")
        html = google_client.get("/diagnostico").get_data(as_text=True)
        assert '<option selected value="google">' in html

    with app.test_client() as meta_client:
        meta_client.get("/diagnostico?fbclid=xyz789")
        html = meta_client.get("/diagnostico").get_data(as_text=True)
        assert '<option selected value="instagram">' in html


def test_partial_lead_saves_contact_without_sensitive_profile(app, client):
    response = client.post(
        "/diagnostico/lead-parcial",
        json={
            "full_name": "Camila Parcial",
            "email": "camila.parcial@example.com",
            "phone": "11988887777",
            "source": "instagram",
            "utm_source": "instagram",
            "utm_campaign": "lancamento_agosto",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}

    with app.app_context():
        created = Client.query.filter_by(email="camila.parcial@example.com").first()
        assert created is not None
        assert created.status == "lead"
        assert created.profile is None
        assert created.utm_campaign == "lancamento_agosto"


def test_partial_lead_and_full_submit_converge_on_same_client(app, client):
    client.get("/?utm_source=instagram&utm_campaign=lancamento_agosto")
    client.post(
        "/diagnostico/lead-parcial",
        json={
            "full_name": "Bia Completa",
            "email": "bia.completa@example.com",
            "phone": "11977776666",
            "source": "instagram",
            "utm_source": "instagram",
            "utm_campaign": "lancamento_agosto",
        },
    )
    with app.app_context():
        partial = Client.query.filter_by(email="bia.completa@example.com").first()
        partial_id = partial.id
        assert partial.profile is None

    client.post(
        "/diagnostico",
        data=_diagnostic_payload(
            full_name="Bia Completa",
            email="bia.completa@example.com",
            utm_source="instagram",
            utm_campaign="lancamento_agosto",
        ),
        follow_redirects=True,
    )

    with app.app_context():
        clients_with_email = Client.query.filter_by(email="bia.completa@example.com").all()
        assert len(clients_with_email) == 1
        final = clients_with_email[0]
        assert final.id == partial_id
        assert final.profile is not None
        assert final.utm_campaign == "lancamento_agosto"


def test_payment_creation(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Diana Alves", email="diana@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/pagamentos/novo",
        data={
            "description": "Consultoria de Imagem — pacote completo",
            "amount": "1500.00",
            "status": "pendente",
            "due_date": "2026-09-15",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        payment = Payment.query.filter_by(client_id=client_id).first()
        assert payment is not None
        assert payment.status == "pendente"
        assert float(payment.amount) == 1500.00


def test_full_client_journey_from_instagram_ad_to_delivered_dossier(app, client):
    """Ponta a ponta com uma cliente fictícia: chega por um anúncio no
    Instagram, abandona o formulário na 1ª etapa (e ainda vira lead),
    volta e completa o diagnóstico, é qualificada e agendada pela equipe,
    e recebe o dossiê (relatório personalizado) ao final."""
    persona_email = "marina.duarte@example.com"

    # 1. Clica no anúncio do Instagram e chega na landing com atribuição de campanha.
    response = client.get(
        "/?utm_source=instagram&utm_medium=paid_social&utm_campaign=setembro_lideranca"
    )
    assert response.status_code == 200

    # 2. Abre o diagnóstico, preenche só a etapa 1 (dados de contato) e abandona.
    #    Isso já precisa criar um lead mínimo, sem nenhuma resposta sensível.
    response = client.post(
        "/diagnostico/lead-parcial",
        json={
            "full_name": "Marina Duarte",
            "email": persona_email,
            "phone": "11955554444",
            "source": "instagram",
            "utm_source": "instagram",
            "utm_medium": "paid_social",
            "utm_campaign": "setembro_lideranca",
        },
    )
    assert response.status_code == 200

    with app.app_context():
        partial = Client.query.filter_by(email=persona_email).first()
        assert partial is not None
        assert partial.status == "lead"
        assert partial.profile is None
        assert partial.utm_campaign == "setembro_lideranca"
        partial_id = partial.id

    # 3. No dia seguinte, ela volta pelo mesmo link e termina o diagnóstico completo.
    response = client.post(
        "/diagnostico",
        data=_diagnostic_payload(
            full_name="Marina Duarte",
            email=persona_email,
            phone="11955554444",
            source="instagram",
            objetivo_profissional="Ser vista como uma liderança natural na nova gerência, sem perder minha essência",
            momento_carreira="Fui promovida a gerente há um mês e ainda estou me adaptando ao peso da nova posição",
            como_quer_ser_percebida="Confiante, estratégica e acessível para o time",
            desafios_imagem="Meu guarda-roupa é do cargo anterior — mais despojado — e não reflete a nova posição",
            ambiente_trabalho="Escritório híbrido, reuniões de diretoria semanais",
            estilo_atual="Casual com toques criativos",
            cores_preferidas="Verde petróleo, off-white e tons terrosos",
            referencias_estilo="Executivas com estilo minimalista e atemporal",
            orcamento_faixa="3000_6000",
            utm_source="instagram",
            utm_medium="paid_social",
            utm_campaign="setembro_lideranca",
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        after_diagnostic = Client.query.filter_by(email=persona_email).first()
        assert after_diagnostic.id == partial_id  # não duplicou: mesmo lead, agora completo
        assert after_diagnostic.status == "diagnostico_concluido"
        assert after_diagnostic.profile is not None
        assert after_diagnostic.profile.consent_at is not None
        assert after_diagnostic.utm_campaign == "setembro_lideranca"

    # 4. A equipe (Fabiana) entra no painel e vê o lead qualificado.
    with app.app_context():
        staff = User(name="Fabiana", email="fabiana.staff@example.com", role="owner")
        staff.set_password("senha-forte-123")
        db.session.add(staff)
        db.session.commit()
    client.post(
        "/login",
        data={"email": "fabiana.staff@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )

    response = client.get(f"/painel/clientes/{partial_id}")
    assert response.status_code == 200
    assert "Marina Duarte".encode() in response.data
    assert "Instagram".encode() in response.data
    assert "setembro_lideranca".encode() in response.data

    # 5. Fabiana liga, qualifica e marca como "Contatado".
    client.post(
        f"/painel/clientes/{partial_id}/status",
        data={"status": "contatado"},
        follow_redirects=True,
    )

    # 6. Agenda a sessão de consultoria — o funil avança sozinho.
    response = client.post(
        f"/painel/clientes/{partial_id}/consultas/nova",
        data={
            "tipo": "consultoria_imagem",
            "scheduled_at": "2026-09-10T15:00",
            "duration_minutes": "90",
            "status": "agendada",
            "notes": "Primeira sessão — trazer peças-chave do guarda-roupa atual.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        qualified = Client.query.filter_by(email=persona_email).first()
        assert qualified.status == "diagnostico_agendado"
        assert Consultation.query.filter_by(client_id=partial_id).count() == 1

    # 7. Depois da consulta, Fabiana gera o rascunho do dossiê a partir do
    #    diagnóstico, personaliza as recomendações e envia para a cliente.
    response = client.get(f"/painel/clientes/{partial_id}/relatorios/novo")
    assert response.status_code == 200
    draft_html = response.get_data(as_text=True)
    assert "liderança natural" in draft_html  # rascunho puxou as respostas do diagnóstico

    response = client.post(
        f"/painel/clientes/{partial_id}/relatorios/novo",
        data={
            "title": "Dossiê de Posicionamento Profissional e Estilo — Marina Duarte",
            "content": (
                "Relatório de Posicionamento Profissional e Estilo\n"
                "Preparado especialmente para Marina Duarte\n\n"
                "1. Seu momento atual\nRecém-promovida a gerente...\n\n"
                "6. Recomendações e próximos passos\n"
                "Paleta em verde petróleo e off-white para transmitir autoridade "
                "com leveza; 5 peças-chave para reuniões de diretoria;"
                " comunicação não-verbal para liderar com presença."
            ),
            "status": "enviado",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # 8. Dossiê entregue: relatório marcado como enviado e cliente em "Proposta Enviada".
    with app.app_context():
        delivered = Client.query.filter_by(email=persona_email).first()
        report = StyleReport.query.filter_by(client_id=partial_id).first()
        assert report is not None
        assert report.status == "enviado"
        assert report.sent_at is not None
        assert "Paleta em verde petróleo" in report.content
        assert delivered.status == "proposta_enviada"
