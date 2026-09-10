"""A Jornada de Transformação da cliente — camada de apresentação calculada,
sem tabela própria. `build_journey(client)` lê dados que já existem em outros
modelos (StyleProfile, StyleReport, Consultation, e futuramente Look e
StyleAssessment) e devolve as 4 etapas fixas do MVP com status computado.

Ver plano da sessão: até a Look (PR3) e StyleAssessment (PR4) existirem, as
etapas "identidade" e "diagnóstico" usam o mesmo proxy (perfil do wizard ou
dossiê entregue) — a Jornada fica com sinal parcial nesse meio-tempo, isso é
uma decisão aceita, não um bug."""

from datetime import datetime

JOURNEY_STATUS_NAO_INICIADO = "nao_iniciado"
JOURNEY_STATUS_EM_ANDAMENTO = "em_andamento"
JOURNEY_STATUS_CONCLUIDO = "concluido"

JOURNEY_STATUS_LABELS = {
    JOURNEY_STATUS_NAO_INICIADO: "Não iniciado",
    JOURNEY_STATUS_EM_ANDAMENTO: "Em andamento",
    JOURNEY_STATUS_CONCLUIDO: "Concluído",
}


def build_journey(client):
    has_identity_proxy = bool(client.profile or client.dossie_report)

    future_agendada = sorted(
        (c for c in client.consultations if c.status == "agendada" and c.scheduled_at >= datetime.utcnow()),
        key=lambda c: c.scheduled_at,
    )
    next_consultation = future_agendada[0] if future_agendada else None
    has_realizada = any(c.status == "realizada" for c in client.consultations)

    if next_consultation:
        evolucao_status = JOURNEY_STATUS_EM_ANDAMENTO
    elif has_realizada:
        evolucao_status = JOURNEY_STATUS_CONCLUIDO
    else:
        evolucao_status = JOURNEY_STATUS_NAO_INICIADO

    identidade_diagnostico_status = (
        JOURNEY_STATUS_CONCLUIDO if has_identity_proxy else JOURNEY_STATUS_NAO_INICIADO
    )

    steps = [
        {
            "key": "identidade",
            "title": "Conhecendo minha identidade",
            "description": "Quem você é, como quer ser percebida e qual é o seu estilo.",
            "status": identidade_diagnostico_status,
            "anchor": "etapa-identidade",
        },
        {
            "key": "diagnostico",
            "title": "Meu diagnóstico de imagem",
            "description": "O que a sua consultora identificou sobre cores, estilo e proporções.",
            "status": identidade_diagnostico_status,
            "anchor": "etapa-diagnostico",
        },
        {
            "key": "looks",
            "title": "Minha assinatura visual",
            "description": "Looks pensados pela sua consultora a partir do seu closet.",
            "status": JOURNEY_STATUS_NAO_INICIADO,
            "anchor": "etapa-looks",
        },
        {
            "key": "evolucao",
            "title": "Minha evolução contínua",
            "description": "Suas consultorias, passadas e futuras.",
            "status": evolucao_status,
            "anchor": "etapa-evolucao",
            "next_consultation": next_consultation,
        },
    ]
    for step in steps:
        step["status_label"] = JOURNEY_STATUS_LABELS[step["status"]]
    return steps
