#!/usr/bin/env python3
"""Sparrow Edition model pack: ship only our remade models, keyed to the player's game.

The remade models keep the original models' texture coordinates and their
lighting is remapped from the game's baked lighting, so the rebuilt banks are
game content and cannot be published. The pack instead holds, per model, the
new mesh, the header change and a lighting remap (no lighting colours), each
encrypted with a key derived from the ORIGINAL model in the player's own
game files. The launcher (launcher/Fable2.Launcher/SparrowModels.cs) opens
every file with the player's game and rebuilds three banks on their PC:
data/streaming.bnk (the level model banks inside it),
data/Globals/globals_model_headers.bnk and data/levels.bnk (lighting).

Payload ("F2MDPL01", little-endian; written by the model pipeline's
export_pack_src.py):
    0   magic "F2MDPL01"
    8   i32 header delta (mesh part 1 size change; header u32 at +60)
    12  f32[6] bounds lo.xyz, hi.xyz of the new mesh
    36  u32 vertex count of the original model (lighting records must match)
    40  u32 vertex count of the new model
    44  u32 length of the new .mdl
    48  the new .mdl
    ..  u32[new*3] original vertex indices, u16[new*3] weights (sum 65535)

Encrypted model file (.emdl, big-endian lengths):
    0   magic "F2MDPK01"
    8   u16 length of the bank path, the path (lowercase, latin-1)
    ..  nonce (12), GCM tag (16), AES-256-GCM ciphertext of the payload
key = SHA-256("F2MDPK01" || the original .mdl entry, uncompressed); the bank
path is the associated data.

Usage:
  python tools/model_pack.py encrypt <pack_src> --game <game root> --out <folder>
  python tools/model_pack.py apply <folder> --game <game root> --out <root>
      Reference rebuild (the launcher does the same): writes the three banks
      under <root>/data/ from the player's game and the .emdl files.
  python tools/model_pack.py split <folder> --out <dist> --version N
      Stored zips + manifest.json (same format as the texture pack); sign
      with `dotnet run --project tools/sparrow-sign -- sign manifest.json`.

Needs `cryptography` and `numpy`.
"""
import argparse
import collections
import datetime
import glob
import gzip
import hashlib
import io
import json
import os
import struct
import sys
import time
import zipfile

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sparrow_bnk as bnk  # noqa: E402

MAGIC = b'F2MDPK01'
PAYLOAD_MAGIC = b'F2MDPL01'
PACK_NAME = 'sparrow-models'
PART_COUNT = 4
RELEASE_URL = 'https://github.com/gitgudscrub/Fable-2-Recomp/releases/download/{tag}/{name}'
STREAMING = 'data/streaming.bnk'
HEADERS = 'data/Globals/globals_model_headers.bnk'
LEVELS = 'data/levels.bnk'


def derive_key(original_mdl):
    return hashlib.sha256(MAGIC + original_mdl).digest()


def model_id(path):
    """Lighting-record model id: FNV-1 32 of the lowercase bank path, big-endian."""
    h = 0x811c9dc5
    for c in path.lower().encode('latin1'):
        h = ((h * 0x01000193) & 0xffffffff) ^ c
    return h.to_bytes(4, 'big')


def level_banks(game):
    """Yields (streaming entry name, Bank) for every level model bank."""
    outer = bnk.Bank(os.path.join(game, STREAMING))
    for name in outer.order:
        if name.lower().endswith('_models.bnk'):
            yield outer, name, bnk.Bank(data=outer.get(name))


def original_models(game, wanted):
    """{bank path: original .mdl bytes} for the wanted paths (first level bank that has it)."""
    found = {}
    for _, _, lvl in level_banks(game):
        for n in lvl.order:
            if n.lower() in wanted and n.lower() not in found:
                found[n.lower()] = lvl.get(n)
    return found


def read_emdl(path):
    b = open(path, 'rb').read()
    assert b[:8] == MAGIC, path
    ln = struct.unpack('>H', b[8:10])[0]
    name = b[10:10 + ln].decode('latin1')
    p = 10 + ln
    return name, b[p:p + 12], b[p + 12:p + 28], b[p + 28:]


def open_emdl(path, original):
    name, nonce, tag, ct = read_emdl(path)
    return name, AESGCM(derive_key(original)).decrypt(nonce, ct + tag, name.encode('latin1'))


def parse_payload(pl):
    assert pl[:8] == PAYLOAD_MAGIC
    delta, lx, ly, lz, hx, hy, hz, nv_orig, nv_new, mlen = struct.unpack_from('<i6fIII', pl, 8)
    mdl = pl[48:48 + mlen]
    p = 48 + mlen
    tri = np.frombuffer(pl, '<u4', nv_new * 3, p).reshape(nv_new, 3)
    w = np.frombuffer(pl, '<u2', nv_new * 3, p + 12 * nv_new).reshape(nv_new, 3)
    return dict(delta=delta, lo=(lx, ly, lz), hi=(hx, hy, hz), nv_orig=nv_orig, mdl=mdl, tri=tri, w=w)


