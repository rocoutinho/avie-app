"""Gera uma textura procedural de "seda escura" com dobras suaves e brilho
dourado para o fundo de .lp-hero/.lp-about — substitui o degradê CSS plano
por uma imagem com relevo real: faixas diagonais largas (dobras), variação
orgânica de brilho e grão fino.

O ruído de larga escala é gerado numa grade baixa-resolução e reamostrado
por interpolação bicúbica (em vez de blur com raio grande): blur grande no
PIL vira uma aproximação por "box blur" que deixa degraus/contornos visíveis
em vez de uma superfície contínua — reamostragem bicúbica não tem esse
problema.

Uso: `pip install pillow numpy`, a partir da raiz do projeto:
`python scripts/generate_silk_bg.py`
"""
from PIL import Image, ImageFilter
import numpy as np

W, H = 2400, 1500

NAVY_DEEP = np.array([16, 21, 34])
NAVY_MID = np.array([36, 46, 71])
NAVY_LIT = np.array([66, 79, 111])
GOLD_SHEEN = np.array([160, 132, 80])


def make_noise(w, h, scale, seed):
    """Ruído suave em larga escala: grade de baixa resolução (~w/scale
    células) reamostrada por bicúbica. Normalizado pra média 0 / desvio 1."""
    rng = np.random.default_rng(seed)
    small_w = max(3, round(w / scale))
    small_h = max(3, round(h / scale))
    noise = rng.random((small_h, small_w)).astype(np.float32)
    im = Image.fromarray((noise * 255).astype(np.uint8), "L")
    im = im.resize((w, h), Image.BILINEAR)
    arr = np.asarray(im).astype(np.float32) / 255.0
    arr -= arr.mean()
    arr /= arr.std() + 1e-6
    return arr


def main():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = xx / W, yy / H

    angle = np.deg2rad(24)
    rot = u * np.cos(angle) + v * np.sin(angle)
    # o próprio eixo das ondas é distorcido por um campo suave e grande,
    # pra dobra não ficar perfeitamente reta/repetitiva
    warp = make_noise(W, H, 500, seed=31) * 0.14
    rot = rot + warp

    folds = (
        0.40 * np.sin(rot * 4.2 * np.pi)
        + 0.15 * np.sin(rot * 9.5 * np.pi + 1.1)
        + 0.06 * np.sin(rot * 19.0 * np.pi + 2.4)
    )
    folds += 0.22 * make_noise(W, H, 420, seed=7)
    folds += 0.08 * make_noise(W, H, 90, seed=11)

    tone = folds
    tone -= tone.min()
    tone /= tone.max()
    tone = tone ** 1.1

    cx, cy = 0.5, 0.28
    dist = np.sqrt(((u - cx) / 0.8) ** 2 + ((v - cy) / 0.95) ** 2)
    vignette = np.clip(1 - 0.22 * dist ** 2, 0.68, 1.0)
    tone *= vignette

    t = tone[..., None]
    low_mid = np.clip(t / 0.5, 0, 1)
    mid_hi = np.clip((t - 0.5) / 0.5, 0, 1)
    color = NAVY_DEEP * (1 - low_mid) + NAVY_MID * low_mid
    color = color * (1 - mid_hi) + NAVY_LIT * mid_hi

    # brilho dourado: manchas suaves e fixas (não derivadas do ruído das
    # dobras, que gerava respingos dourados soltos em vez de um sheen
    # coerente), nos mesmos pontos dos radial-gradients dourados usados em
    # .lp-silk-bg no CSS — mantém a identidade visual consistente.
    def soft_spot(cx_, cy_, rx_, ry_):
        d = np.sqrt(((u - cx_) / rx_) ** 2 + ((v - cy_) / ry_) ** 2)
        return np.clip(1 - d, 0, 1) ** 2

    gold_mix = (
        0.22 * soft_spot(0.16, 0.10, 0.5, 0.42)
        + 0.16 * soft_spot(0.90, 0.16, 0.42, 0.36)
        + 0.12 * soft_spot(0.78, 0.94, 0.55, 0.44)
    )[..., None]
    gold_mix = np.clip(gold_mix, 0, 0.42) * (0.35 + 0.65 * tone[..., None])
    color = color * (1 - gold_mix) + GOLD_SHEEN * gold_mix

    rng = np.random.default_rng(23)
    grain = (rng.random((H, W)).astype(np.float32) - 0.5)[..., None] * 7.0
    color = color + grain

    color = np.clip(color, 0, 255).astype(np.uint8)
    Image.fromarray(color, "RGB").save("static/img/silk-bg.jpg", quality=92)
    print("saved static/img/silk-bg.jpg", (W, H))


if __name__ == "__main__":
    main()
