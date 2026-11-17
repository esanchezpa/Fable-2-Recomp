"""Pick an ambientCG material for each tiling game texture (input for
tools/material_swap.py).

For every hash in the hand-picked lists (category -> hashes; the same lists the
bold redraws used, so atlases and painted props are already left out):

  1. Skip textures that do not tile (the wrap seam differs from the interior)
     or that have cut-out alpha.
  2. Compare structure, not colour (material_swap moves the colour onto the
     original's anyway): CLIP image embeddings of grey-scale versions, the
     original tiled 2x2 so it is judged as a surface, restricted to the
     material families that fit its category.
  3. Repeat: how many times the material must tile across the texture so its
     detail is the same size as the original's (ratio of the centroids of the
     two power spectra).
  4. Normal map: the DXN texture the same draws bind, from a log_texture_sets
     session log, when that normal map is bound with no other colour texture
     (a shared map would mismatch the others).

Writes a spec JSON for material_swap.py. Entries already in --keep (the
hand-tuned trial spec) are kept as they are.
"""

import argparse
import glob
import json
import os
import re
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_textures as up  # noqa: E402

CLIP = 'openai/clip-vit-base-patch32'
# Category (reimagine lists) -> ambientCG families allowed.
FAMILIES = {
    'stone': ['Rock', 'Rocks', 'Bricks', 'PavingStones', 'Plaster'],
    'brick': ['Bricks', 'PavingStones', 'Plaster'],
    'wood': ['Planks', 'Wood', 'WoodSiding', 'WoodFloor', 'Logs'],
    'roof': ['RoofingTiles', 'ThatchedRoof'],
    'bark': ['Bark'],
    'ground': ['Ground', 'Gravel', 'Rocks', 'Pathway', 'Moss'],
    'grass': ['Grass', 'Ground', 'Moss'],
}
STRUCTURED = {'Bricks', 'PavingStones', 'Planks', 'Wood', 'WoodSiding', 'WoodFloor', 'Logs',
              'RoofingTiles', 'ThatchedRoof'}


def family(asset):
    return re.sub(r'\d.*', '', asset)


def seam_ratio(g):
    """Mean step across the wrap seams over the mean step inside (1 = tiles)."""
    inner = (np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean()) / 2 + 1e-4
    seam = (np.abs(g[0] - g[-1]).mean() + np.abs(g[:, 0] - g[:, -1]).mean()) / 2
    return float(seam / inner)


def detail_freq(g):
    """Power-spectrum centroid in cycles per image (detail size), large-scale
    shading removed."""
    g = g - g.mean()
    p = np.abs(np.fft.rfft2(g)) ** 2
    h, w = g.shape
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.rfftfreq(w)[None, :] * w
    r = np.sqrt(fx * fx + fy * fy)
    m = (r >= 2) & (r <= min(h, w) / 4)
    return float((p[m] * r[m]).sum() / (p[m].sum() + 1e-9))


def anisotropy(g):
    """log(vertical / horizontal gradient energy): > 0 for horizontal lines
    (planks, brick courses, roof rows), < 0 for vertical ones."""
    gx = np.diff(g, axis=1)
    gy = np.diff(g, axis=0)
    return float(np.log((gy * gy).mean() + 1e-6) - np.log((gx * gx).mean() + 1e-6))


def grey(img, size=256):
    return np.asarray(img.convert('L').resize((size, size), Image.LANCZOS), np.float32) / 255.0