def cmd_encrypt(args):
    index = json.load(open(os.path.join(args.src, 'index.json')))
    originals = original_models(args.game, set(index.values()))
    os.makedirs(os.path.join(args.out, 'models'), exist_ok=True)
    done = 0
    for key, name in sorted(index.items()):
        if name not in originals:
            print(f'  {name}: not in this game, skipped')
            continue
        pl = open(os.path.join(args.src, key + '.bin'), 'rb').read()
        nonce = os.urandom(12)
        sealed = AESGCM(derive_key(originals[name])).encrypt(nonce, pl, name.encode('latin1'))
        nb = name.encode('latin1')
        with open(os.path.join(args.out, 'models', key + '.emdl'), 'wb') as f:
            f.write(MAGIC + struct.pack('>H', len(nb)) + nb + nonce + sealed[-16:] + sealed[:-16])
        done += 1
    print(f'{done} models encrypted into {args.out}/models')


def patch_header(h, m):
    h = bytearray(h)
    lo, hi = np.array(m['lo'], np.float64), np.array(m['hi'], np.float64)
    c = (lo + hi) / 2
    p1 = struct.unpack_from('>I', h, 60)[0]
    struct.pack_into('>I', h, 60, p1 + m['delta'])
    r = float(np.linalg.norm(hi - lo) / 2)
    struct.pack_into('>4f', h, 16, *c, r)
    struct.pack_into('>6f', h, 32, *lo, *hi)
    struct.pack_into('>f', h, 72, 2 * r)
    return bytes(h)


def _u32(d, p):
    return struct.unpack_from('>I', d, p)[0]


