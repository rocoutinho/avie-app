from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    DateTimeLocalField,
    DecimalField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp

from models import (
    BUDGET_RANGES,
    CLIENT_STATUSES,
    CLOSET_ITEM_CATEGORIES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    LEAD_SOURCES,
    LOOK_MOMENTS,
    PAYMENT_STATUSES,
    REPORT_STATUSES,
)

# Extensões aceitas nos campos de upload de imagem (Cloudinary) — ver
# image_upload.py. Mesma lista pros 3 campos que ganharam upload.
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif"]


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")


class DiagnosticForm(FlaskForm):
    full_name = StringField(
        "Nome completo",
        validators=[DataRequired(), Length(max=150)],
        render_kw={"autocomplete": "name"},
    )
    email = StringField(
        "E-mail",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"type": "email", "inputmode": "email", "autocomplete": "email"},
    )
    phone = StringField(
        "WhatsApp / Telefone",
        validators=[DataRequired(), Length(max=30)],
        render_kw={"type": "tel", "inputmode": "tel", "autocomplete": "tel"},
    )
    instagram = StringField(
        "Instagram (opcional)",
        validators=[Optional(), Length(max=100)],
        render_kw={"autocomplete": "off"},
    )
    source = SelectField("Como você conheceu o trabalho?", choices=LEAD_SOURCES)

    # Atribuição de campanha — preenchidos via JS a partir de utm_* na URL
    # ou da sessão (capturados na primeira visita, ver blueprints/public.py).
    utm_source = HiddenField()
    utm_medium = HiddenField()
    utm_campaign = HiddenField()
    utm_content = HiddenField()
    utm_term = HiddenField()

    objetivo_profissional = TextAreaField(
        "Qual é o seu principal objetivo profissional hoje?", validators=[DataRequired()]
    )
    momento_carreira = TextAreaField(
        "Como você descreveria o momento atual da sua carreira?", validators=[DataRequired()]
    )
    como_quer_ser_percebida = TextAreaField(
        "Como você gostaria de ser percebida profissionalmente?", validators=[DataRequired()]
    )
    desafios_imagem = TextAreaField(
        "Quais são seus maiores desafios com imagem e estilo hoje?", validators=[DataRequired()]
    )
    ambiente_trabalho = StringField(
        "Como é o ambiente / cultura do seu trabalho?", validators=[Optional(), Length(max=255)]
    )
    estilo_atual = TextAreaField("Como você descreveria seu estilo atual?", validators=[Optional()])
    cores_preferidas = StringField(
        "Cores que você mais gosta de usar", validators=[Optional(), Length(max=255)]
    )
    referencias_estilo = StringField(
        "Referências de estilo que te inspiram", validators=[Optional(), Length(max=255)]
    )
    orcamento_faixa = SelectField("Faixa de investimento pretendida", choices=BUDGET_RANGES)
    consent = BooleanField(
        "Li e concordo com o uso dos meus dados conforme a Política de Privacidade",
        validators=[DataRequired(message="É necessário aceitar para continuar.")],
    )
    # Honeypot: campo invisível para humanos, atrai bots de spam. Deve ficar vazio.
    website = StringField("Deixe este campo em branco", validators=[Optional(), Length(max=0)])
    submit = SubmitField("Enviar diagnóstico")


