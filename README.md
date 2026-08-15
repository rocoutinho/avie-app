# Avie — Sistema da Consultoria Fabiana Montemor

Sistema interno para a operação de consultoria de imagem e estilo da
Fabiana Montemor, com foco em posicionamento profissional e
autoconhecimento. Cobre o ciclo completo do negócio: captação de leads
com diagnóstico personalizado, CRM de clientes, agendamento de consultas,
geração de relatórios personalizados e controle de pagamentos.

Feito para ser mantido por 2 pessoas sem experiência prévia em
desenvolvimento (uma delas entusiasta de tecnologia): stack mínima, sem
etapa de build de frontend, um único banco de dados em arquivo (SQLite) e
tudo rodando com `python`/`flask` a partir da linha de comando.

## Por que essa stack

- **Flask + Jinja + Bootstrap (via CDN)**: sem Node, sem bundler, sem
  passo de compilação. Editar um `.html` e dar refresh já mostra o
  resultado — curva de aprendizado baixa.
- **SQLite**: banco de dados é um arquivo só (`instance/avie.db`), sem
  servidor de banco para instalar/manter. Cresce com o negócio; quando
  fizer sentido, trocar para Postgres é só mudar a variável
  `DATABASE_URL`.
- **Sem dependência de serviços pagos no v1** (e-mail, calendário,
  pagamento online, IA): tudo isso está listado no roadmap abaixo como
  evolução, não como pré-requisito para começar a usar.

## Como rodar localmente

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # ajuste SECRET_KEY para um valor aleatório

flask db upgrade                # cria/atualiza as tabelas do banco (via migrações)
flask create-admin              # cria o primeiro usuário (Fabiana ou o suporte)

flask run                       # abre em http://127.0.0.1:5000
```

Sempre que `models.py` mudar, gere uma nova migração em vez de mexer no
banco na mão:

```bash
flask db migrate -m "descrição da mudança"
flask db upgrade
```

- Página pública: `/` (landing) e `/diagnostico` (formulário de
  diagnóstico que qualquer visitante preenche).
- Área da equipe: `/login` → `/painel` (Kanban de clientes, consultas e
  pagamentos).

## Fluxo do sistema

1. **Captação** — a cliente em potencial preenche `/diagnostico`
   (objetivos profissionais, autopercepção, desafios de imagem, estilo
   atual). Isso cria automaticamente um registro de **Lead** no CRM.
2. **Qualificação** — a equipe move o status do cliente no painel
   (Lead → Contatado → Diagnóstico Agendado...).
3. **Consulta** — agendar a sessão dentro do cadastro do cliente
   (`+ Agendar`).
4. **Relatório personalizado** — a partir das respostas do diagnóstico,
   o sistema gera um **rascunho** do relatório (seções: momento atual,
   objetivo, como quer ser percebida, desafios, leitura de estilo). A
   consultora revisa, personaliza e marca como enviado.
5. **Financeiro** — pagamentos simples (descrição, valor, status,
   vencimento) ficam vinculados ao cliente; segue sendo o contador
   terceirizado quem cuida da contabilidade formal.

## Estrutura de pastas

```
app.py              # application factory + comandos flask (create-admin, backup-db)
config.py           # configuração (lê .env; exige SECRET_KEY em produção)
extensions.py       # instâncias do SQLAlchemy, Flask-Login, Flask-Migrate, Flask-Limiter
models.py           # tabelas: User, Client, StyleProfile, Consultation, StyleReport, Payment
forms.py            # formulários (Flask-WTF)
reports_engine.py   # gera o rascunho do relatório personalizado
blueprints/          # rotas: auth, public, dashboard, clients, reports
templates/           # HTML (Jinja + Bootstrap)
static/css/          # estilo visual da marca
migrations/          # histórico de mudanças no banco (Flask-Migrate/Alembic)
tests/               # testes automatizados (pytest)
```

## Segurança e dados pessoais (LGPD)

O sistema coleta dados pessoais sensíveis no diagnóstico público (objetivos
de carreira, autopercepção, orçamento). Antes de captar clientes reais:

- **`SECRET_KEY`**: obrigatório via variável de ambiente quando
  `AVIE_ENV=production`; a aplicação recusa subir sem ela.
- **Consentimento**: o formulário de diagnóstico exige aceite explícito de
  uma [Política de Privacidade](templates/privacy.html) (`/privacidade`)
  antes de enviar, com data/hora do consentimento salva junto ao perfil.
- **Anti-spam**: campo honeypot invisível + limite de 5 envios por hora por
  IP no formulário público, e 10 tentativas por minuto no login.
- **Cookies de sessão**: `HttpOnly` sempre; `Secure` (só via HTTPS) quando
  `AVIE_ENV=production`.
- **Backup do banco**: `flask backup-db` copia o SQLite atual para
  `instance/backups/` com timestamp. Agende isso (cron/Task Scheduler)
  enquanto o banco for um arquivo local — é o item de maior risco de perda
  de dados do sistema hoje.
- **Rate limiting em memória**: funciona bem para um único processo/servidor
  (o cenário atual). Se o sistema crescer para múltiplas instâncias, trocar
  o `storage_uri` do `Limiter` (em `extensions.py`) para Redis.

## Roadmap de evolução

Mapeado à estrutura de "rodar rápido, depois melhorar" com a qual esse
projeto começou:

| Frente | Como opera hoje (v1) | Próximo passo de crescimento |
|---|---|---|
| Estratégia e Entrega | Painel único, 100% conduzido pela consultora | Automatizar lembretes de status/relatório pendente |
| Marketing e Vendas | Formulário de diagnóstico + landing simples | Integrar rastreamento de campanhas (UTM) por origem de lead |
| Operações e Suporte | Painel manual (Kanban, agendamento, relatórios) | Sincronizar consultas com Google Calendar; lembretes automáticos por e-mail/WhatsApp |
| Financeiro | Registro manual de pagamentos no CRM | Cobrança online (Pix/cartão) integrada ao cadastro do cliente |
| Relatórios | Rascunho gerado por template a partir do diagnóstico | Assistente com IA para enriquecer o rascunho antes da revisão da consultora |

Nenhum desses itens é necessário para começar a usar o sistema — a ideia
é adicionar cada um só quando o volume de clientes justificar.

## Rodando os testes

```bash
pytest
```
