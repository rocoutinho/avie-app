import markdown as _markdown
from markupsafe import Markup

_PT_MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def render_markdown(text):
    """Converte o Markdown de um BlogPost.body_markdown pra HTML. O
    conteúdo só é escrito por staff autenticado (mesmo nível de confiança
    já dado a outros campos "URL/HTML crus" do sistema, como
    Campaign.hero_image_url) — não há sanitização adicional porque não é
    input de visitante público."""
    html = _markdown.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])
    return Markup(html)


def format_date_pt(value):
    """'%d de %B de %Y' via strftime depende do locale do servidor (em
    produção normalmente é C/en_US, o que renderiza 'August' em vez de
    'agosto') — monta a data com nomes de mês fixos em pt-BR."""
    if not value:
        return ""
    return f"{value.day} de {_PT_MONTHS[value.month - 1]} de {value.year}"