class ClientForm(FlaskForm):
    full_name = StringField("Nome completo", validators=[DataRequired(), Length(max=150)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField("Telefone", validators=[Optional(), Length(max=30)])
    instagram = StringField("Instagram", validators=[Optional(), Length(max=100)])
    source = SelectField("Origem", choices=LEAD_SOURCES)
    status = SelectField("Status", choices=CLIENT_STATUSES)
    notes = TextAreaField("Notas internas", validators=[Optional()])
    style_notes = TextAreaField(
        "Sobre a cliente (silhueta, formato do rosto, visagismo...)", validators=[Optional()]
    )

    # "Minha Identidade" (MVP Minha Imagem) — ver models.py:Client.
    idade = IntegerField("Idade", validators=[Optional(), NumberRange(min=0, max=120)])
    profissao = StringField("Profissão", validators=[Optional(), Length(max=150)])
    cidade = StringField("Cidade", validators=[Optional(), Length(max=100)])
    foto_perfil = StringField(
        "Link da foto de perfil (opcional — Google Drive, Dropbox etc.)",
        validators=[Optional(), Length(max=500)],
    )
    foto_perfil_arquivo = FileField(
        "...ou envie um arquivo (substitui o link acima, se preenchido)",
        validators=[Optional(), FileAllowed(IMAGE_EXTENSIONS, "Apenas imagens.")],
    )
    identidade_rotina = TextAreaField(
        "Quem sou (rotina, momentos importantes)", validators=[Optional()], render_kw={"rows": 4}
    )
    identidade_objetivo = TextAreaField(
        "Como quero ser percebida (objetivos, imagem desejada, desafios)",
        validators=[Optional()],
        render_kw={"rows": 4},
    )
    identidade_estilo = TextAreaField(
        "Meu estilo (referências, preferências, marcas, inspirações)",
        validators=[Optional()],
        render_kw={"rows": 4},
    )

    submit = SubmitField("Salvar")


class SetClientPasswordForm(FlaskForm):
    password = PasswordField(
        "Senha de acesso do cliente",
        validators=[DataRequired(), Length(min=8, message="Pelo menos 8 caracteres.")],
    )
    submit = SubmitField("Definir senha de acesso")


class DossieServicesForm(FlaskForm):
    """Campos do dossiê em si (título, PDF, os 4 serviços) — compartilhados
    entre o cadastro inicial (ClientDossieForm) e a edição de um dossiê já
    existente (EditDossieForm), pra manter os dois formulários em sincronia
    sem duplicar os campos."""

    dossie_title = StringField(
        "Título do dossiê", validators=[DataRequired(), Length(max=255)]
    )
    pdf_url = StringField(
        "Link do PDF do dossiê (opcional — Google Drive, Dropbox etc.)",
        validators=[Optional(), Length(max=500)],
    )
    estilo_pessoal = TextAreaField(
        "Estilo", validators=[Optional()], render_kw={"rows": 4}
    )
    proporcoes = TextAreaField(
        "Biotipo", validators=[Optional()], render_kw={"rows": 4}
    )
    coloracao = TextAreaField(
        "Cores", validators=[Optional()], render_kw={"rows": 4}
    )
    visagismo = TextAreaField(
        "Visagismo", validators=[Optional()], render_kw={"rows": 4}
    )
    arquetipos = TextAreaField(
        "Arquétipos", validators=[Optional()], render_kw={"rows": 4}
    )


class ClientDossieForm(DossieServicesForm):
    """Cadastro consolidado para clientes que já receberam o dossiê fora do
    sistema — cria/atualiza o Client, registra o dossiê como StyleReport
    enviado, e gera o acesso à área do cliente numa única submissão (ver
    blueprints/clients.py:new_client_with_dossie)."""

    full_name = StringField("Nome completo", validators=[DataRequired(), Length(max=150)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField(
        "WhatsApp / Telefone", validators=[DataRequired(), Length(max=30)]
    )
    submit = SubmitField("Concluir cadastro e enviar acesso")


class EditDossieForm(DossieServicesForm):
    """Edição de um dossiê já existente (blueprints/clients.py:edit_dossie)
    — não mexe em identidade/acesso do cliente, só no conteúdo do dossiê."""

    submit = SubmitField("Salvar dossiê")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "Nova senha", validators=[DataRequired(), Length(min=8, message="Pelo menos 8 caracteres.")]
    )
    confirm = PasswordField(
        "Confirmar nova senha",
        validators=[DataRequired(), EqualTo("password", message="As senhas não coincidem.")],
    )
    submit = SubmitField("Definir minha senha")


class ConsultationForm(FlaskForm):
    tipo = SelectField("Tipo de consulta", choices=CONSULTATION_TYPES)
    scheduled_at = DateTimeLocalField(
        "Data e hora", format="%Y-%m-%dT%H:%M", validators=[DataRequired()]
    )
    duration_minutes = IntegerField(
        "Duração (minutos)", default=60, validators=[DataRequired(), NumberRange(min=15, max=480)]
    )
    status = SelectField("Status", choices=CONSULTATION_STATUSES)
    notes = TextAreaField("Notas", validators=[Optional()])
    submit = SubmitField("Salvar")


class ReportForm(FlaskForm):
    title = StringField("Título", validators=[DataRequired(), Length(max=255)])
    content = TextAreaField("Conteúdo", validators=[DataRequired()])
    status = SelectField("Status", choices=REPORT_STATUSES)
    submit = SubmitField("Salvar relatório")


class BlogPostForm(FlaskForm):
    slug = StringField(
        "Slug (define a URL: /blog/o-que-voce-escrever-aqui)",
        validators=[
            DataRequired(),
            Length(max=120),
            Regexp(
                r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
                message="Use apenas letras minúsculas, números e hífens (ex: 5-erros-de-imagem-profissional).",
            ),
        ],
    )
    title = StringField("Título", validators=[DataRequired(), Length(max=255)])
    excerpt = TextAreaField(
        "Resumo (aparece na listagem do blog e como descrição ao compartilhar no LinkedIn)",
        validators=[DataRequired(), Length(max=300)],
    )
    cover_image_url = StringField(
        "URL da imagem de capa (opcional — cole o link de uma imagem já publicada)",
        validators=[Optional(), Length(max=500)],
    )
    author_name = StringField(
        "Assinatura (nome exibido como autora do artigo)",
        validators=[DataRequired(), Length(max=150)],
        default="Fabiana Montemor",
    )
    body_markdown = TextAreaField(
        "Conteúdo (Markdown — ## para subtítulo, **negrito**, - para lista, etc. "
        "Não repita o título aqui, a página já mostra ele sozinho no topo.)",
        validators=[DataRequired()],
        render_kw={"rows": 18},
    )
    submit = SubmitField("Salvar rascunho")


class BlogPostReviewForm(FlaskForm):
    review_note = TextAreaField("Motivo da recusa (opcional)", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Recusar")


class PaymentForm(FlaskForm):
    description = StringField("Descrição", validators=[DataRequired(), Length(max=255)])
    amount = DecimalField("Valor (R$)", validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField("Status", choices=PAYMENT_STATUSES)
    due_date = DateField("Vencimento", validators=[Optional()])
    submit = SubmitField("Salvar")


class ClosetItemForm(FlaskForm):
    category = SelectField("Categoria", choices=CLOSET_ITEM_CATEGORIES)
    description = StringField("Descrição da peça", validators=[DataRequired(), Length(max=255)])
    photo_url = StringField("Link da foto (opcional)", validators=[Optional(), Length(max=500)])
    photo_file = FileField(
        "...ou envie um arquivo (substitui o link acima, se preenchido)",
        validators=[Optional(), FileAllowed(IMAGE_EXTENSIONS, "Apenas imagens.")],
    )
    notes = TextAreaField("Notas (opcional)", validators=[Optional()])
    submit = SubmitField("Salvar")


class ShoppingListItemForm(FlaskForm):
    category = SelectField("Categoria", choices=CLOSET_ITEM_CATEGORIES)
    description = StringField("Peça sugerida", validators=[DataRequired(), Length(max=255)])
    motivo = TextAreaField("Motivo da recomendação (o porquê)", validators=[Optional()])
    photo_url = StringField("Link da foto (opcional)", validators=[Optional(), Length(max=500)])
    photo_file = FileField(
        "...ou envie um arquivo (substitui o link acima, se preenchido)",
        validators=[Optional(), FileAllowed(IMAGE_EXTENSIONS, "Apenas imagens.")],
    )
    link_compra = StringField(
        "Link de compra (opcional, parceiro)", validators=[Optional(), Length(max=500)]
    )
    notes = TextAreaField("Notas (opcional)", validators=[Optional()])
    submit = SubmitField("Salvar")


class StyleAssessmentForm(FlaskForm):
    estacao_cor = StringField(
        "Estação de cor (ex: Outono suave)", validators=[Optional(), Length(max=100)]
    )
    paleta_principal = StringField(
        "Paleta principal (ex: tons terrosos e neutros)", validators=[Optional(), Length(max=255)]
    )
    estilo_predominante = StringField(
        "Estilo predominante (ex: Elegante contemporâneo)",
        validators=[Optional(), Length(max=100)],
    )
    estilo_complementar = StringField(
        "Estilo complementar (opcional)", validators=[Optional(), Length(max=100)]
    )
    mensagem_desejada = StringField(
        "Mensagem que a cliente quer transmitir (ex: confiança e sofisticação)",
        validators=[Optional(), Length(max=255)],
    )
    submit = SubmitField("Salvar")


class LookForm(FlaskForm):
    nome = StringField("Nome do look", validators=[DataRequired(), Length(max=150)])
    photo_url = StringField(
        "Link da foto principal (opcional)", validators=[Optional(), Length(max=500)]
    )
    photo_file = FileField(
        "...ou envie um arquivo (substitui o link acima, se preenchido)",
        validators=[Optional(), FileAllowed(IMAGE_EXTENSIONS, "Apenas imagens.")],
    )
    momento = SelectField("Momento", choices=LOOK_MOMENTS)
    ocasiao = StringField("Ocasião (opcional)", validators=[Optional(), Length(max=150)])
    descricao = TextAreaField("Descrição (opcional)", validators=[Optional()])
    mensagem_transmitida = StringField(
        "Mensagem que o look transmite (opcional)", validators=[Optional(), Length(max=255)]
    )
    closet_item_ids = SelectMultipleField(
        "Peças do closet usadas neste look", coerce=int, validators=[Optional()]
    )
    submit = SubmitField("Salvar")


class EbookForm(FlaskForm):
    title = StringField("Título do ebook", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField(
        "Descrição (o que a pessoa recebe, mostrado na página de captura)",
        validators=[DataRequired()],
    )
    cover_image_url = StringField(
        "URL da imagem de capa (opcional)", validators=[Optional(), Length(max=500)]
    )
    file_url = StringField(
        "Link do PDF (Google Drive, Dropbox etc. — configurado como \"qualquer "
        "pessoa com o link pode visualizar\")",
        validators=[DataRequired(), Length(max=500)],
    )
    active = BooleanField(
        "Ativo (é este que aparece em /ebook — só um fica ativo por vez)",
        default=True,
    )
    submit = SubmitField("Salvar")


class EbookDownloadForm(FlaskForm):
    full_name = StringField(
        "Nome completo",
        validators=[DataRequired(), Length(max=150)],
        render_kw={"autocomplete": "name"},
    )
    email = StringField(
        "E-mail",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"type": "email", "inputmode": "email", "autocomplete": "email"},
    )
    phone = StringField(
        "WhatsApp / Telefone",
        validators=[DataRequired(), Length(max=30)],
        render_kw={"type": "tel", "inputmode": "tel", "autocomplete": "tel"},
    )
    wants_diagnostic = BooleanField("Quero receber um diagnóstico gratuito, sem compromisso")
    # Honeypot: campo invisível para humanos, atrai bots de spam. Deve ficar vazio.
    website = StringField("Deixe este campo em branco", validators=[Optional(), Length(max=0)])
    submit = SubmitField("Quero baixar o ebook")
