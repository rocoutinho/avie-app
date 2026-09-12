import io
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from journey import build_journey
from models import (
    BlogPost,
    Client,
    ClosetItem,
    Consultation,
    Ebook,
    Look,
    Payment,
    ShoppingListItem,
    StyleAssessment,
    StyleProfile,
    StyleReport,
    User,
)


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


@pytest.fixture
def marketing_client(app, client):
    with app.app_context():
        user = User(name="Fabiana Marketing", email="marketing@example.com", role="marketing")
        user.set_password("senha-forte-123")
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "marketing@example.com", "password": "senha-forte-123"},
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


def test_sessions_list_shows_all_consultations_with_status_filter(app, logged_in_client, client):
    with app.app_context():
        lead = Client(full_name="Diana Sessions", email="diana-sessions@example.com", status="lead")
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id
        db.session.add(
            Consultation(
                client_id=lead_id,
                tipo="diagnostico_gratuito",
                scheduled_at=datetime(2026, 9, 1, 14, 0),
                status="agendada",
            )
        )
        db.session.add(
            Consultation(
                client_id=lead_id,
                tipo="consultoria_imagem",
                scheduled_at=datetime(2026, 8, 20, 10, 0),
                status="realizada",
            )
        )
        db.session.commit()

    response = logged_in_client.get("/painel/sessoes/")
    assert response.status_code == 200
    assert b"Diana Sessions" in response.data
    assert response.data.count(b"Diana Sessions") == 2

    response = logged_in_client.get("/painel/sessoes/?status=realizada")
    assert response.status_code == 200
    assert response.data.count(b"Diana Sessions") == 1

    # Cliente (não-staff) não acessa a listagem interna.
    with app.app_context():
        portal_client = Client(full_name="Cliente Comum", email="cliente-comum@example.com", status="lead")
        portal_client.set_password("senha-cliente-123")
        db.session.add(portal_client)
        db.session.commit()

    client.get("/logout")
    client.post(
        "/login",
        data={"email": "cliente-comum@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/painel/sessoes/", follow_redirects=False)
    assert response.status_code == 403


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


def test_payments_list_shows_all_payments_with_status_filter(app, logged_in_client, client):
    with app.app_context():
        lead = Client(full_name="Elisa Payments", email="elisa-payments@example.com", status="cliente_ativo")
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id
        db.session.add(
            Payment(
                client_id=lead_id,
                description="Sinal da consultoria",
                amount=500,
                status="pago",
            )
        )
        db.session.add(
            Payment(
                client_id=lead_id,
                description="Saldo da consultoria",
                amount=1000,
                status="pendente",
            )
        )
        db.session.commit()

    response = logged_in_client.get("/painel/pagamentos/")
    assert response.status_code == 200
    assert b"Elisa Payments" in response.data
    assert response.data.count(b"Elisa Payments") == 2

    response = logged_in_client.get("/painel/pagamentos/?status=pago")
    assert response.status_code == 200
    assert response.data.count(b"Elisa Payments") == 1

    # Cliente (não-staff) não acessa a listagem interna.
    with app.app_context():
        portal_client = Client(full_name="Cliente Pagamentos", email="cliente-pagamentos@example.com", status="lead")
        portal_client.set_password("senha-cliente-123")
        db.session.add(portal_client)
        db.session.commit()

    client.get("/logout")
    client.post(
        "/login",
        data={"email": "cliente-pagamentos@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/painel/pagamentos/", follow_redirects=False)
    assert response.status_code == 403


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


def test_seed_admin_noop_without_env_vars(app, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["seed-admin"])

    assert "não definidos" in result.output
    with app.app_context():
        assert User.query.count() == 0


def test_seed_admin_creates_user_and_is_idempotent(app, monkeypatch):
    monkeypatch.setenv("ADMIN_NAME", "Fabiana Montemor")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "senha-bem-forte-123")
    monkeypatch.setenv("ADMIN_ROLE", "owner")
    runner = app.test_cli_runner()

    first = runner.invoke(args=["seed-admin"])
    assert "criado" in first.output
    with app.app_context():
        assert User.query.filter_by(email="admin@example.com").count() == 1

    second = runner.invoke(args=["seed-admin"])
    assert "já existe" in second.output
    with app.app_context():
        assert User.query.filter_by(email="admin@example.com").count() == 1


def _blog_post_payload(**overrides):
    payload = {
        "title": "5 erros de imagem que sabotam sua autoridade",
        "slug": "5-erros-de-imagem",
        "excerpt": "Erros comuns de imagem profissional e como corrigi-los.",
        "cover_image_url": "",
        "author_name": "Fabiana Montemor",
        "body_markdown": "## Introdução\n\nTexto de teste do artigo.",
    }
    payload.update(overrides)
    return payload


def test_marketing_creates_post_but_cannot_approve_it(app, marketing_client):
    response = marketing_client.post(
        "/painel/blog/novo", data=_blog_post_payload(), follow_redirects=True
    )
    assert response.status_code == 200

    with app.app_context():
        post = BlogPost.query.filter_by(slug="5-erros-de-imagem").first()
        assert post is not None
        assert post.status == "rascunho"
        post_id = post.id

    response = marketing_client.post(
        f"/painel/blog/{post_id}/enviar-revisao", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(BlogPost, post_id).status == "em_revisao"

    # Marketing não pode aprovar — só o owner.
    response = marketing_client.post(f"/painel/blog/{post_id}/aprovar")
    assert response.status_code == 403

    # A página pública ainda não existe, porque não foi aprovada.
    response = marketing_client.get("/blog/5-erros-de-imagem")
    assert response.status_code == 404


def test_owner_approves_post_and_it_goes_live(app, logged_in_client):
    with app.app_context():
        marketing_user = User(name="Fabiana Marketing", email="mkt-blog@example.com", role="marketing")
        marketing_user.set_password("senha-forte-123")
        db.session.add(marketing_user)
        db.session.commit()
        post = BlogPost(
            slug="posicionamento-profissional",
            title="Como construir posicionamento profissional",
            excerpt="Um guia prático.",
            body_markdown="Conteúdo de teste.",
            status="em_revisao",
            created_by_id=marketing_user.id,
        )
        db.session.add(post)
        db.session.commit()
        post_id = post.id

    response = logged_in_client.post(f"/painel/blog/{post_id}/aprovar", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        approved = db.session.get(BlogPost, post_id)
        assert approved.status == "publicado"
        assert approved.published_at is not None
        assert approved.reviewed_by_id is not None

    response = logged_in_client.get("/blog/posicionamento-profissional")
    assert response.status_code == 200
    assert "Como construir posicionamento profissional".encode() in response.data

    response = logged_in_client.get("/blog")
    assert response.status_code == 200
    assert "Como construir posicionamento profissional".encode() in response.data


def test_owner_rejects_post_back_to_draft_with_note(app, logged_in_client):
    with app.app_context():
        marketing_user = User(name="Fabiana Marketing", email="mkt-blog2@example.com", role="marketing")
        marketing_user.set_password("senha-forte-123")
        db.session.add(marketing_user)
        db.session.commit()
        post = BlogPost(
            slug="linkedin-para-executivos",
            title="LinkedIn para executivos",
            excerpt="Como usar o LinkedIn a favor da sua imagem.",
            body_markdown="Conteúdo de teste.",
            status="em_revisao",
            created_by_id=marketing_user.id,
        )
        db.session.add(post)
        db.session.commit()
        post_id = post.id

    response = logged_in_client.post(
        f"/painel/blog/{post_id}/recusar",
        data={"review_note": "Ajustar o título"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        rejected = db.session.get(BlogPost, post_id)
        assert rejected.status == "rascunho"
        assert rejected.review_note == "Ajustar o título"

    response = logged_in_client.get("/blog/linkedin-para-executivos")
    assert response.status_code == 404


def test_blog_markdown_renders_to_html(app, logged_in_client):
    with app.app_context():
        post = BlogPost(
            slug="artigo-markdown",
            title="Artigo com Markdown",
            excerpt="Teste de renderização.",
            body_markdown="## Subtítulo\n\nTexto em **negrito** e uma lista:\n\n- Item um\n- Item dois",
            status="publicado",
            published_at=datetime.utcnow(),
            created_by_id=User.query.first().id,
        )
        db.session.add(post)
        db.session.commit()

    response = logged_in_client.get("/blog/artigo-markdown")
    assert response.status_code == 200
    assert b"<h2>Subt\xc3\xadtulo</h2>" in response.data
    assert b"<strong>negrito</strong>" in response.data
    assert b"<li>Item um</li>" in response.data


def test_ebook_landing_shows_placeholder_without_active_ebook(client):
    response = client.get("/ebook")
    assert response.status_code == 200
    assert "Em breve".encode() in response.data


def _ebook_payload(**overrides):
    payload = {
        "title": "Guia de Posicionamento Profissional",
        "description": "Um guia prático para alinhar imagem e carreira.",
        "cover_image_url": "",
        "file_url": "https://drive.google.com/file/d/teste/view",
        "active": "y",
    }
    payload.update(overrides)
    return payload


def test_owner_creates_ebook_and_activating_another_deactivates_it(app, logged_in_client):
    response = logged_in_client.post("/painel/ebooks/novo", data=_ebook_payload(), follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        first = Ebook.query.filter_by(title="Guia de Posicionamento Profissional").first()
        assert first is not None
        assert first.active is True

    response = logged_in_client.post(
        "/painel/ebooks/novo",
        data=_ebook_payload(title="Segundo Guia"),
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        first_reloaded = db.session.get(Ebook, first.id)
        second = Ebook.query.filter_by(title="Segundo Guia").first()
        assert first_reloaded.active is False
        assert second.active is True

    response = logged_in_client.get("/ebook")
    assert response.status_code == 200
    assert b"Segundo Guia" in response.data


def test_ebook_download_creates_lead_and_redirects_to_success(app, client):
    with app.app_context():
        owner = User(name="Fabiana", email="staff-ebook1@example.com", role="owner")
        owner.set_password("senha-forte-123")
        db.session.add(owner)
        db.session.commit()
        ebook = Ebook(
            title="Guia de Imagem",
            description="Descrição de teste.",
            file_url="https://drive.google.com/file/d/teste2/view",
            active=True,
            created_by_id=owner.id,
        )
        db.session.add(ebook)
        db.session.commit()

    response = client.post(
        "/ebook",
        data={
            "full_name": "Carlos Lead",
            "email": "carlos@example.com",
            "phone": "11988887777",
            "wants_diagnostic": "y",
            "website": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Guia de Imagem".encode() in response.data

    with app.app_context():
        lead = Client.query.filter_by(email="carlos@example.com").first()
        assert lead is not None
        assert lead.source == "ebook"
        assert "diagnóstico" in lead.notes.lower()


def test_ebook_download_rejects_honeypot(app, client):
    with app.app_context():
        owner = User(name="Fabiana", email="staff-ebook2@example.com", role="owner")
        owner.set_password("senha-forte-123")
        db.session.add(owner)
        db.session.commit()
        ebook = Ebook(
            title="Guia de Imagem",
            description="Descrição de teste.",
            file_url="https://drive.google.com/file/d/teste3/view",
            active=True,
            created_by_id=owner.id,
        )
        db.session.add(ebook)
        db.session.commit()

    response = client.post(
        "/ebook",
        data={
            "full_name": "Bot",
            "email": "bot@example.com",
            "phone": "11900000000",
            "website": "http://spam.example.com",
        },
    )
    assert response.status_code == 200

    with app.app_context():
        assert Client.query.filter_by(email="bot@example.com").first() is None


def test_client_without_password_cannot_login(app, client):
    with app.app_context():
        lead = Client(full_name="Sem Acesso", email="semacesso@example.com", status="lead")
        db.session.add(lead)
        db.session.commit()

    response = client.post(
        "/login",
        data={"email": "semacesso@example.com", "password": "qualquer-coisa"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "inválidos".encode() in response.data


def test_staff_sets_client_password_and_client_logs_into_own_area(app, logged_in_client, client):
    with app.app_context():
        lead = Client(full_name="Carla Cliente", email="carla-portal@example.com", status="lead")
        db.session.add(lead)
        db.session.commit()
        client_id = lead.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/senha",
        data={"password": "senha-cliente-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        updated = db.session.get(Client, client_id)
        assert updated.check_password("senha-cliente-123") is True

    # logged_in_client e client são o mesmo cliente de teste (mesmos
    # cookies) — sai da sessão de staff antes de logar como cliente.
    client.get("/logout")

    response = client.post(
        "/login",
        data={"email": "carla-portal@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Olá, Carla".encode() in response.data

    # Cliente não acessa o painel interno.
    response = client.get("/painel/", follow_redirects=False)
    assert response.status_code == 403

    response = client.get("/painel/clientes/", follow_redirects=False)
    assert response.status_code == 403


def test_removing_client_access_blocks_future_login(app, logged_in_client, client):
    with app.app_context():
        lead = Client(full_name="Acesso Temporário", email="temp-portal@example.com", status="lead")
        lead.set_password("senha-temp-123")
        db.session.add(lead)
        db.session.commit()
        client_id = lead.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/senha/remover", follow_redirects=True
    )
    assert response.status_code == 200

    client.get("/logout")
    response = client.post(
        "/login",
        data={"email": "temp-portal@example.com", "password": "senha-temp-123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "inválidos".encode() in response.data


def _dossie_payload(**overrides):
    payload = {
        "full_name": "Nova Cliente Dossiê",
        "email": "dossie-nova@example.com",
        "phone": "11988887777",
        "dossie_title": "Diagnóstico de Estilo — Nova Cliente",
        "estilo_pessoal": "Estilo clássico com toques contemporâneos.",
        "proporcoes": "Silhueta retangular, valorizar cintura.",
        "coloracao": "Paleta de inverno — cores frias e contrastadas.",
        "visagismo": "",
    }
    payload.update(overrides)
    return payload


def test_staff_creates_client_with_dossie(app, logged_in_client):
    response = logged_in_client.post(
        "/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True
    )
    assert response.status_code == 200
    assert "Cadastro de Nova Cliente Dossiê concluído".encode() in response.data

    with app.app_context():
        created = Client.query.filter_by(email="dossie-nova@example.com").first()
        assert created is not None
        assert created.status == "cliente_concluido"
        assert created.password_hash is not None
        assert created.password_reset_token is not None
        assert created.password_reset_token_valid() is True

        reports = StyleReport.query.filter_by(client_id=created.id).all()
        assert len(reports) == 1
        assert reports[0].status == "enviado"
        assert reports[0].estilo_pessoal == "Estilo clássico com toques contemporâneos."
        assert reports[0].proporcoes == "Silhueta retangular, valorizar cintura."
        assert reports[0].coloracao == "Paleta de inverno — cores frias e contrastadas."
        assert reports[0].visagismo is None
        assert reports[0].sent_at is not None


def test_dossie_onboarding_upserts_existing_client_by_email(app, logged_in_client):
    with app.app_context():
        existing = Client(
            full_name="Nome Antigo", email="ja-existe@example.com", status="lead", source="instagram"
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

    response = logged_in_client.post(
        "/painel/clientes/novo-com-dossie",
        data=_dossie_payload(full_name="Nome Atualizado", email="ja-existe@example.com"),
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        updated = db.session.get(Client, existing_id)
        assert updated.full_name == "Nome Atualizado"
        # A origem original não é sobrescrita pelo onboarding.
        assert updated.source == "instagram"
        assert len(Client.query.filter_by(email="ja-existe@example.com").all()) == 1


def test_dossie_reset_link_lets_client_set_own_password_and_login(app, logged_in_client, client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)

    with app.app_context():
        created = Client.query.filter_by(email="dossie-nova@example.com").first()
        token = created.password_reset_token

    client.get("/logout")

    response = client.post(
        f"/redefinir-senha/{token}",
        data={"password": "minha-nova-senha", "confirm": "minha-nova-senha"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        updated = Client.query.filter_by(email="dossie-nova@example.com").first()
        assert updated.check_password("minha-nova-senha") is True
        assert updated.password_reset_token is None

    response = client.post(
        "/login",
        data={"email": "dossie-nova@example.com", "password": "minha-nova-senha"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Olá, Nova".encode() in response.data


def test_reset_password_rejects_invalid_token(client):
    response = client.get("/redefinir-senha/token-invalido", follow_redirects=True)
    assert response.status_code == 200
    assert "expirou".encode() in response.data or "Entrar".encode() in response.data


def test_dossie_client_sees_service_cards_instead_of_diagnostic_cta(app, logged_in_client, client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)

    client.get("/logout")
    client.post(
        "/login", data={"email": "dossie-nova@example.com", "password": "senha-nao-importa"}
    )

    with app.app_context():
        created = Client.query.filter_by(email="dossie-nova@example.com").first()
        created.set_password("senha-cliente-final")
        db.session.commit()

    client.post(
        "/login",
        data={"email": "dossie-nova@example.com", "password": "senha-cliente-final"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/diagnostico")
    assert response.status_code == 200
    assert "Fazer meu diagnóstico".encode() not in response.data
    assert "Estilo".encode() in response.data
    assert "Cores".encode() in response.data
    assert "Estilo clássico com toques contemporâneos.".encode() in response.data
    # Visagismo e Arquétipos ficaram em branco no dossiê — não devem virar cards vazios.
    assert "Visagismo".encode() not in response.data
    assert "Arquétipos".encode() not in response.data


def test_resubmitting_dossie_onboarding_updates_same_report(app, logged_in_client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)
    logged_in_client.post(
        "/painel/clientes/novo-com-dossie",
        data=_dossie_payload(estilo_pessoal="Estilo atualizado na segunda submissão."),
        follow_redirects=True,
    )

    with app.app_context():
        client_obj = Client.query.filter_by(email="dossie-nova@example.com").first()
        assert client_obj.status == "cliente_concluido"
        reports = StyleReport.query.filter_by(client_id=client_obj.id).all()
        assert len(reports) == 1
        assert reports[0].estilo_pessoal == "Estilo atualizado na segunda submissão."


def test_staff_edits_dossie_and_client_area_reflects_it(app, logged_in_client, client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)
    with app.app_context():
        client_obj = Client.query.filter_by(email="dossie-nova@example.com").first()
        client_id = client_obj.id
        client_obj.set_password("senha-cliente-final")
        db.session.commit()

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/dossie/editar",
        data={
            "dossie_title": "Diagnóstico de Estilo — Nova Cliente",
            "pdf_url": "https://example.com/dossie.pdf",
            "estilo_pessoal": "Estilo editado depois do cadastro.",
            "proporcoes": "Silhueta retangular, valorizar cintura.",
            "coloracao": "Paleta de inverno — cores frias e contrastadas.",
            "visagismo": "",
            "arquetipos": "Arquétipo Sábia.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Baixar PDF do dossiê".encode() in response.data

    with app.app_context():
        report = db.session.get(Client, client_id).dossie_report
        assert report.estilo_pessoal == "Estilo editado depois do cadastro."
        assert report.arquetipos == "Arquétipo Sábia."
        assert report.pdf_url == "https://example.com/dossie.pdf"

    logged_in_client.get("/logout")
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "dossie-nova@example.com", "password": "senha-cliente-final"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/diagnostico")
    assert "Estilo editado depois do cadastro.".encode() in response.data
    assert "Arquétipo Sábia.".encode() in response.data


def test_edit_report_redirects_dossie_report_to_edit_dossie(app, logged_in_client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)
    with app.app_context():
        client_obj = Client.query.filter_by(email="dossie-nova@example.com").first()
        client_id = client_obj.id
        report_id = client_obj.dossie_report.id

    response = logged_in_client.get(
        f"/painel/clientes/{client_id}/relatorios/{report_id}/editar", follow_redirects=False
    )
    assert response.status_code == 302
    assert f"/painel/clientes/{client_id}/dossie/editar" in response.headers["Location"]


def test_delete_report_removes_preliminary_report_but_blocks_dossie(app, logged_in_client):
    logged_in_client.post("/painel/clientes/novo-com-dossie", data=_dossie_payload(), follow_redirects=True)
    with app.app_context():
        client_obj = Client.query.filter_by(email="dossie-nova@example.com").first()
        client_id = client_obj.id
        dossie_report_id = client_obj.dossie_report.id

        extra = StyleReport(
            client_id=client_id, title="Diagnóstico preliminar — teste", content="rascunho", status="rascunho"
        )
        db.session.add(extra)
        db.session.commit()
        extra_id = extra.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/relatorios/{extra_id}/excluir", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(StyleReport, extra_id) is None

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/relatorios/{dossie_report_id}/excluir", follow_redirects=False
    )
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(StyleReport, dossie_report_id) is not None


def test_analytics_aggregates_clients_payments_and_sessions(app, logged_in_client, client):
    with app.app_context():
        active = Client(
            full_name="Fernanda Analytics", email="fernanda-analytics@example.com",
            status="cliente_ativo", source="instagram",
        )
        lead = Client(
            full_name="Gustavo Analytics", email="gustavo-analytics@example.com",
            status="lead", source="google",
        )
        db.session.add_all([active, lead])
        db.session.commit()
        active_id = active.id

        db.session.add(Payment(client_id=active_id, description="Pago", amount=1000, status="pago"))
        db.session.add(Payment(client_id=active_id, description="Pendente", amount=200, status="pendente"))
        db.session.add(Payment(client_id=active_id, description="Atrasado", amount=50, status="atrasado"))
        db.session.add(
            Consultation(
                client_id=active_id,
                tipo="consultoria_imagem",
                scheduled_at=datetime(2026, 9, 1, 14, 0),
                status="agendada",
            )
        )
        db.session.commit()

    response = logged_in_client.get("/painel/analytics/")
    assert response.status_code == 200
    assert "R$ 1000.00".encode() in response.data
    assert "R$ 250.00".encode() in response.data  # 200 pendente + 50 atrasado

    # Cliente (não-staff) não acessa a listagem interna.
    with app.app_context():
        portal_client = Client(full_name="Cliente Analytics", email="cliente-analytics@example.com", status="lead")
        portal_client.set_password("senha-cliente-123")
        db.session.add(portal_client)
        db.session.commit()

    client.get("/logout")
    client.post(
        "/login",
        data={"email": "cliente-analytics@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/painel/analytics/", follow_redirects=False)
    assert response.status_code == 403


def test_staff_navbar_links_to_studio_and_business_groups(logged_in_client):
    response = logged_in_client.get("/painel/")
    assert response.status_code == 200
    for href in (
        b'href="/painel/clientes/"',
        b'href="/painel/sessoes/"',
        b'href="/painel/pagamentos/"',
        b'href="/painel/analytics/"',
        b'href="/painel/blog/"',
        b'href="/painel/ebooks/"',
    ):
        assert href in response.data
    assert b'href="/painel/dossies/"' not in response.data


def test_staff_saves_style_notes_via_client_edit(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Helena Estilo", email="helena-estilo@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/editar",
        data={
            "full_name": "Helena Estilo",
            "email": "helena-estilo@example.com",
            "phone": "",
            "instagram": "",
            "source": "indicacao",
            "status": "cliente_ativo",
            "notes": "",
            "style_notes": "Silhueta ampulheta, rosto oval, prefere tons quentes.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Silhueta ampulheta".encode() in response.data

    with app.app_context():
        assert db.session.get(Client, client_id).style_notes == "Silhueta ampulheta, rosto oval, prefere tons quentes."


def test_staff_manages_closet_items_and_client_sees_them_read_only(app, logged_in_client, client):
    with app.app_context():
        c = Client(full_name="Isabela Closet", email="isabela-closet@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/closet/novo",
        data={
            "category": "blazer",
            "description": "Blazer preto alfaiataria",
            "photo_url": "https://example.com/blazer.jpg",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Blazer preto alfaiataria".encode() in response.data

    with app.app_context():
        item = ClosetItem.query.filter_by(client_id=client_id).first()
        assert item is not None
        assert item.category == "blazer"
        item_id = item.id

    # Aparece na área do cliente, sem opção de editar/excluir.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "isabela-closet@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/looks")
    assert response.status_code == 200
    assert "Blazer preto alfaiataria".encode() in response.data
    assert b"Excluir" not in response.data

    # Volta como staff (mesmos cookies do fixture logged_in_client) e remove a peça.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "staff@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )
    response = client.post(
        f"/painel/clientes/{client_id}/closet/{item_id}/excluir", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ClosetItem, item_id) is None


def test_staff_manages_shopping_list_and_client_sees_it_read_only(app, logged_in_client, client):
    with app.app_context():
        c = Client(full_name="Julia Compras", email="julia-compras@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/lista-compras/novo",
        data={"category": "sapato", "description": "Scarpin nude", "motivo": "Falta um sapato neutro pra fechar looks de trabalho.", "notes": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Scarpin nude".encode() in response.data

    with app.app_context():
        item = ShoppingListItem.query.filter_by(client_id=client_id).first()
        assert item is not None
        assert item.status == "recomendada"
        item_id = item.id

    # Avança o status pra comprada.
    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/lista-compras/{item_id}/status",
        data={"status": "comprada"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id).status == "comprada"

    # Aparece na área do cliente, sem opção de editar/excluir.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "julia-compras@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/looks")
    assert response.status_code == 200
    assert "Scarpin nude".encode() in response.data
    assert "Falta um sapato neutro".encode() in response.data
    assert "Comprada".encode() in response.data
    assert b"Excluir" not in response.data

    # Volta como staff e remove a sugestão.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "staff@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )
    response = client.post(
        f"/painel/clientes/{client_id}/lista-compras/{item_id}/excluir", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id) is None


def test_shopping_list_item_status_rejects_invalid_value(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Rita Compras", email="rita-compras@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        item = ShoppingListItem(client_id=c.id, category="sapato", description="Scarpin nude")
        db.session.add(item)
        db.session.commit()
        client_id, item_id = c.id, item.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/lista-compras/{item_id}/status",
        data={"status": "nao-existe"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id).status == "recomendada"


def test_staff_edits_shopping_list_item_with_purchase_link(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Marina Link", email="marina-link@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        item = ShoppingListItem(client_id=c.id, category="sapato", description="Scarpin nude")
        db.session.add(item)
        db.session.commit()
        client_id, item_id = c.id, item.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/lista-compras/{item_id}/editar",
        data={
            "category": "sapato",
            "description": "Scarpin nude",
            "motivo": "Fecha looks de trabalho.",
            "photo_url": "https://example.com/scarpin.jpg",
            "link_compra": "https://parceiro.example.com/scarpin-nude",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        item = db.session.get(ShoppingListItem, item_id)
        assert item.link_compra == "https://parceiro.example.com/scarpin-nude"
        assert item.photo_url == "https://example.com/scarpin.jpg"


def test_client_accepts_shopping_list_item_recommendation(app, client):
    with app.app_context():
        c = Client(full_name="Paula Aceita", email="paula-aceita@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        with_link = ShoppingListItem(
            client_id=c.id,
            category="sapato",
            description="Scarpin nude",
            link_compra="https://parceiro.example.com/scarpin-nude",
        )
        no_link = ShoppingListItem(client_id=c.id, category="acessorio", description="Bolsa estruturada")
        db.session.add_all([with_link, no_link])
        db.session.commit()
        item_id_with_link, item_id_no_link = with_link.id, no_link.id

    client.post(
        "/login",
        data={"email": "paula-aceita@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )

    response = client.get("/minha-area/looks")
    assert "Aceitar recomendação".encode() in response.data
    assert "Ver produto".encode() in response.data

    response = client.post(
        f"/minha-area/lista-compras/{item_id_with_link}/aceitar", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id_with_link).status == "aprovada"

    # Sem link_compra, aceitar não tem efeito (rota só existe pro fluxo com link).
    response = client.post(
        f"/minha-area/lista-compras/{item_id_no_link}/aceitar", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id_no_link).status == "recomendada"


def test_client_cannot_accept_another_clients_shopping_list_item(app, client):
    with app.app_context():
        owner = Client(full_name="Dona Item", email="dona-item@example.com", status="cliente_ativo")
        intruder = Client(full_name="Outra Cliente", email="outra-cliente@example.com", status="cliente_ativo")
        intruder.set_password("senha-cliente-123")
        db.session.add_all([owner, intruder])
        db.session.commit()
        item = ShoppingListItem(
            client_id=owner.id,
            category="sapato",
            description="Scarpin da Dona Item",
            link_compra="https://parceiro.example.com/scarpin",
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    client.post(
        "/login",
        data={"email": "outra-cliente@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.post(f"/minha-area/lista-compras/{item_id}/aceitar")
    assert response.status_code == 404
    with app.app_context():
        assert db.session.get(ShoppingListItem, item_id).status == "recomendada"


def test_build_journey_for_empty_client_is_all_not_started(app):
    with app.app_context():
        c = Client(full_name="Cliente Vazia", email="vazia@example.com")
        db.session.add(c)
        db.session.commit()

        steps = build_journey(c)
        assert len(steps) == 4
        assert [s["status"] for s in steps] == ["nao_iniciado"] * 4
        assert steps[3]["next_consultation"] is None


def test_build_journey_dossie_no_longer_proxies_identity_or_diagnostico(app):
    with app.app_context():
        c = Client(full_name="Cliente Dossiê", email="dossie-journey@example.com")
        db.session.add(c)
        db.session.commit()

        report = StyleReport(
            client_id=c.id,
            title="Dossiê",
            content="",
            status="enviado",
            estilo_pessoal="Clássico contemporâneo",
        )
        db.session.add(report)
        db.session.commit()

        steps = build_journey(c)
        by_key = {s["key"]: s for s in steps}
        # Desde a PR4, nem identidade nem diagnóstico usam mais o dossiê como
        # proxy — cada etapa tem sinal real e independente.
        assert by_key["identidade"]["status"] == "nao_iniciado"
        assert by_key["diagnostico"]["status"] == "nao_iniciado"
        assert by_key["looks"]["status"] == "nao_iniciado"
        assert by_key["evolucao"]["status"] == "nao_iniciado"


def test_build_journey_diagnostico_status_reflects_style_assessment(app):
    with app.app_context():
        c = Client(full_name="Cliente Diagnóstico", email="diagnostico-journey@example.com")
        db.session.add(c)
        db.session.commit()

        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "diagnostico")["status"] == "nao_iniciado"

        assessment = StyleAssessment(client_id=c.id, estacao_cor="Outono suave")
        db.session.add(assessment)
        db.session.commit()

        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "diagnostico")["status"] == "concluido"


def test_build_journey_identity_status_reflects_narrative_fields(app):
    with app.app_context():
        c = Client(full_name="Cliente Identidade", email="identidade-journey@example.com")
        db.session.add(c)
        db.session.commit()

        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "identidade")["status"] == "nao_iniciado"

        c.identidade_rotina = "Rotina corrida entre reuniões e academia."
        db.session.commit()
        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "identidade")["status"] == "em_andamento"

        c.identidade_objetivo = "Quer transmitir mais autoridade."
        c.identidade_estilo = "Gosta de alfaiataria e cores neutras."
        db.session.commit()
        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "identidade")["status"] == "concluido"


def test_build_journey_with_future_consultation_is_em_andamento(app):
    with app.app_context():
        c = Client(full_name="Cliente Agendada", email="agendada-journey@example.com")
        db.session.add(c)
        db.session.commit()

        future = Consultation(
            client_id=c.id,
            scheduled_at=datetime(2099, 1, 1, 10, 0),
            status="agendada",
        )
        db.session.add(future)
        db.session.commit()

        steps = build_journey(c)
        evolucao = next(s for s in steps if s["key"] == "evolucao")
        assert evolucao["status"] == "em_andamento"
        assert evolucao["next_consultation"].id == future.id


def test_build_journey_with_only_past_consultation_is_concluido(app):
    with app.app_context():
        c = Client(full_name="Cliente Realizada", email="realizada-journey@example.com")
        db.session.add(c)
        db.session.commit()

        past = Consultation(
            client_id=c.id,
            scheduled_at=datetime(2020, 1, 1, 10, 0),
            status="realizada",
        )
        db.session.add(past)
        db.session.commit()

        steps = build_journey(c)
        evolucao = next(s for s in steps if s["key"] == "evolucao")
        assert evolucao["status"] == "concluido"
        assert evolucao["next_consultation"] is None


def test_client_area_shows_journey_cards(app, client):
    with app.app_context():
        c = Client(full_name="Marina Jornada", email="marina-jornada@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        report = StyleReport(
            client_id=c.id,
            title="Dossiê",
            content="",
            status="enviado",
            estilo_pessoal="Clássico contemporâneo",
        )
        db.session.add(report)
        db.session.add(StyleAssessment(client_id=c.id, estacao_cor="Outono suave"))
        db.session.commit()

    client.post(
        "/login",
        data={"email": "marina-jornada@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/")
    assert response.status_code == 200
    assert "Sua jornada de transformação".encode() in response.data
    assert "Conhecendo minha identidade".encode() in response.data
    assert "Meu diagnóstico de imagem".encode() in response.data
    assert "Minha assinatura visual".encode() in response.data
    assert "Minha evolução contínua".encode() in response.data
    assert "Concluído".encode() in response.data


def test_staff_saves_identity_fields_via_client_edit(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Renata Identidade", email="renata-identidade@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/editar",
        data={
            "full_name": "Renata Identidade",
            "email": "renata-identidade@example.com",
            "phone": "",
            "instagram": "",
            "source": "indicacao",
            "status": "cliente_ativo",
            "notes": "",
            "style_notes": "",
            "idade": "34",
            "profissao": "Advogada",
            "cidade": "São Paulo",
            "foto_perfil": "https://example.com/renata.jpg",
            "identidade_rotina": "Rotina corrida entre audiências e reuniões.",
            "identidade_objetivo": "Quer transmitir mais autoridade sem perder a leveza.",
            "identidade_estilo": "Alfaiataria com toques contemporâneos.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Alfaiataria com toques contemporâneos".encode() in response.data

    with app.app_context():
        c = db.session.get(Client, client_id)
        assert c.idade == 34
        assert c.profissao == "Advogada"
        assert c.cidade == "São Paulo"
        assert c.identidade_objetivo == "Quer transmitir mais autoridade sem perder a leveza."


def test_client_sees_own_identity_page(app, client):
    with app.app_context():
        c = Client(full_name="Beatriz Identidade", email="beatriz-identidade@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        c.idade = 29
        c.profissao = "Médica"
        c.identidade_rotina = "Plantões alternados com pouco tempo pra se cuidar."
        c.identidade_objetivo = "Quer se sentir confiante mesmo com rotina corrida."
        c.identidade_estilo = "Peças práticas que também sirvam pra ocasiões formais."
        db.session.add(c)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "beatriz-identidade@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/identidade")
    assert response.status_code == 200
    assert "Plantões alternados".encode() in response.data
    assert "Quer se sentir confiante".encode() in response.data
    assert "Peças práticas".encode() in response.data


def test_client_area_identity_route_blocked_for_staff(app, logged_in_client):
    response = logged_in_client.get("/minha-area/identidade")
    assert response.status_code == 403


def test_client_area_diagnostico_route_blocked_for_staff(app, logged_in_client):
    response = logged_in_client.get("/minha-area/diagnostico")
    assert response.status_code == 403


def test_client_area_evolucao_route_blocked_for_staff(app, logged_in_client):
    response = logged_in_client.get("/minha-area/evolucao")
    assert response.status_code == 403


def test_client_sees_next_and_past_consultations_on_evolucao_page(app, client):
    with app.app_context():
        c = Client(full_name="Vera Evolução", email="vera-evolucao@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        db.session.add(
            Consultation(
                client_id=c.id, tipo="consultoria_imagem",
                scheduled_at=datetime(2030, 1, 10, 14, 0), status="agendada",
            )
        )
        db.session.add(
            Consultation(
                client_id=c.id, tipo="diagnostico_gratuito",
                scheduled_at=datetime(2020, 1, 5, 10, 0), status="realizada",
            )
        )
        db.session.commit()

    client.post(
        "/login",
        data={"email": "vera-evolucao@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/evolucao")
    assert response.status_code == 200
    assert "10/01/2030".encode() in response.data
    assert "05/01/2020".encode() in response.data


def test_build_journey_looks_status_reflects_real_look(app):
    with app.app_context():
        c = Client(full_name="Cliente Looks", email="looks-journey@example.com")
        db.session.add(c)
        db.session.commit()

        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "looks")["status"] == "nao_iniciado"

        look = Look(client_id=c.id, nome="Reunião executiva")
        db.session.add(look)
        db.session.commit()

        steps = build_journey(c)
        assert next(s for s in steps if s["key"] == "looks")["status"] == "concluido"


def test_staff_creates_look_with_closet_items_and_client_favorites_it(app, logged_in_client, client):
    with app.app_context():
        c = Client(full_name="Paula Looks", email="paula-looks@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

        item1 = ClosetItem(client_id=client_id, category="blazer", description="Blazer preto")
        item2 = ClosetItem(client_id=client_id, category="calca", description="Calça alfaiataria bege")
        db.session.add_all([item1, item2])
        db.session.commit()
        item1_id, item2_id = item1.id, item2.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/looks/novo",
        data={
            "nome": "Reunião executiva",
            "photo_url": "https://example.com/look1.jpg",
            "momento": "trabalho",
            "ocasiao": "Reunião com investidores",
            "descricao": "Combinação estruturada e confiante.",
            "mensagem_transmitida": "Autoridade",
            "closet_item_ids": [str(item1_id), str(item2_id)],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Reunião executiva".encode() in response.data

    # O cruzamento closet -> looks aparece na página do Closet, não na de Looks.
    response = logged_in_client.get(f"/painel/clientes/{client_id}/closet")
    assert "usada em 1 look".encode() in response.data

    with app.app_context():
        look = Look.query.filter_by(client_id=client_id).first()
        assert look is not None
        assert len(look.items) == 2
        assert look.favorited is False
        look_id = look.id

    # Cliente vê o look e favorita.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "paula-looks@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/looks")
    assert response.status_code == 200
    assert "Reunião executiva".encode() in response.data
    assert "Blazer preto".encode() in response.data

    response = client.post(f"/minha-area/looks/{look_id}/favoritar", follow_redirects=True)
    assert response.status_code == 200
    assert "★ Favorito".encode() in response.data
    with app.app_context():
        assert db.session.get(Look, look_id).favorited is True

    # Volta como staff e remove o look.
    client.get("/logout")
    client.post(
        "/login",
        data={"email": "staff@example.com", "password": "senha-forte-123"},
        follow_redirects=True,
    )
    response = client.post(f"/painel/clientes/{client_id}/looks/{look_id}/excluir", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Look, look_id) is None


def test_client_filters_looks_by_momento(app, client):
    with app.app_context():
        c = Client(full_name="Marcia Momentos", email="marcia-momentos@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        db.session.add(Look(client_id=c.id, nome="Blazer de reunião", momento="trabalho"))
        db.session.add(Look(client_id=c.id, nome="Vestido de festa", momento="evento"))
        db.session.commit()

    client.post(
        "/login",
        data={"email": "marcia-momentos@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )

    response = client.get("/minha-area/looks")
    assert "Blazer de reunião".encode() in response.data
    assert "Vestido de festa".encode() in response.data

    response = client.get("/minha-area/looks?momento=trabalho")
    assert "Blazer de reunião".encode() in response.data
    assert "Vestido de festa".encode() not in response.data


def test_client_filters_closet_by_categoria(app, client):
    with app.app_context():
        c = Client(full_name="Carla Categorias", email="carla-categorias@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        db.session.add(ClosetItem(client_id=c.id, category="blazer", description="Blazer estruturado"))
        db.session.add(ClosetItem(client_id=c.id, category="calca", description="Calça pantalona"))
        db.session.commit()

    client.post(
        "/login",
        data={"email": "carla-categorias@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )

    response = client.get("/minha-area/looks")
    assert "Blazer estruturado".encode() in response.data
    assert "Calça pantalona".encode() in response.data

    response = client.get("/minha-area/looks?categoria=blazer")
    assert "Blazer estruturado".encode() in response.data
    assert "Calça pantalona".encode() not in response.data


def test_client_cannot_favorite_another_clients_look(app, client):
    with app.app_context():
        owner = Client(full_name="Dona do Look", email="dona-look@example.com", status="cliente_ativo")
        owner.set_password("senha-cliente-123")
        outsider = Client(full_name="Outra Cliente", email="outra-cliente@example.com", status="cliente_ativo")
        outsider.set_password("senha-cliente-123")
        db.session.add_all([owner, outsider])
        db.session.commit()
        owner_id = owner.id

        look = Look(client_id=owner_id, nome="Look privado")
        db.session.add(look)
        db.session.commit()
        look_id = look.id

    client.post(
        "/login",
        data={"email": "outra-cliente@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.post(f"/minha-area/looks/{look_id}/favoritar")
    assert response.status_code == 404


def test_staff_creates_and_edits_style_assessment(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Camila Diagnóstico", email="camila-diagnostico@example.com", status="cliente_ativo")
        db.session.add(c)
        db.session.commit()
        client_id = c.id

    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/diagnostico-estruturado/editar",
        data={
            "estacao_cor": "Outono suave",
            "paleta_principal": "tons terrosos e neutros",
            "estilo_predominante": "Elegante contemporâneo",
            "estilo_complementar": "",
            "mensagem_desejada": "confiança e sofisticação",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Outono suave".encode() in response.data

    with app.app_context():
        assessment = StyleAssessment.query.filter_by(client_id=client_id).first()
        assert assessment is not None
        assert assessment.paleta_principal == "tons terrosos e neutros"

    # Editar de novo não cria um segundo registro (1:1).
    response = logged_in_client.post(
        f"/painel/clientes/{client_id}/diagnostico-estruturado/editar",
        data={
            "estacao_cor": "Inverno profundo",
            "paleta_principal": "tons frios e contrastantes",
            "estilo_predominante": "Elegante contemporâneo",
            "estilo_complementar": "",
            "mensagem_desejada": "confiança e sofisticação",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert StyleAssessment.query.filter_by(client_id=client_id).count() == 1
        assert StyleAssessment.query.filter_by(client_id=client_id).first().estacao_cor == "Inverno profundo"


def test_client_sees_style_assessment_on_diagnostico_page(app, client):
    with app.app_context():
        c = Client(full_name="Denise Diagnóstico", email="denise-diagnostico@example.com", status="cliente_ativo")
        c.set_password("senha-cliente-123")
        db.session.add(c)
        db.session.commit()
        assessment = StyleAssessment(
            client_id=c.id,
            estacao_cor="Primavera clara",
            paleta_principal="tons quentes e luminosos",
            estilo_predominante="Romântico moderno",
            mensagem_desejada="leveza e frescor",
        )
        db.session.add(assessment)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "denise-diagnostico@example.com", "password": "senha-cliente-123"},
        follow_redirects=True,
    )
    response = client.get("/minha-area/diagnostico")
    assert response.status_code == 200
    assert "Primavera clara".encode() in response.data
    assert "leveza e frescor".encode() in response.data


def test_client_is_recorrente_needs_two_realized_consultations(app):
    with app.app_context():
        c = Client(full_name="Fernanda Recorrente", email="fernanda-recorrente@example.com")
        db.session.add(c)
        db.session.commit()
        assert c.is_recorrente is False

        db.session.add(Consultation(client_id=c.id, scheduled_at=datetime(2026, 1, 1, 10, 0), status="realizada"))
        db.session.commit()
        assert c.is_recorrente is False

        db.session.add(Consultation(client_id=c.id, scheduled_at=datetime(2026, 3, 1, 10, 0), status="realizada"))
        db.session.commit()
        assert c.is_recorrente is True


def test_analytics_shows_recurring_clients_count(app, logged_in_client):
    with app.app_context():
        c = Client(full_name="Helena Recorrente", email="helena-recorrente-analytics@example.com")
        db.session.add(c)
        db.session.commit()
        db.session.add(Consultation(client_id=c.id, scheduled_at=datetime(2026, 1, 1, 10, 0), status="realizada"))
        db.session.add(Consultation(client_id=c.id, scheduled_at=datetime(2026, 3, 1, 10, 0), status="realizada"))
        db.session.commit()

    response = logged_in_client.get("/painel/analytics/")
    assert response.status_code == 200
    assert "Clientes recorrentes".encode() in response.data


def test_upload_image_noop_without_cloudinary_configured(app):
    from werkzeug.datastructures import FileStorage

    from image_upload import upload_image

    with app.app_context():
        fake_file = FileStorage(stream=io.BytesIO(b"conteudo fake"), filename="foto.jpg")
        assert app.config.get("CLOUDINARY_URL") is None
        assert upload_image(fake_file) is None


def test_closet_item_photo_upload_overrides_pasted_url(app, logged_in_client):
    app.config["CLOUDINARY_URL"] = "cloudinary://fake_key:fake_secret@fake_cloud"
    try:
        with app.app_context():
            c = Client(full_name="Iris Upload", email="iris-upload@example.com")
            db.session.add(c)
            db.session.commit()
            client_id = c.id

        with patch("image_upload.cloudinary.uploader.upload") as mock_upload:
            mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/fake/avie/blazer.jpg"}
            response = logged_in_client.post(
                f"/painel/clientes/{client_id}/closet/novo",
                data={
                    "category": "blazer",
                    "description": "Blazer com foto enviada",
                    "photo_url": "https://exemplo.com/link-colado.jpg",
                    "photo_file": (io.BytesIO(b"conteudo fake de imagem"), "blazer.jpg"),
                    "notes": "",
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            mock_upload.assert_called_once()

        with app.app_context():
            item = ClosetItem.query.filter_by(client_id=client_id).first()
            assert item.photo_url == "https://res.cloudinary.com/fake/avie/blazer.jpg"
    finally:
        app.config["CLOUDINARY_URL"] = None


def test_closet_item_keeps_pasted_url_when_no_file_uploaded(app, logged_in_client):
    app.config["CLOUDINARY_URL"] = "cloudinary://fake_key:fake_secret@fake_cloud"
    try:
        with app.app_context():
            c = Client(full_name="Julia Upload", email="julia-upload@example.com")
            db.session.add(c)
            db.session.commit()
            client_id = c.id

        with patch("image_upload.cloudinary.uploader.upload") as mock_upload:
            response = logged_in_client.post(
                f"/painel/clientes/{client_id}/closet/novo",
                data={
                    "category": "blazer",
                    "description": "Blazer só com link",
                    "photo_url": "https://exemplo.com/link-colado.jpg",
                    "notes": "",
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            mock_upload.assert_not_called()

        with app.app_context():
            item = ClosetItem.query.filter_by(client_id=client_id).first()
            assert item.photo_url == "https://exemplo.com/link-colado.jpg"
    finally:
        app.config["CLOUDINARY_URL"] = None


def test_closet_item_prep_fields_are_optional_and_persist(app):
    with app.app_context():
        c = Client(full_name="Karen Closet", email="karen-closet@example.com")
        db.session.add(c)
        db.session.commit()

        # sem os campos preparatórios: continua funcionando normalmente
        bare_item = ClosetItem(client_id=c.id, category="blazer", description="Blazer sem detalhes")
        db.session.add(bare_item)
        db.session.commit()
        assert bare_item.cor is None
        assert bare_item.marca is None
        assert bare_item.ocasiao is None
        assert bare_item.estacao is None
        assert bare_item.estilo is None

        # preenchidos: persistem normalmente
        detailed_item = ClosetItem(
            client_id=c.id,
            category="vestido",
            description="Vestido midi",
            cor="Verde-oliva",
            marca="Zara",
            ocasiao="Evento",
            estacao="Verão",
            estilo="Elegante",
        )
        db.session.add(detailed_item)
        db.session.commit()

        saved = db.session.get(ClosetItem, detailed_item.id)
        assert saved.cor == "Verde-oliva"
        assert saved.marca == "Zara"
        assert saved.ocasiao == "Evento"
        assert saved.estacao == "Verão"
        assert saved.estilo == "Elegante"