def parse_sets(logs):
    """[texture-set] lines -> list of {fetch: hash}."""
    sets = []
    rx = re.compile(r'\[texture-set\] ps (\w+)((?: \d+=\w+)*)')
    for path in logs:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = rx.search(line)
            if m:
                sets.append({int(k): v for k, v in (t.split('=') for t in m[2].split())})
    return sets


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pack_root')
    ap.add_argument('--lists', required=True, help='JSON {category: [hashes]}')
    ap.add_argument('--pool', required=True, help='folder of <asset>.jpg ambientCG colour previews')
    ap.add_argument('--logs', nargs='*', default=[], help='game logs from a log_texture_sets session')
    ap.add_argument('--keep', default=os.path.join(here, 'material_swap.json'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--tools', default=os.path.join(repo, 'out', 'tooling', 'upscale'))
    ap.add_argument('--models', default=os.path.join(repo, 'out', 'tooling', 'reimagine', 'models'))
    ap.add_argument('--max-seam', type=float, default=1.8)
    args = ap.parse_args()

    import torch
    from transformers import CLIPModel, CLIPProcessor

    lists = json.load(open(args.lists, encoding='utf-8'))
    keep = {h: v for h, v in json.load(open(args.keep, encoding='utf-8')).items() if not h.startswith('_')}
    dumps = {}
    for p in glob.glob(os.path.join(args.pack_root, 'dump', '*.dds')):
        r = up.parse_dump_name(os.path.basename(p))
        if r:
            dumps[r[0]] = (p, r[3])

    model = CLIPModel.from_pretrained(CLIP, cache_dir=args.models).to('cuda').eval()
    proc = CLIPProcessor.from_pretrained(CLIP, cache_dir=args.models)

    def embed(imgs):
        out = []
        with torch.no_grad():
            for i in range(0, len(imgs), 64):
                x = proc(images=imgs[i:i + 64], return_tensors='pt').to('cuda')
                f = model.get_image_features(**x)
                if not torch.is_tensor(f):  # newer transformers return a model output
                    f = f.pooler_output
                    if f.shape[-1] != model.config.projection_dim:
                        f = model.visual_projection(f)
                out.append(torch.nn.functional.normalize(f, dim=-1).cpu().numpy())
        return np.concatenate(out)

    # Candidate pool.
    pool = sorted(glob.glob(os.path.join(args.pool, '*.jpg')))
    pool = [p for p in pool if os.path.getsize(p) > 4096]
    names = [os.path.splitext(os.path.basename(p))[0] for p in pool]
    print(f'{len(names)} candidate materials')
    pimgs, pfreq, paniso = [], [], []
    for p in pool:
        g = grey(Image.open(p))
        pfreq.append(detail_freq(g))
        paniso.append(anisotropy(g))
        pimgs.append(Image.fromarray((g * 255).astype(np.uint8)).convert('RGB'))
    pemb = embed(pimgs)

    sets = parse_sets(args.logs)
    print(f'{len(sets)} texture sets from {len(args.logs)} logs')

    work = tempfile.mkdtemp(prefix='matmatch_')
    spec, skipped = {}, {}
    todo = [(c, h.upper()) for c, hs in lists.items() for h in hs]
    for cat, h in todo:
        if h in keep:
            spec[h] = keep[h]
            continue
        if h not in dumps or cat not in FAMILIES:
            skipped[h] = 'no dump' if h not in dumps else f'category {cat}'
            continue
        up.texconv(args.tools, ['-ft', 'png', '-f', 'R8G8B8A8_UNORM', '-o', work, dumps[h][0]])
        img = Image.open(os.path.join(work, os.path.splitext(os.path.basename(dumps[h][0]))[0] + '.png'))
        if img.mode == 'RGBA' and np.asarray(img.getchannel('A')).min() < 128:
            skipped[h] = 'cut-out alpha'
            continue
        g = grey(img)
        sr = seam_ratio(np.asarray(img.convert('L'), np.float32) / 255.0)
        if sr > args.max_seam:
            skipped[h] = f'does not tile (seam {sr:.1f})'
            continue
        tiled = np.tile(g, (2, 2))
        e = embed([Image.fromarray((tiled * 255).astype(np.uint8)).convert('RGB')])[0]
        allowed = [i for i, n in enumerate(names) if family(n) in FAMILIES[cat]]
        sims = pemb[allowed] @ e
        fo, ao = detail_freq(g), anisotropy(g)
        ranked = []
        for i, sim in zip(allowed, sims):
            # Lines running the other way: turn the material a quarter.
            rot = 90 if (ao * paniso[i] < 0 and abs(ao) > 0.25 and abs(paniso[i]) > 0.25) else 0
            ratio = fo / max(pfreq[i], 1e-3)
            rep_i = int(np.clip(round(ratio), 1, 4))
            # Detail of the wrong size after the best whole repeat costs score;
            # a material finer than the original (ratio < 1) costs more.
            off = abs(np.log2(max(ratio, 1e-3) / rep_i))
            score = float(sim) - 0.04 * off - (0.04 * off if ratio < 1 else 0.0)
            ranked.append((score, names[i], rep_i, rot))
        ranked.sort(reverse=True)
        _, mat, repeat, rot = ranked[0]
        normal = None
        if sets:
            slots = {k for st in sets for k, t in st.items() if t == h}
            cands = {t for st in sets if h in st.values() for t in st.values()
                     if t in dumps and dumps[t][1] == 'DXN'}
            if len(cands) == 1:
                n = next(iter(cands))
                # Other colour textures drawn with the same normal map, in the
                # slot this texture uses: if any, the map is shared.
                partners = {st[k] for st in sets if n in st.values() for k in slots if k in st} - {h}
                normal = n if not partners else None
        spec[h] = {'material': mat, 'repeat': repeat, 'rotate': rot,
                   'mode': 'global' if family(mat) in STRUCTURED else 'organic',
                   'normal': normal, 'category': cat,
                   'candidates': [[n, r, o, round(sc, 3)] for sc, n, r, o in ranked[:6]],
                   'note': f'auto {cat}: score {ranked[0][0]:.2f}, seam {sr:.2f}'}
        print(f'  {h} {cat:6s} -> {mat:16s} x{repeat} r{rot} {spec[h]["mode"]:7s} normal {normal or "-"}')
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=1)
    print(f'{len(spec)} entries -> {args.out}; skipped {len(skipped)}')
    for h, why in skipped.items():
        print(f'  skip {h}: {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