def patch_lmp(lmp_gz, maps):
    """Remap the vertex-colour records of replaced models in one level's LightmapFile.
    Layout: "LightmapFile", u32 version, [u32 if >= 12]; static lightmaps u32 N
    {u64 key, u32 w, u32 h, u32 size, data}; variant u32 N {u8 kind, u64 key, u32 n,
    kind 0: n u32 colours, else n bytes}; words u32 N {u64 key, u32 n, n u32};
    [v >= 11: u32 N, N * 56 bytes]. Key = model id (4 bytes) + instance id."""
    raw = gzip.decompress(lmp_gz)
    fname = lmp_gz[10:lmp_gz.index(b'\0', 10)] if lmp_gz[3] & 8 else b''
    assert raw[:12] == b'LightmapFile'
    v = _u32(raw, 12)
    p = 16 + (4 if v >= 12 else 0)
    n = _u32(raw, p); p += 4
    for _ in range(n):
        p += 20 + _u32(raw, p + 16)
    out = bytearray(); last = 0; stats = collections.Counter()

    def remap(start, body, count):
        nonlocal last
        m = maps.get(raw[start:start + 4])
        if m is None:
            return
        if count != m['nv_orig']:
            stats['left as is'] += 1
            return
        col = np.frombuffer(raw, np.uint8, 4 * count, body).reshape(count, 4).astype(np.uint32)
        acc = (col[m['tri'].astype(np.int64)] * m['w'][:, :, None].astype(np.uint32)).sum(1)
        new = ((acc + 32767) // 65535).clip(0, 255).astype(np.uint8)
        out.extend(raw[last:body - 4]); out.extend(struct.pack('>I', len(new))); out.extend(new.tobytes())
        last = body + 4 * count
        stats['replaced'] += 1

    n = _u32(raw, p); p += 4
    for _ in range(n):
        kind = raw[p]; c = _u32(raw, p + 9); body = p + 13
        if kind == 0:
            remap(p + 1, body, c)
        elif maps.get(raw[p + 1:p + 5]) is not None:
            stats['left as is'] += 1
        p = body + (4 * c if kind == 0 else c)
    n = _u32(raw, p); p += 4
    for _ in range(n):
        c = _u32(raw, p + 8); body = p + 12
        remap(p, body, c)
        p = body + 4 * c
    if not stats['replaced']:
        return None, stats
    out.extend(raw[last:])
    bio = io.BytesIO()
    with gzip.GzipFile(filename=fname.decode('latin1'), mode='wb', fileobj=bio, mtime=0) as g:
        g.write(bytes(out))
    return bio.getvalue(), stats


def cmd_apply(args):
    files = sorted(glob.glob(os.path.join(args.pack, 'models', '*.emdl')))
    wanted = {read_emdl(f)[0]: f for f in files}
    t0 = time.time()
    models = {}
    outer = bnk.Bank(os.path.join(args.game, STREAMING))
    rebuilt = {}
    for lname in outer.order:
        if not lname.lower().endswith('_models.bnk'):
            continue
        lvl = bnk.Bank(data=outer.get(lname))
        hit = [n for n in lvl.order if n.lower() in wanted]
        if not hit:
            continue
        for n in hit:
            if n.lower() not in models:
                try:
                    models[n.lower()] = parse_payload(open_emdl(wanted[n.lower()], lvl.get(n))[1])
                except Exception as e:  # cryptography.exceptions.InvalidTag
                    print(f'  {n}: does not open with this game ({type(e).__name__})')
                    models[n.lower()] = None
        if not any(models.get(n.lower()) for n in hit):
            continue
        tmp = os.path.join(args.out, '_level.bnk')
        os.makedirs(args.out, exist_ok=True)
        bnk.write_bank(tmp, lvl.order, lambda n: models[n.lower()]['mdl'] if models.get(n.lower()) else lvl.get(n), 1)
        rebuilt[lname.lower()] = open(tmp, 'rb').read()
        os.remove(tmp)
    ok = {k: v for k, v in models.items() if v}
    print(f'{len(ok)} models opened, {len(rebuilt)} level banks rebuilt ({time.time() - t0:.0f} s)')

    def out(rel):
        path = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    bnk.write_bank(out(STREAMING), outer.order,
                   lambda n: rebuilt.get(n.lower()) or outer.get(n), 0, entry_align=0x8000)
    h = bnk.Bank(os.path.join(args.game, HEADERS))
    bnk.write_bank(out(HEADERS), h.order, lambda n: patch_header(h.get(n), ok[n.lower()]) if n.lower() in ok else h.get(n),
                   0, entry_align=1)
    maps = {model_id(k): v for k, v in ok.items()}
    lv = bnk.Bank(os.path.join(args.game, LEVELS))
    newl = {}; tot = collections.Counter()
    for n in lv.order:
        if n.lower().endswith('.lmp'):
            b, s = patch_lmp(lv.get(n), maps)
            tot.update(s)
            if b:
                newl[n.lower()] = b
    bnk.write_bank(out(LEVELS), lv.order, lambda n: newl.get(n.lower()) or lv.get(n), 0, entry_align=lv.alignment())
    print(f'lighting {dict(tot)}; wrote {args.out}/data ({time.time() - t0:.0f} s)')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def cmd_split(args):
    files = sorted(glob.glob(os.path.join(args.folder, 'models', '*.emdl')))
    if not files:
        raise SystemExit(f'no .emdl files under {args.folder}/models')
    os.makedirs(args.out, exist_ok=True)
    tag = f'models-v{args.version}'
    groups = [[] for _ in range(PART_COUNT)]
    for path in files:
        groups[hashlib.sha1(os.path.basename(path).encode()).digest()[0] % PART_COUNT].append(path)
    parts = []; total = 0
    for index, group in enumerate(groups):
        name = f'{PACK_NAME}-v{args.version}-part{index:02d}.zip'
        dst = os.path.join(args.out, name)
        with zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED) as zf:
            for path in group:
                info = zipfile.ZipInfo(os.path.basename(path), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                zf.writestr(info, open(path, 'rb').read())
        size = os.path.getsize(dst); total += size
        parts.append({'name': name, 'size': size, 'sha256': sha256_file(dst), 'files': len(group),
                      'url': RELEASE_URL.format(tag=tag, name=name)})
        print(f'  {name}: {len(group)} files, {size / 2**20:.1f} MB')
    manifest = {'pack': PACK_NAME, 'version': args.version, 'game_profile': args.profile,
                'created': datetime.date.today().isoformat(), 'file_format': 'F2MDPK01',
                'install_dir': 'sparrow-pack/models', 'total_bytes': total, 'file_count': len(files), 'parts': parts}
    with open(os.path.join(args.out, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(manifest, fh, indent=2); fh.write('\n')
    print(f'{len(files)} models in {PART_COUNT} parts, {total / 2**20:.1f} MB; release tag {tag}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('encrypt'); p.add_argument('src'); p.add_argument('--game', required=True); p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_encrypt)
    p = sub.add_parser('apply'); p.add_argument('pack'); p.add_argument('--game', required=True); p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_apply)
    p = sub.add_parser('split'); p.add_argument('folder'); p.add_argument('--out', required=True)
    p.add_argument('--version', type=int, required=True); p.add_argument('--profile', default='goty-us-eu')
    p.set_defaults(fn=cmd_split)
    args = ap.parse_args()
    return args.fn(args) or 0


if __name__ == '__main__':
    sys.exit(main())
