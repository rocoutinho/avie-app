"""Gera o rascunho inicial de um relatório personalizado a partir do
diagnóstico de autoconhecimento e estilo respondido pela cliente.

O texto gerado aqui é só o ponto de partida: a consultora sempre revisa e
personaliza antes de enviar. Isso mantém o v1 simples (sem dependência de
IA ou serviços externos) e deixa espaço para, no futuro, plugar um
assistente de escrita com IA sem mudar o resto do sistema.
"""


def generate_report_draft(client, profile):
    if not profile:
        return (
            f"Relatório personalizado para {client.full_name}\n\n"
            "Ainda não há respostas do diagnóstico de autoconhecimento para esta "
            "pessoa. Preencha o link do diagnóstico com a cliente ou escreva o "
            "relatório manualmente abaixo."
        )

    return f"""Relatório de Posicionamento Profissional e Estilo
Preparado especialmente para {client.full_name}

1. Seu momento atual
{profile.momento_carreira}

2. Onde você quer chegar
{profile.objetivo_profissional}

3. Como você quer ser percebida
{profile.como_quer_ser_percebida}

4. O que está no seu caminho hoje
{profile.desafios_imagem}

5. Leitura de estilo
Estilo atual observado: {profile.estilo_atual or "a definir na consulta"}
Cores de afinidade: {profile.cores_preferidas or "a definir na consulta"}
Referências que ressoam com você: {profile.referencias_estilo or "a definir na consulta"}

6. Recomendações e próximos passos
[Personalize esta seção com as recomendações da consultoria: paleta de
cores, peças-chave, comunicação não-verbal e plano de ação.]

—
Fabiana Montemor · Consultoria de Imagem e Estilo
"""
