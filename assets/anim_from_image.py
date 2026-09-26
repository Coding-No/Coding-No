#!/usr/bin/env python3
# LALA - Profile Art Animator: "Desa Malam" dari gambar kiriman user  (v2)
# Author: LALA
# Repo  : Coding-No/Coding-No (profile README)
#
# v2 = pelajaran dari v1:
#   - PAN parallax DIREMP: kamera geser bikin 48 frame beda total -> GIF
#     1,9 MB + komposisi kepotong (pohon ilang, bulan mepet pojok, kepala pusing).
#   - Sekarang: FRAME UTUH (komposisi asli user nol diubah), sorotan di
#     objek kecil. GIF jadi kecil karena 90% area identik antar frame.
#   - Struktur file GIF default = full canvas, jadi nol masalah "delta frame
#     nempel di kiri" yang biasanya bikin GIF hasil Pillow rusak.
#
# Kunci loop seamless: SEMUA animasi dihitung dari phase = frame/total * 2*pi.
# sin(0) == sin(2*pi) -> frame terakhir nyambung mulus ke frame pertama.
#
# Outline + bentuk dasar digambar ULANG dari BASE tiap frame -> nol ghosting.

import os
import math
import numpy as np
from PIL import Image

SRC = "/home/nopauwxp/.hermes/cache/images/img_dd6cb30f9cb1.jpg"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==== RESTORASI PIXEL ART ====
# Gambar kiriman 1280x714 tapi run-length median 1-2 px -> hasil upscale.
# Basis aslinya ~160x89. Downscale balik pakai NEAREST biar kotak pikselnya
# kembali tegas, bukan blur hasil LANCZOS.
GRID_W, GRID_H = 160, 89
SCALE = 6                    # 160*6 = 960 px lebar (muat GitHub, tetap tajam)
TOTAL = 60                   # 60 frame x 90ms = 5,4 detik per putaran
FPS = 11
COLORS = 64

W, H = GRID_W, GRID_H


def load_grid():
    im = Image.open(SRC).convert("RGB")
    return np.asarray(im.resize((GRID_W, GRID_H), Image.NEAREST)).astype(np.int16)


BASE = load_grid()


def rrect(a, x0, y0, x1, y1):
    return a[max(0, y0):min(H, y1), max(0, x0):min(W, x1)]


def _lum(a):
    return a[..., 0] * 0.30 + a[..., 1] * 0.59 + a[..., 2] * 0.11


# ==== MASK WILAYAH ====
lum = _lum(BASE)

# --- AIR SAWAH: biru/cyan di paruh bawah, tapi BUKAN padi gelap ---
water = np.zeros((H, W), bool)
water[int(H * 0.40):, :] = True
water &= (BASE[..., 2] > BASE[..., 0] + 8) & (BASE[..., 2] > 42)

water_rows = [y for y in range(int(H * 0.40), H) if water[y].sum() > 26]

# --- JENDELA & LENTERA desa: kuning/oranye terang ---
glow_src = np.zeros((H, W), bool)
glow_src[int(H * 0.30):int(H * 0.62), int(W * 0.45):] = True     # kluster kanan
glow_src |= (BASE[..., 0] > 140) & (BASE[..., 1] > 100) & (BASE[..., 2] < 160) & ((BASE[..., 0] - BASE[..., 2]) > 45)

# --- BINTANG: titik terang di langit atas ---
sky = np.zeros((H, W), bool)
sky[:int(H * 0.40), :] = True
star_pool = sky & (lum > 150)
sy, sx = np.where(star_pool)

rng = np.random.default_rng(6767)

# stok kunang-kunang: area padi/rumput bawah, nol di langit
ff_zone = np.zeros((H, W), bool)
ff_zone[int(H * 0.44):, :] = True
ff_zone &= ~((BASE[..., 0] > 150) & (BASE[..., 2] < 150))       # hindari jendela
fy, fx = np.where(ff_zone)
FF_N = 46
pick = rng.choice(len(fx), min(FF_N, len(fx)), replace=False)
ff_x, ff_y = fx[pick], fy[pick]
# Fase disimpan sebagai FRAKSI dari 2pi, tempo harus BULAT:
# phase_i = ph * cycle_i + 2pi*k_i/total  ->  nol berubah saat f->f+total.
ff_cycle = rng.integers(1, 4, FF_N).astype(float)          # 1,2,3 siklus per loop
ff_phase = rng.integers(0, TOTAL, FF_N).astype(float) * 2 * math.pi / TOTAL
ff_amp = 0.8 + rng.random(FF_N) * 2.4
ff_bright = 0.55 + rng.random(FF_N) * 0.45

# stok bintang kelap-kelip (ambil maks 40 titik paling terang)
if len(sx) > 40:
    sel = rng.choice(len(sx), 40, replace=False)
    sx, sy = sx[sel], sy[sel]
STAR_N = len(sx)
star_cycle = rng.integers(1, 4, STAR_N).astype(float)          # 1,2,3 siklus per loop
star_phase = rng.integers(0, TOTAL, STAR_N).astype(float) * 2 * math.pi / TOTAL

# stok padi yang rayap: baris padi di paruh bawah
RICE_ROWS = [y for y in range(int(H * 0.45), int(H * 0.80)) if (lum[y] > 40).sum() > 30]


