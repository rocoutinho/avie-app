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

- **Flask + Jinja + Bootstrap (vendorizado localmente, sem CDN)**: sem
  Node, sem bundler, sem passo de compilação. Editar um `.html` e dar
  refresh já mostra o resultado — curva de aprendizado baixa. Bootstrap,
  fontes e o ícone da marca ficam em `static/`, então o site funciona
  mesmo se o Google Fonts ou o jsDelivr estiverem fora do ar ou
  bloqueados na rede de quem visita (isso já aconteceu durante o
  desenvolvimento — ver `static/vendor/` e `static/fonts/`).
- **SQLite**: banco de dados é um arquivo só (`instance/avie.db`), sem
  servidor de banco para instalar/manter. Cresce com o negócio; quando
  fizer sentido, trocar para Postgres é só mudar a variável
  `DATABASE_URL`.
- **Sem dependência de serviços pagos no v1** (e-mail, calendário,
  pagamento online, IA): tudo isso está listado no roadmap abaixo como
  evolução, não como pré-requisito para começar a usar.
- **Custo zero em produção enquanto o sistema é experimental**: o
  deploy no Render usa o plano free (sem banco Postgres pago) — ver
  "Deploy" mais abaixo. A troca de contrapartida é que o disco é
  efêmero (os dados somem a cada deploy/reinício), aceitável nesta
  fase; quando isso deixar de fazer sentido, é só voltar pro plano
  pago com um banco persistente.

## Como rodar localmente

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # ajuste SECRET_KEY para um valor aleatório

flask db upgrade                # cria/atualiza as tabelas do banco (via migrações)
flask create-admin              # cria o primeiro usuário (Fabiana ou o suporte)
flask seed-demo-client          # opcional: cria um cliente fictício pra navegar o sistema

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

## Captação de leads via Instagram, Google e LinkedIn

O sistema foi preparado para receber tráfego de anúncios/links desses três
canais com o mínimo de atrito possível:

- **Atribuição automática**: links de campanha com parâmetros `utm_source`,
  `utm_medium` e `utm_campaign` (ex.: `?utm_source=instagram&utm_medium=paid_social&utm_campaign=lancamento_agosto`)
  são guardados assim que a pessoa chega — tanto pela landing (`/`) quanto
  clicando direto num link para `/diagnostico`. O campo "Como você conheceu
  o trabalho?" do formulário já vem pré-selecionado a partir disso (a pessoa
  pode corrigir). Sem `utm_source` explícito, um `gclid` na URL (padrão do
  Google Ads) é lido como Google, e um `fbclid` (padrão do Meta Ads) como
  Instagram. A ficha do cliente no painel mostra a origem e a campanha.
- **Nenhum lead se perde por abandono**: o formulário de diagnóstico é um
  wizard de 3 etapas. Assim que a pessoa termina a 1ª etapa (nome, e-mail,
  telefone), esse contato mínimo já é salvo como Lead no CRM — mesmo que
  ela feche a aba antes de terminar as etapas seguintes. Isso é
  especialmente importante em tráfego pago frio, onde a maior parte do
  abandono acontece. Nenhuma resposta sensível do diagnóstico (objetivos,
  autopercepção, orçamento) é salva antes do consentimento explícito na
  última etapa — só o contato para retomada.
- **Cartão de compartilhamento**: ao colar o link do site no bio do
  Instagram, num post do LinkedIn ou num anúncio, aparece um cartão com
  título, descrição e imagem de marca (Open Graph / Twitter Card,
  configurados em `templates/base.html`).
- **Mensuração (opcional)**: `GA4_MEASUREMENT_ID`, `META_PIXEL_ID` e
  `LINKEDIN_PARTNER_ID` no `.env` ativam Google Analytics 4, Meta Pixel e
  LinkedIn Insight Tag, respectivamente — nenhum é carregado sem essas
  variáveis. Ao ativar, atualize a Política de Privacidade (`/privacidade`)
  para mencionar cookies de conversão/retargeting.

Ao montar um link de campanha, use sempre `utm_source` com um destes
valores para a atribuição automática funcionar: `instagram`, `google` ou
`linkedin`. Exemplo para um anúncio no Instagram apontando direto para o
diagnóstico:
`https://SEUDOMINIO/diagnostico?utm_source=instagram&utm_medium=paid_social&utm_campaign=NOME_DA_CAMPANHA`.

## Blog e funil de conteúdo para o LinkedIn

Um artigo é escrito e testado no blog do site antes de ser reaproveitado
manualmente no LinkedIn da Fabiana — mesmo fluxo de aprovação das
campanhas (`/painel/campanhas`):

1. **Rascunho** — em `/painel/blog/novo`, `marketing` (ou `owner`) escreve
   título, resumo, imagem de capa (URL) e o conteúdo em **Markdown**
   (`## subtítulo`, `**negrito**`, `- item de lista`, `> citação`).
