"""Replace tiling game surfaces with new CC0 photo-scanned materials.

Where tools/reimagine_textures.py redraws the game's own textures, this swaps
a tiling surface (grass, dirt, cliff, brick, planks) for a different, real
material from ambientCG (https://ambientcg.com, CC0 1.0: free to use and
ship), then pulls it back to the game's look:

  colour  The material is tiled --repeat times across the texture, then its
          colours are moved onto the original's: 'organic' keeps the
          original's colour at large scale (its blotches and tints, which
          other terrain layers are painted to match) and takes everything
          finer from the material; 'global' (structured surfaces such as
          bricks, whose layout differs) matches only the overall colour and
          contrast.
  normal  The material's normal map, tiled the same way, replaces the game's
          normal map for that surface (the pairing is in the spec: the
          texture the same draws bind as their normal map). The game's
          normal-map convention (which way X and Y point) is measured from
          its own maps, see detect_convention.

Spec (JSON, default tools/material_swap.json):
  {"<colour hash>": {"material": "Grass004", "repeat": 2, "mode": "organic",
                     "normal": "<normal hash>" or null, "strength": 1.0,
                     "note": "..."}}

Output goes to <pack_root>/replace (the game's live texture folder); what was
there first is copied to <pack_root>/packs/pre-material so it can be put back
with --restore. Each swapped texture gets a <hash>.material marker.
"""

import argparse
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_textures as up  # noqa: E402  (texconv, encode_all)

Image.MAX_IMAGE_PIXELS = None
USER_AGENT = 'material-swap/1.0'


# --- materials -----------------------------------------------------------------

def fetch_material(cache, asset, res):
    """Download and unpack <asset>_<res>-JPG.zip once; returns its folder."""
    folder = os.path.join(cache, f'{asset}_{res}')
    if os.path.isdir(folder) and glob.glob(os.path.join(folder, '*Color.jpg')):
        return folder
    url = f'https://ambientcg.com/get?file={asset}_{res}-JPG.zip'
    print(f'  downloading {asset} ({res})')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            base = os.path.basename(name)
            # Only the flat maps; never write outside the folder.
            if base and base.lower().endswith(('.jpg', '.png')) and '/' not in base and '\\' not in base:
                with open(os.path.join(folder, base), 'wb') as f:
                    f.write(z.read(name))
    return folder


def material_map(folder, kind):
    hits = sorted(glob.glob(os.path.join(folder, f'*_{kind}.jpg')) + glob.glob(os.path.join(folder, f'*_{kind}.png')))
    return Image.open(hits[0]) if hits else None


# --- image helpers -------------------------------------------------------------

def gauss_wrap(a, sigma):
    """Gaussian blur of a 2D array with wrap-around edges (tiling textures)."""
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    k = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(a) * k, s=(h, w)).astype(np.float32)


def tile_to(img, repeat, size, resample=Image.LANCZOS):
    """The image tiled repeat x repeat, resized to size (w, h)."""
    a = np.asarray(img)
    a = np.tile(a, (repeat, repeat) + (1,) * (a.ndim - 2))
    return Image.fromarray(a).resize(size, resample)


# sRGB-ish opponent space: luma plus two chroma axes. Good enough for moving
# a palette; the swap never leaves the game's own colour range.
M = np.array([[0.299, 0.587, 0.114], [0.5, -0.4187, -0.0813], [-0.1687, -0.3313, 0.5]], np.float32)
MI = np.linalg.inv(M).astype(np.float32)


def to_opp(rgb):
    return rgb @ M.T


def from_opp(opp):
    return np.clip(opp @ MI.T, 0.0, 1.0)


