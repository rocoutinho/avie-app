"""Prepara um retrato para mesclar organicamente no fundo "seda escura"
das seções .lp-hero/.lp-about (ver .lp-silk-bg em static/css/style.css).

Sem uma foto real de tecido, uma máscara CSS pura deixa uma "auréola"
visível (o degradê de opacidade revela o cinza do fundo de estúdio da
foto original por baixo). Aqui a mesclagem é feita no próprio pixel:
puxamos a cor pra o tom do navy de fundo ANTES de começar a reduzir o
alpha — assim quando a transparência entra, a cor já é quase idêntica
ao fundo, sem salto visível.

Uso: `pip install pillow numpy` (não são dependências do app, só desse
script), ajustar os parâmetros de cada retrato (centro/raio da elipse)
e rodar `python scripts/blend_portrait.py` a partir da raiz do projeto
sempre que uma foto nova entrar no hero ou na seção "sobre".
"""

from PIL import Image
import numpy as np

# Amostrado direto da página renderizada (.lp-silk-bg), coluna central,
# do topo ao rodapé da área onde o retrato fica.
TARGET_TOP = (37, 47, 69)
TARGET_BOTTOM = (33, 42, 59)


def smoothstep(edge0, edge1, x):
    """Curva com derivada zero nas duas pontas — sem "quina" no início
    nem no fim da transição, que é o que o olho lê como anel visível
    numa máscara elíptica."""
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def process_portrait(src_path, dst_path, cx_frac, cy_frac, rx_frac, ry_frac,
                      fade_start=0.10, fade_end=1.15):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    arr = np.array(im).astype(np.float32)

    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * cx_frac, h * cy_frac
    rx, ry = w * rx_frac, h * ry_frac
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)

    t = smoothstep(fade_start, fade_end, dist)

    row_t = (yy / h)[..., None]
    target_field = np.array(TARGET_TOP) * (1 - row_t) + np.array(TARGET_BOTTOM) * row_t
    arr = arr * (1 - t[..., None]) + target_field * t[..., None]
    alpha = 1 - t

    out = np.dstack([arr, alpha * 255]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(dst_path)
    print(f"saved {dst_path} {Image.open(dst_path).size}")


if __name__ == "__main__":
    # rx/ry precisam ser pequenos o bastante pra o fade TERMINAR (alpha
    # chegar a zero) antes da borda reta do quadro — do contrário fica
    # opaco até o corte reto e parece um recorte, não um esmaecer.
    process_portrait(
        "static/img/fabiana-hero.jpg",
        "static/img/fabiana-hero-blend.png",
        cx_frac=0.5, cy_frac=0.40, rx_frac=0.40, ry_frac=0.38,
        fade_start=0.08, fade_end=1.0,
    )

    process_portrait(
        "static/img/fabiana-sobre.jpg",
        "static/img/fabiana-sobre-blend.png",
        cx_frac=0.5, cy_frac=0.42, rx_frac=0.40, ry_frac=0.38,
        fade_start=0.08, fade_end=1.0,
    )
