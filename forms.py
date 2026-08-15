from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DateTimeLocalField,
    DecimalField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from models import (
    BUDGET_RANGES,
    CLIENT_STATUSES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    LEAD_SOURCES,
    PAYMENT_STATUSES,
    REPORT_STATUSES,
)


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
    submit = SubmitField("Salvar")


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


class PaymentForm(FlaskForm):
    description = StringField("Descrição", validators=[DataRequired(), Length(max=255)])
    amount = DecimalField("Valor (R$)", validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField("Status", choices=PAYMENT_STATUSES)
    due_date = DateField("Vencimento", validators=[Optional()])
    submit = SubmitField("Salvar")