2. **Enviar para revisão** — o artigo fica visível só no painel, não no
   site público.
3. **Aprovar e publicar** (só `owner`) — fica no ar em `/blog/<slug>` e
   passa a aparecer na listagem `/blog`. Se o `owner` **recusar**, o
   artigo volta pra rascunho com um motivo de recusa opcional.

O resumo também vira a descrição mostrada ao colar o link no LinkedIn, e
a imagem de capa vira o `og:image` daquele artigo especificamente (cada
post tem seu próprio cartão de compartilhamento, diferente do cartão
genérico do resto do site).

**Atenção**: artigos do blog estão sujeitos à mesma perda de dados do
plano free do Render que o resto do banco (ver "Deploy" abaixo) — um
artigo publicado sobrevive até o próximo deploy/reinício do serviço, não
depois disso. Diferente de um lead de teste no CRM, um artigo é conteúdo
de verdade — vale a pena reavaliar esse trade-off (banco persistente)
assim que o blog tiver posts que realmente importa manter.

## Ebook (isca digital)

Em `/painel/ebooks`, qualquer pessoa da equipe cadastra um ebook: título,
descrição, imagem de capa (opcional) e o **link** do PDF — não é upload
de arquivo, precisa ser um link já hospedado (Google Drive, Dropbox etc.,
configurado como "qualquer pessoa com o link pode visualizar"). Isso é
proposital: o disco do plano free do Render é efêmero, um PDF enviado
pelo sistema seria apagado no próximo deploy e quebraria o link que já
foi enviado por e-mail para quem baixou. Só um ebook fica **ativo** por
vez (botão "Ativar" na listagem) — é ele que aparece em `/ebook`.

Sem fluxo de aprovação (diferente de campanhas e blog) — é tratado como
um material de marketing simples, não como conteúdo público que precisa
de revisão.

Fluxo de quem baixa: em `/ebook`, a pessoa informa nome, e-mail, telefone
e opcionalmente marca "quero receber um diagnóstico gratuito, sem
compromisso". Ao enviar, isso cria (ou atualiza) um registro de **Lead**
no CRM (origem "Ebook") com uma nota sobre o download e o interesse no
diagnóstico, o link é enviado por e-mail (mesmo mecanismo do diagnóstico —
não faz nada sem `MAIL_SERVER` configurado) e a pessoa já cai numa página
com o botão de download imediato (não depende do e-mail chegar) e um
link de WhatsApp pra continuar a conversa. Não há envio automático por
WhatsApp — isso exigiria uma API paga (Twilio/Meta), fora do escopo atual.

## Área do cliente

Staff e cliente entram pelo mesmo botão "Clientes" (`/login`) — o sistema
reconhece automaticamente quem é quem: se o e-mail/senha bate com um
usuário da equipe (`owner`/`marketing`), cai no painel interno de sempre;
senão, se bate com um cliente que já tem acesso liberado, cai na área
dele (`/minha-area`), que mostra só o diagnóstico e as recomendações
daquele cliente — nunca dados de outros.

**Cliente não se autocadastra.** Como a Fabiana já tem os dados de cada
cliente no CRM, é ela (ou o suporte) quem libera o acesso: na ficha do
cliente (`/painel/clientes/<id>`), o card "Acesso à área do cliente"
define uma senha — a partir daí, o e-mail já cadastrado + essa senha
já servem de login. Repassa a senha pro cliente por WhatsApp ou e-mail
manualmente. O acesso pode ser removido a qualquer momento no mesmo card.

**Cadastro com dossiê** (`/painel/clientes/novo-com-dossie`): para
clientes reais que já receberam o dossiê fora do sistema. Numa
submissão só, cria (ou atualiza, por e-mail) o cadastro com status
"Cliente Concluído" (já passou por diagnóstico + consultoria — diferente
de "Cliente Ativo", que é pra um engajamento em andamento), e registra o
dossiê como um `StyleReport` já "enviado" — com um campo por serviço
entregue (**Estilo, Biotipo, Cores, Visagismo, Arquétipos**; deixe em
branco os que não se aplicam) e um link opcional pro PDF original —,
gera uma senha temporária e um link de troca de senha
(`/redefinir-senha/<token>`, válido por 72h) — esse link é o que se
repassa por e-mail (se `MAIL_SERVER` estiver configurado) e/ou por um
botão de WhatsApp que já abre a conversa com o número do próprio cliente
com a mensagem pronta. Reenviar o formulário pro mesmo e-mail atualiza o
dossiê existente em vez de criar outro — pra só ajustar o conteúdo
depois (sem mexer em senha/acesso), use "Editar dossiê" na ficha do
cliente, que edita exatamente essa mesma linha. Na ficha do cliente
(admin) o dossiê tem seu próprio card, com o texto de cada serviço e o
link do PDF; na área do cliente, cada serviço vira um card com ícone —
mesma informação nos dois lugares, porque os dois lêem o mesmo registro.
Isso fica no lugar do CTA de "fazer o diagnóstico" (que só faz sentido
pra quem chegou pelo funil público, via `/diagnostico` — quem já tem
dossiê não precisa refazer nada). Esse
link de troca de senha é, hoje, o único fluxo de "esqueci minha senha"
— não há um link de "solicitar redefinição"
que o próprio cliente possa disparar sozinho.