def build_frame(f, total):
    """1 frame. Semua dari phase -> loop mulus. Outline digambar ulang."""
    ph = 2 * math.pi * f / total
    a = BASE.astype(np.float32).copy()

    # ---------- 1) BINTANG kelap-kelip (individu, fase acak) ----------
    for i in range(STAR_N):
        tw = 0.40 + 0.60 * (0.5 + 0.5 * math.sin(ph * star_cycle[i] + star_phase[i]))
        y, x = int(sy[i]), int(sx[i])
        a[y, x] = np.clip(a[y, x] * tw + 245 * (tw ** 4), 0, 255)

    # ---------- 2) JENDELA: napas cahaya hangat + halo tetangga ----------
    breathe = 0.78 + 0.22 * (0.5 + 0.5 * math.sin(ph * 1.0))
    g = glow_src & (a[..., 0] > 110)
    a[g] = np.clip(a[g] * breathe + 40 * breathe, 0, 255)
    # halo: tetangga glow ikut naik tipis -> lampu kerasa "nyala"
    hh = np.zeros((H, W), bool)
    hh[:, 1:] |= g[:, :-1]; hh[:, :-1] |= g[:, 1:]
    hh[1:, :] |= g[:-1, :]; hh[:-1, :] |= g[1:, :]
    hh &= ~g
    hh &= (a[..., 0] > 70) & (a[..., 2] < 160)
    a[hh] = np.clip(a[hh] * (0.90 + 0.10 * breathe) + 16 * breathe, 0, 255)

    # ---------- 3) KILAU AIR: streak digeser bolak-balik 1 px ----------
    # Nol pan, cuma baris air yang geser -> file tetap kecil + komposisi utuh.
    for y in water_rows:
        sh = int(round(math.sin(ph * 1.0 + y * 0.42) * 1.4))
        if sh:
            a[y] = np.roll(a[y], sh, axis=0)

    # ---------- 4) PADI: rayap 1 px kena angin ----------
    sway = int(round(math.sin(ph * 0.9) * 1.4))
    if sway and RICE_ROWS:
        y0, y1 = RICE_ROWS[0], RICE_ROWS[-1] + 1
        band = a[y0:y1].copy()
        a[y0:y1] = np.clip(band * 0.97 + np.roll(band, sway, axis=1) * 0.03, 0, 255)

    # ---------- 5) KUNANG-KUNANG: orb 5 piksel + bob + kedip ----------
    for i in range(FF_N):
        # semua pakai kelipatan bulat ph -> t(f==total) == t(0)
        t = ph * ff_cycle[i] + ff_phase[i]
        bx = int(round(math.sin(t) * ff_amp[i]))
        by = int(round(math.cos(t * 2.0) * ff_amp[i] * 0.75))
        bi = 0.5 + 0.5 * math.sin(t * 3.0)
        b = ff_bright[i] * (0.02 + 0.98 * bi)      # turun sampe nyaris mati -> kedip jelas
        if b < 0.10:
            continue                               # fase gelap: bener-bener nol piksel
        y = int(np.clip(ff_y[i] + by, 0, H - 1))
        x = int(np.clip(ff_x[i] + bx, 0, W - 1))
        core = np.array([255, 245, 168], np.float32) * b
        halo = np.array([196, 216, 112], np.float32) * b * 0.46
        # cross 5 piksel + 4 diagonal -> bias lebih kelihatan di layar kecil
        for dy, dx, col in ((0, 0, core),
                            (-1, 0, halo), (1, 0, halo), (0, -1, halo), (0, 1, halo),
                            (-1, -1, halo), (-1, 1, halo), (1, -1, halo), (1, 1, halo)):
            yy, xx = int(np.clip(y + dy, 0, H - 1)), int(np.clip(x + dx, 0, W - 1))
            k = 0.66 if (dy == 0 and dx == 0) else 0.30
            a[yy, xx] = np.clip(a[yy, xx] * (1 - k) + col * k, 0, 255)

    return a


def render_from(a):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    return img.resize((W * SCALE, H * SCALE), Image.NEAREST)


def render_frame(f, total):
    return render_from(build_frame(f, total))


def make_gif(total=TOTAL, fps=FPS, name="desa-malam.gif", colors=COLORS):
    """Nol trik. Loop mulus karena SEMUA sinyal periodik atas `total`."""
    frames = [render_frame(f, total) for f in range(total)]
    pal = frames[0].convert("P", palette=Image.ADAPTIVE, colors=colors)
    pf = [x.quantize(palette=pal, dither=Image.NONE) for x in frames]
    out = os.path.join(OUT_DIR, name)
    pf[0].save(out, save_all=True, append_images=pf[1:],
               duration=int(1000 / fps), loop=0, optimize=True, disposal=1)
    return out, len(frames), os.path.getsize(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Animasikan gambar pixel-art jadi GIF loop mulus (LALA)")
    ap.add_argument("--frames", type=int, default=TOTAL)
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--colors", type=int, default=COLORS)
    ap.add_argument("--name", default="desa-malam.gif")
    ns = ap.parse_args()
    p, n, sz = make_gif(ns.frames, ns.fps, ns.name, ns.colors)
    print(f"OK {p}  {n} frame  {sz/1024:.0f} KB")