def match_colour(new, orig, mode, detail, chroma=None):
    """new, orig: float RGB (h, w, 3) in 0..1 at the output size."""
    n, o = to_opp(new), to_opp(orig)
    out = np.empty_like(n)
    if mode == 'organic':
        sigma = new.shape[1] / 96.0
        for c in range(3):
            o_lo = gauss_wrap(o[..., c], sigma)
            n_lo = gauss_wrap(n[..., c], sigma)
            n_hi = n[..., c] - n_lo
            o_hi_sd = float(np.std(o[..., c] - o_lo)) + 1e-4
            n_hi_sd = float(np.std(n_hi)) + 1e-4
            # Fine detail at the original's contrast (a little more for luma:
            # the point is a crisper surface), chroma detail kept calmer.
            gain = (o_hi_sd / n_hi_sd) * (detail if c == 0 else 0.8)
            out[..., c] = o_lo + n_hi * gain
    else:
        sigma = new.shape[1] / 4.0
        for c in range(3):
            o_lo = gauss_wrap(o[..., c], sigma)
            nc = n[..., c]
            oc = o[..., c] - o_lo + o_lo.mean()  # the original minus its broad shading
            gain = (float(np.std(oc)) + 1e-4) / (float(np.std(nc)) + 1e-4) * (detail if c == 0 else (0.6 if chroma is None else chroma))
            out[..., c] = (nc - nc.mean()) * gain + o_lo
    return from_opp(out)


# --- normal maps ---------------------------------------------------------------

def decode_dds(tools, path, work):
    up.texconv(tools, ['-ft', 'png', '-f', 'R8G8B8A8_UNORM', '-o', work, path])
    png = os.path.join(work, os.path.splitext(os.path.basename(path))[0] + '.png')
    return Image.open(png).convert('RGBA')


def detect_convention(colour, normal):
    """Signs (sx, sy) such that the game's normal = (sx*nx, sy*ny) for a
    surface whose height rises with brightness, with nx, ny in image axes
    (x right, y down) in the 'height gradient' sense: n ~ (-dh/dx, -dh/dy).
    Measured by correlating the game's map with the gradient of its own
    colour texture's brightness (dark mortar and cracks are low)."""
    w, h = normal.size
    lum = np.asarray(colour.convert('L').resize((w, h), Image.LANCZOS), np.float32) / 255.0
    lum = lum - gauss_wrap(lum, w / 32.0)
    lum = gauss_wrap(lum, 1.0)
    gx = (np.roll(lum, -1, 1) - np.roll(lum, 1, 1)) * 0.5
    gy = (np.roll(lum, -1, 0) - np.roll(lum, 1, 0)) * 0.5
    a = np.asarray(normal, np.float32) / 127.5 - 1.0
    r, g = a[..., 0], a[..., 1]

    def corr(p, q):
        p, q = p - p.mean(), q - q.mean()
        return float((p * q).sum() / (np.sqrt((p * p).sum() * (q * q).sum()) + 1e-9))

    return {'r~-gx': corr(r, -gx), 'g~-gy': corr(g, -gy), 'r~-gy': corr(r, -gy), 'g~-gx': corr(g, -gx)}


def build_normal(mat_normal_gl, repeat, size, strength, sx, sy):
    """ambientCG NormalGL (x right, y UP the image) -> game convention."""
    a = np.asarray(mat_normal_gl.convert('RGB'), np.float32)
    a = np.tile(a, (repeat, repeat, 1))
    comps = [np.asarray(Image.fromarray(a[..., c]).resize(size, Image.LANCZOS), np.float32) / 127.5 - 1.0
             for c in range(3)]
    x, y_up, z = comps
    # Image-axis gradient sense: +x right, +y DOWN the image.
    x, y = x * strength, -y_up * strength
    z = np.maximum(z, 0.05)
    n = np.sqrt(x * x + y * y + z * z) + 1e-6
    x, y = sx * x / n, sy * y / n
    out = np.zeros(x.shape + (4,), np.uint8)
    out[..., 0] = np.clip((x * 0.5 + 0.5) * 255 + 0.5, 0, 255)
    out[..., 1] = np.clip((y * 0.5 + 0.5) * 255 + 0.5, 0, 255)
    out[..., 3] = 255
    return Image.fromarray(out, 'RGBA')