O que a área do cliente mostra hoje: o diagnóstico que ele preencheu e
as recomendações/relatórios que a consultoria já enviou (`status`
"enviado"), além de um aviso simples de "seu último acesso foi em ...".
**Histórico de acesso mais completo e "dicas personalizadas" ainda não
foram implementados** — precisam ser detalhados antes (quantas entradas
mostrar, de onde vêm as dicas etc.).

## Estrutura de pastas

```
app.py              # application factory + comandos flask (create-admin, backup-db)
config.py           # configuração (lê .env; exige SECRET_KEY em produção)
extensions.py       # instâncias do SQLAlchemy, Flask-Login, Flask-Migrate, Flask-Limiter
models.py           # tabelas: User, Client, StyleProfile, Consultation, StyleReport, Payment, Campaign, BlogPost
forms.py            # formulários (Flask-WTF)
reports_engine.py   # gera o rascunho do relatório personalizado
blog_engine.py       # renderiza Markdown -> HTML e formata datas em pt-BR pro blog
blueprints/          # rotas: auth, public, dashboard, clients, reports, campaigns, blog, ebooks, client_area
templates/           # HTML (Jinja + Bootstrap)
static/vendor/        # Bootstrap CSS/JS vendorizado (sem CDN)
static/fonts/         # fontes auto-hospedadas (Inter, Cormorant Garamond)
static/css/           # tokens de cor/tipografia da marca + estilos
static/img/           # ícone da marca (leque de cores)
migrations/          # histórico de mudanças no banco (Flask-Migrate/Alembic)
tests/               # testes automatizados (pytest)
```

## Identidade visual

A partir do `Manual da Marca V1.2024` (StudioBin) e dos arquivos reais de
logo/ícone/tipografia fornecidos pela Fabiana, o sistema usa:

- **Cores**: azul índigo `#323955` (texto, logotipo), azul marinho `#1f2733`
  (fundos escuros — navbar e hero) e dourado `#bd9750` / `#f5d886` (CTAs e
  destaques) — valores hex exatos da Paleta de Cores do manual. Definidas
  como variáveis CSS em `static/css/style.css` — trocar a marca inteira é
  editar esse bloco.
- **Ícone e logotipo**: arquivos reais da marca (`static/img/icon-navy.png`,
  `icon-gold.png`, `logo-full-navy.png`, `logo-full-gold.png`,
  `logo-watermark.png`) — o anel do "leque de cores" alterna entre azul
  (fundo claro) e dourado (fundo escuro); os segmentos coloridos nunca
  mudam.
- **Tipografia**: título em "Edensor" (arquivo `static/fonts/edensor.woff2`,
  variante "FREE" da fonderia FactoryType) está carregada mas **não** é
  usada em `h1/h2/h3` — esse arquivo específico derruba acentos do
  português (ã, é, ç, í) de forma consistente no Chromium (confirmado com
  `document.fonts.status === "loaded"`, não é problema de carregamento).
  `h1/h2/h3/.font-serif` usam "Cormorant Garamond" (Google Fonts/OFL) por
  segurança. Se surgir um arquivo da Edensor licenciado/hinted
  corretamente, troque o `font-family` em `static/css/style.css` — nada
  mais no sistema precisa mudar. Rótulos em caixa-alta (`.eyebrow`,
  cabeçalhos de rodapé etc.) usam "News Gothic Condensed"
  (`static/fonts/news-gothic-condensed.woff2`, Bitstream/Monotype, uso web
  licenciado) — essa não apresentou o mesmo problema de acentuação.

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
  `instance/backups/` com timestamp. Útil localmente; em produção não
  ajuda contra a perda de dados a cada deploy (ver "Deploy" abaixo), já
  que o backup ficaria no mesmo disco efêmero que o banco.
