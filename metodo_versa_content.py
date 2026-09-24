"""As 4 etapas do Método Versa — única fonte de verdade, usada pela página
pública (/metodo-versa) e pela seção correspondente do admin
(dashboard.metodo_versa). Existia só como HTML solto em
templates/metodo_versa.html antes das duas páginas existirem; virou dado
pra evitar as duas divergirem com o tempo. Não inventar etapas novas aqui —
ver CLAUDE.md."""

METODO_VERSA_STEPS = [
    {
        "n": 1,
        "title": "Diagnóstico",
        "description": "Mapeamento da sua imagem atual, seu momento de carreira e seus objetivos.",
    },
    {
        "n": 2,
        "title": "Estratégia",
        "description": "Definição do posicionamento de imagem alinhado à sua identidade e aos seus objetivos profissionais.",
    },
    {
        "n": 3,
        "title": "Transformação",
        "description": "Aplicação prática: estilo, coloração, visagismo e guarda-roupa estratégico.",
    },
    {
        "n": 4,
        "title": "Acompanhamento",
        "description": "Consolidação dos resultados e ajustes contínuos ao longo da sua jornada.",
    },
]