# --- main ----------------------------------------------------------------------

def dump_path(pack_root, h):
    hits = glob.glob(os.path.join(pack_root, 'dump', h + '_*.dds'))
    if not hits:
        raise SystemExit(f'{h}: no dump (play past it with texture_dump on)')
    return hits[0]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pack_root', help="the game's textures folder (dump/, replace/)")
    ap.add_argument('--spec', default=os.path.join(here, 'material_swap.json'))
    ap.add_argument('--out', help='output folder (default <pack_root>/replace)')
    ap.add_argument('--tools', default=os.path.join(repo, 'out', 'tooling', 'upscale'))
    ap.add_argument('--cache', default=os.path.join(repo, 'out', 'tooling', 'materials'))
    ap.add_argument('--res', default='2K', help='ambientCG resolution to download (1K, 2K, 4K)')
    ap.add_argument('--scale', type=int, default=2, help='output size = this x the game texture')
    ap.add_argument('--max-out', type=int, default=2048)
    ap.add_argument('--detail', type=float, default=1.15, help='luma detail gain over the original')
    ap.add_argument('--only', default='', help='comma-separated hash prefixes')
    ap.add_argument('--preview', help='write before/after PNGs here')
    ap.add_argument('--no-install', action='store_true', help='only write --preview images')
    ap.add_argument('--restore', action='store_true', help='put back what the swap replaced')
    ap.add_argument('--convention', default='', help='force normal signs "sx,sy" (default: measured)')
    args = ap.parse_args()

    out = args.out or os.path.join(args.pack_root, 'replace')
    backup = os.path.join(args.pack_root, 'packs', 'pre-material')
    spec = json.load(open(args.spec, encoding='utf-8'))
    spec = {h: v for h, v in spec.items() if not h.startswith('_')}
    only = [p.upper() for p in args.only.split(',') if p]
    if only:
        spec = {h: v for h, v in spec.items() if any(h.startswith(p) for p in only)}

    if args.restore:
        for h, v in spec.items():
            for hh in [h] + ([v['normal']] if v.get('normal') else []):
                src = os.path.join(backup, hh + '.dds')
                dst = os.path.join(out, hh + '.dds')
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                elif os.path.exists(dst):
                    os.remove(dst)  # there was no replacement before the swap
                for m in glob.glob(os.path.join(out, hh + '.material')):
                    os.remove(m)
        print(f'restored {len(spec)} surfaces')
        return 0

    work = tempfile.mkdtemp(prefix='matswap_')
    try:
        staged = os.path.join(work, 'staged')
        encoded = os.path.join(work, 'encoded')
        dec = os.path.join(work, 'dec')
        for d in (staged, encoded, dec):
            os.makedirs(d)
        if args.preview:
            os.makedirs(args.preview, exist_ok=True)

        # The game's normal convention, measured over every paired map.
        measured = {}
        if args.convention:
            sx, sy = (float(s) for s in args.convention.split(','))
        else:
            votes = {'r~-gx': [], 'g~-gy': [], 'r~-gy': [], 'g~-gx': []}
            measured = {}
            for h, v in spec.items():
                if v.get('normal'):
                    c = decode_dds(args.tools, dump_path(args.pack_root, h), dec)
                    nm = decode_dds(args.tools, dump_path(args.pack_root, v['normal']), dec)
                    r = detect_convention(c, nm)
                    print(f"  convention {h[:8]}/{v['normal'][:8]}: " +
                          ' '.join(f'{k} {x:+.2f}' for k, x in r.items()))
                    measured[h] = r
                    for k in votes:
                        votes[k].append(r[k])
            med = {k: float(np.median(x)) for k, x in votes.items() if x}
            if not med:
                sx = sy = 1.0
            else:
                if max(abs(med['r~-gy']), abs(med['g~-gx'])) > max(abs(med['r~-gx']), abs(med['g~-gy'])):
                    raise SystemExit(f'normal maps look axis-swapped ({med}); pass --convention')
                sx = 1.0 if med['r~-gx'] >= 0 else -1.0
                sy = 1.0 if med['g~-gy'] >= 0 else -1.0
                print(f'  normal convention: x {sx:+.0f}, y {sy:+.0f}  (median {med})')

        jobs = []
        for h, v in spec.items():
            folder = fetch_material(args.cache, v['material'], args.res)
            orig = decode_dds(args.tools, dump_path(args.pack_root, h), dec).convert('RGB')
            ow, oh = orig.size
            k = max(1, min(args.scale, args.max_out // max(ow, oh)))
            size = (ow * k, oh * k)
            repeat = int(v.get('repeat', 1))
            mat = tile_to(material_map(folder, 'Color').convert('RGB'), repeat, size)
            o_up = np.asarray(orig.resize(size, Image.LANCZOS), np.float32) / 255.0
            res = match_colour(np.asarray(mat, np.float32) / 255.0, o_up, v.get('mode', 'organic'),
                               float(v.get('detail', args.detail)), v.get('chroma'))
            res_img = Image.fromarray((res * 255 + 0.5).astype(np.uint8), 'RGB')
            png = os.path.join(staged, h + '.png')
            res_img.save(png)
            jobs.append((png, 'BC7_UNORM', False))
            line = f"  {h} {v['material']} x{repeat} {v.get('mode', 'organic')} -> {size[0]}x{size[1]}"
            if args.preview:
                orig.resize(size, Image.LANCZOS).save(os.path.join(args.preview, f'{h}_before.png'))
                res_img.save(os.path.join(args.preview, f'{h}_after.png'))
            if v.get('normal'):
                nh = v['normal']
                # <hash>_<w>x<h>_<fmt>.dds
                nw, nhh = (int(s) for s in os.path.basename(dump_path(args.pack_root, nh)).split('_')[1].split('x'))
                nk = max(1, min(args.scale, args.max_out // max(nw, nhh)))
                # A map whose own correlation is clear keeps its own signs
                # (some walls are mirrored); unclear ones use the majority.
                m = measured.get(h, {})
                tx = (1.0 if m['r~-gx'] > 0 else -1.0) if abs(m.get('r~-gx', 0)) > 0.3 else sx
                ty = (1.0 if m['g~-gy'] > 0 else -1.0) if abs(m.get('g~-gy', 0)) > 0.3 else sy
                nimg = build_normal(material_map(folder, 'NormalGL'), repeat, (nw * nk, nhh * nk),
                                    float(v.get('strength', 1.0)), tx, ty)
                npng = os.path.join(staged, nh + '.png')
                nimg.save(npng)
                jobs.append((npng, 'BC5_UNORM', False))
                if args.preview:
                    nimg.convert('RGB').save(os.path.join(args.preview, f'{nh}_normal_after.png'))
                line += f' + normal {nh} ({tx:+.0f},{ty:+.0f})'
            print(line)

        if args.no_install:
            return 0
        print('  compressing')
        up.encode_all(args.tools, jobs, encoded)
        os.makedirs(backup, exist_ok=True)
        for name in os.listdir(encoded):
            hh = os.path.splitext(name)[0].upper()
            dst = os.path.join(out, hh + '.dds')
            keep = os.path.join(backup, hh + '.dds')
            if os.path.exists(dst) and not os.path.exists(keep) and \
                    not os.path.exists(os.path.join(out, hh + '.material')):
                shutil.copy2(dst, keep)
            shutil.move(os.path.join(encoded, name), dst)
            src_h = next((h for h, v in spec.items() if hh in (h, v.get('normal'))), '')
            with open(os.path.join(out, hh + '.material'), 'w') as f:
                f.write(f"ambientCG {spec[src_h]['material']} (CC0 1.0)\n")
        print(f'installed {len(jobs)} textures -> {out}')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