- **Cliente fictício para navegação**: `flask seed-demo-client` cria (ou
  reseta) um cliente de exemplo — `cliente.demo@example.com` / senha
  `Demo@2026!` — com dados em todas as áreas do sistema: dossiê com 4 dos
  5 serviços preenchidos (Visagismo em branco de propósito, pra mostrar
  que o sistema lida bem com dossiês parciais) e link de PDF, um
  relatório de acompanhamento, um rascunho,
  consultorias e pagamentos, pra dar pra navegar o painel inteiro e a
  área do cliente sem usar dados de clientes reais. E-mail/telefone são
  propositalmente fictícios (não disparam contato de verdade). Idempotente
  — pode rodar de novo quando quiser um estado limpo. Como o disco de
  produção é efêmero (ver "Deploy"), esse cliente some a cada
  deploy/restart junto com o resto do banco; rode o comando de novo se
  precisar dele lá.
- **Rate limiting em memória**: funciona bem para um único processo/servidor
  (o cenário atual). Se o sistema crescer para múltiplas instâncias, trocar
  o `storage_uri` do `Limiter` (em `extensions.py`) para Redis.

## Deploy

Hospedado no Render.com (`avie-app`), plano **free** — custo zero enquanto
o sistema é experimental. Sem banco Postgres: produção roda em SQLite,
igual ao ambiente local.

**Troca envolvida (aceita de propósito nesta fase)**: o disco do plano
free é efêmero — os dados (leads, clientes, usuários) somem a cada deploy
e a cada reinício por inatividade. Pra que o site nunca fique inacessível
por isso, o comando de start (`render.yaml`) roda sozinho, a cada boot:

```
flask db upgrade && flask seed-admin && flask seed-demo-client && gunicorn app:app --bind 0.0.0.0:$PORT
```

> **Atenção**: como o serviço `avie-app` foi criado manualmente no Render
> (ver abaixo), esse `render.yaml` **não se aplica sozinho**. Pra esse
> Start Command valer de verdade em produção, é preciso colar essa mesma
> linha em **Settings → Build & Deploy → Start Command** no painel do
> Render e salvar — só editar o arquivo no repositório não muda o que
> está rodando lá.

`flask db upgrade` recria as tabelas; `flask seed-admin` recria o usuário
de acesso a partir das variáveis `ADMIN_NAME`/`ADMIN_EMAIL`/
`ADMIN_PASSWORD`/`ADMIN_ROLE` configuradas no painel do Render (não faz
nada se essas variáveis não estiverem definidas, ou se o usuário já
existir — seguro de rodar toda vez); `flask seed-demo-client` recria o
cliente fictício de navegação (ver "Segurança e boas práticas" acima) —
sempre roda, é idempotente e não depende de variável nenhuma.

**Configurar pela primeira vez** (o serviço `avie-app` já existe e foi
criado manualmente no Render, então `render.yaml` não se aplica sozinho —
os campos abaixo precisam ser conferidos/ajustados à mão no painel):

1. **Settings → Instance Type**: Free.
2. **Settings → Build & Deploy → Start Command**:
   `flask db upgrade && flask seed-admin && flask seed-demo-client && gunicorn app:app --bind 0.0.0.0:$PORT`
3. **Environment**: adicionar `ADMIN_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
   (senha com pelo menos 10 caracteres), `ADMIN_ROLE` (`owner` ou
   `marketing`); remover `DATABASE_URL` se existir uma apontando pro
   Postgres antigo (sem essa variável, a aplicação usa SQLite
   automaticamente).
4. Se ainda existir um banco Postgres (`avie-db`) criado antes dessa
   mudança, pode ser apagado no painel do Render — não é mais usado.

**Quando o negócio justificar o custo**: trocar o plano de volta pra
`starter` e definir `DATABASE_URL` com a connection string de um banco
Postgres (Render ou outro provedor) — o código já suporta os dois sem
mudança nenhuma.

## Roadmap de evolução

Mapeado à estrutura de "rodar rápido, depois melhorar" com a qual esse
projeto começou:

| Frente | Como opera hoje (v1) | Próximo passo de crescimento |
|---|---|---|
| Estratégia e Entrega | Painel único, 100% conduzido pela consultora | Automatizar lembretes de status/relatório pendente |
| Marketing e Vendas | Landing + diagnóstico com atribuição UTM e captura de lead parcial (Instagram, Google, LinkedIn) | Página de agradecimento com eventos de conversão por canal; testes A/B de headline |
| Operações e Suporte | Painel manual (Kanban, agendamento, relatórios) | Sincronizar consultas com Google Calendar; lembretes automáticos por e-mail/WhatsApp |
| Financeiro | Registro manual de pagamentos no CRM | Cobrança online (Pix/cartão) integrada ao cadastro do cliente |
| Relatórios | Rascunho gerado por template a partir do diagnóstico | Assistente com IA para enriquecer o rascunho antes da revisão da consultora |

Nenhum desses itens é necessário para começar a usar o sistema — a ideia
é adicionar cada um só quando o volume de clientes justificar.

## Rodando os testes

```bash
pytest
```
