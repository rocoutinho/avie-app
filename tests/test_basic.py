from datetime import datetime

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import BlogPost, Campaign, Client, Consultation, Ebook, Payment, StyleProfile, StyleReport, User


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


def _campaign_payload(**overrides):
    payload = {
        "internal_name": "Instagram Agosto",
        "slug": "instagram-agosto",
        "hero_eyebrow": "",
        "hero_title": "Título de teste",
        "hero_highlight": "",
        "hero_subtitle": "",
        "hero_cta_text": "",
        "hero_image_url": "",
        "theme_color": "",
        "embed_url": "",
    }
    payload.update(overrides)
    return payload


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


def test_marketing_creates_campaign_but_cannot_approve_it(app, marketing_client):
    response = marketing_client.post(
        "/painel/campanhas/novo", data=_campaign_payload(), follow_redirects=True
    )
    assert response.status_code == 200

    with app.app_context():
        campaign = Campaign.query.filter_by(slug="instagram-agosto").first()
        assert campaign is not None
        assert campaign.status == "rascunho"
        campaign_id = campaign.id

    response = marketing_client.post(
        f"/painel/campanhas/{campaign_id}/enviar-revisao", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Campaign, campaign_id).status == "em_revisao"

    # Marketing não pode aprovar — só o owner.
    response = marketing_client.post(f"/painel/campanhas/{campaign_id}/aprovar")
    assert response.status_code == 403

    # A página pública ainda não existe, porque não foi aprovada.
    response = marketing_client.get("/lp/instagram-agosto")
    assert response.status_code == 404


def test_owner_approves_campaign_and_it_goes_live(app, logged_in_client):
    with app.app_context():
        marketing_user = User(name="Fabiana Marketing", email="mkt2@example.com", role="marketing")
        marketing_user.set_password("senha-forte-123")
        db.session.add(marketing_user)
        db.session.commit()
        campaign = Campaign(
            slug="black-friday",
            internal_name="Black Friday",
            hero_title="Título Black Friday",
            status="em_revisao",
            created_by_id=marketing_user.id,
        )
        db.session.add(campaign)
        db.session.commit()
        campaign_id = campaign.id

    response = logged_in_client.post(
        f"/painel/campanhas/{campaign_id}/aprovar", follow_redirects=True
    )
    assert response.status_code == 200

    with app.app_context():
        approved = db.session.get(Campaign, campaign_id)
        assert approved.status == "publicado"
        assert approved.published_at is not None
        assert approved.reviewed_by_id is not None

    response = logged_in_client.get("/lp/black-friday")
    assert response.status_code == 200
    assert "Título Black Friday".encode() in response.data


def test_owner_rejects_campaign_back_to_draft_with_note(app, logged_in_client):
    with app.app_context():
        marketing_user = User(name="Fabiana Marketing", email="mkt3@example.com", role="marketing")
        marketing_user.set_password("senha-forte-123")
        db.session.add(marketing_user)
        db.session.commit()
        campaign = Campaign(
            slug="natal",
            internal_name="Natal",
            hero_title="Título Natal",
            status="em_revisao",
            created_by_id=marketing_user.id,
        )
        db.session.add(campaign)
        db.session.commit()
        campaign_id = campaign.id

    response = logged_in_client.post(
        f"/painel/campanhas/{campaign_id}/recusar",
        data={"review_note": "Trocar a imagem do topo"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        rejected = db.session.get(Campaign, campaign_id)
        assert rejected.status == "rascunho"
        assert rejected.review_note == "Trocar a imagem do topo"

    response = logged_in_client.get("/lp/natal")
    assert response.status_code == 404


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

    response = client.post(
        "/login",
        data={"email": "dossie-nova@example.com", "password": "senha-cliente-final"},
        follow_redirects=True,
    )
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
    response = client.post(
        "/login",
        data={"email": "dossie-nova@example.com", "password": "senha-cliente-final"},
        follow_redirects=True,
    )
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


def test_published_campaign_with_embed_url_renders_iframe_instead_of_hero(app, client):
    with app.app_context():
        user = User(name="Fabiana", email="owner-embed@example.com", role="owner")
        user.set_password("senha-forte-123")
        db.session.add(user)
        db.session.commit()
        campaign = Campaign(
            slug="canvas-teste",
            internal_name="Campanha Canvas",
            hero_title="Título do hero, deve ser ignorado",
            embed_url="https://example.com/minha-landing-canvas",
            status="publicado",
            created_by_id=user.id,
        )
        db.session.add(campaign)
        db.session.commit()

    response = client.get("/lp/canvas-teste")
    assert response.status_code == 200
    assert b'src="https://example.com/minha-landing-canvas"' in response.data
    # A seção de hero nativa (landing.html) não deve ser renderizada.
    assert b"lp-hero" not in response.data


def test_campanha_slug_also_resolves_at_root_path(app, client):
    with app.app_context():
        user = User(name="Fabiana", email="owner-campanha@example.com", role="owner")
        user.set_password("senha-forte-123")
        db.session.add(user)
        db.session.commit()
        campaign = Campaign(
            slug="campanha",
            internal_name="Campanha Principal",
            hero_title="Hero da campanha principal",
            embed_url="https://example.com/campanha-principal",
            status="publicado",
            created_by_id=user.id,
        )
        db.session.add(campaign)
        db.session.commit()

    response = client.get("/campanha")
    assert response.status_code == 200
    assert b'src="https://example.com/campanha-principal"' in response.data

    # /lp/campanha continua funcionando — o Werkzeug redireciona pra URL
    # canônica /campanha (evita conteúdo duplicado em duas URLs).
    response = client.get("/lp/campanha", follow_redirects=True)
    assert response.status_code == 200
    assert b'src="https://example.com/campanha-principal"' in response.data


def test_unpublished_campanha_slug_returns_404_at_root_path(client):
    response = client.get("/campanha")
    assert response.status_code == 404
