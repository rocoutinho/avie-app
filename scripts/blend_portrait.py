"""Prepara um retrato para mesclar organicamente no fundo "seda escura"
das seções .lp-hero/.lp-about (ver .lp-silk-bg em static/css/style.css).

Duas etapas combinadas:

1. Recorte por cor: o fundo de estúdio original (preto liso no hero, parede
   verde no "sobre") é detectado por distância de cor até uma amostra dos
   cantos da própria foto e vira transparente/navy — isso é o que faz o
   FUNDO da foto desaparecer rente ao contorno da pessoa, em vez de deixar
   uma "mancha" escura em volta dela do tamanho de uma elipse genérica.
2. Vinheta elíptica suave (smoothstep, sem "quina" — o que gera anel visível
   numa máscara) só nas bordas do enquadramento, pra o retrato "flutuar" e
   dissolver no topo/base do recorte em vez de terminar num corte reto.

O rosto e o tronco ficam 100% nítidos (alpha=1, cor original) porque estão
bem distantes, em cor, do fundo de estúdio — só o próprio fundo e a faixa
externa da vinheta perdem opacidade.

Uso: `pip install pillow numpy`, ajustar os parâmetros por foto e rodar
`python scripts/blend_portrait.py` a partir da raiz do projeto sempre que
uma foto nova entrar no hero ou na seção "sobre".
"""
from PIL import Image, ImageFilter
import numpy as np

# Amostrado direto de static/img/silk-bg.jpg (ver generate_silk_bg.py),
# coluna central, do topo ao rodapé da área onde o retrato fica.
TARGET_TOP = (49, 60, 87)
TARGET_BOTTOM = (44, 56, 82)


def smoothstep(edge0, edge1, x):
    """Curva com derivada zero nas duas pontas — sem "quina" no início
    nem no fim da transição, que é o que o olho lê como anel visível
    numa máscara elíptica."""
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def _fit_background_field(arr, border_frac=0.045):
    """O fundo de estúdio não é uma cor sólida — tem vinheta (mais claro
    perto do centro, onde a luz principal bate, mais escuro nas bordas).
    Em vez de comparar cada pixel a UMA cor de referência (o que confunde
    esse brilho central do próprio fundo com a pessoa), ajusta um campo
    contínuo (polinômio quadrático em x,y) só com pixels da moldura da
    foto — sempre fundo puro — e usa esse campo como referência local em
    cada ponto da imagem."""
    h, w, _ = arr.shape
    bh, bw = max(4, int(h * border_frac)), max(4, int(w * border_frac))
    yy, xx = np.mgrid[0:h, 0:w]

    border = np.zeros((h, w), dtype=bool)
    border[:bh, :] = True
    border[-bh:, :] = True
    border[:, :bw] = True
    border[:, -bw:] = True

    xs = (xx[border].astype(np.float32) / w)
    ys = (yy[border].astype(np.float32) / h)
    A = np.stack([np.ones_like(xs), xs, ys, xs * xs, ys * ys, xs * ys], axis=1)
    samples = arr[border]  # N x 3

    coeffs, *_ = np.linalg.lstsq(A, samples, rcond=None)  # 6 x 3

    xf = (xx.astype(np.float32) / w).ravel()
    yf = (yy.astype(np.float32) / h).ravel()
    Afull = np.stack([np.ones_like(xf), xf, yf, xf * xf, yf * yf, xf * yf], axis=1)
    field = (Afull @ coeffs).reshape(h, w, 3)
    return field


def background_mask(arr, threshold=42, feather=3.0):
    """Confiança de 'é fundo de estúdio' por proximidade de cor ao campo de
    fundo ajustado (ver _fit_background_field, cobre a vinheta). Retorna 0
    (fundo) .. 1 (sujeito)."""
    ref_field = _fit_background_field(arr)
    dist = np.linalg.norm(arr - ref_field, axis=2)
    fg = np.clip(dist / threshold, 0, 1)
    fg_img = Image.fromarray((fg * 255).astype(np.uint8), "L")
    fg_img = fg_img.filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(fg_img).astype(np.float32) / 255.0


def process_portrait(src_path, dst_path, cx_frac, cy_frac, rx_frac, ry_frac,
                      fade_start=0.72, fade_end=1.05, bg_threshold=42):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    arr = np.array(im).astype(np.float32)

    fg_conf = background_mask(arr, threshold=bg_threshold)
    fg_conf = fg_conf ** 1.4  # empurra tons intermediários (sombra/transição no pano) pro lado do fundo

    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * cx_frac, h * cy_frac
    rx, ry = w * rx_frac, h * ry_frac
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    vignette = 1 - smoothstep(fade_start, fade_end, dist)

    alpha = fg_conf * vignette

    row_t = (yy / h)[..., None]
    target_field = np.array(TARGET_TOP) * (1 - row_t) + np.array(TARGET_BOTTOM) * row_t
    a3 = alpha[..., None]
    out_rgb = arr * a3 + target_field * (1 - a3)

    out = np.dstack([out_rgb, alpha * 255]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(dst_path)
    print(f"saved {dst_path} {Image.open(dst_path).size}")


if __name__ == "__main__":
    process_portrait(
        "static/img/fabiana-hero.jpg",
        "static/img/fabiana-hero-blend.png",
        cx_frac=0.5, cy_frac=0.40, rx_frac=0.44, ry_frac=0.42,
        fade_start=0.72, fade_end=1.05, bg_threshold=60,
    )

    process_portrait(
        "static/img/fabiana-sobre.jpg",
        "static/img/fabiana-sobre-blend.png",
        cx_frac=0.5, cy_frac=0.42, rx_frac=0.44, ry_frac=0.42,
        fade_start=0.72, fade_end=1.05, bg_threshold=140,
    )
