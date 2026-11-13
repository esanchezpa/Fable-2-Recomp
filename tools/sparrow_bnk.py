"""Read and write Fable II .bnk archives (used by tools/model_pack.py).

Layout (big-endian):
    0   u32 data base (aligned, 0x8000 for the shipped banks)
    4   u32 3
    8   u8  compressed flag
    9   table of contents: one zlib stream cut into 64 KB pieces, each
        "u32 compressed size, u32 uncompressed size" + data; the last piece
        has an uncompressed size below 0x10000
    base  entry data
TOC: u32 count, then per entry u32 name length (with the NUL), name, and
    uncompressed banks: u32 offset, u32 size
    compressed banks:   u32 offset, u32 size, u32 stored size, u32 chunk count,
                        u32 uncompressed size of each chunk
Offsets are relative to the data base. A compressed entry is one zlib stream
per 32 KB of stored data (chunk i starts at i * 0x8000), sync-flushed and never
finished: the game hangs on finished streams padded with zeros, so every chunk
but the last is padded to 32 KB with empty deflate blocks instead.
"""
import struct
import zlib


def _inflate_toc(b, p):
    d = zlib.decompressobj()
    out = []
    while p + 8 <= len(b):
        cs, us = struct.unpack('>II', b[p:p + 8])
        out.append(d.decompress(b[p + 8:p + 8 + cs]))
        p += 8 + cs
        if us < 0x10000:
            break
    return b''.join(out), p


class Bank:
    def __init__(self, path=None, data=None):
        self.b = b = data if data is not None else open(path, 'rb').read()
        self.comp = b[8]
        toc, tocend = _inflate_toc(b, 9)
        self.base = struct.unpack('>I', b[:4])[0]
        n = struct.unpack('>I', toc[:4])[0]
        q = 4
        self.ents = {}
        self.order = []
        for _ in range(n):
            ln = struct.unpack('>I', toc[q:q + 4])[0]
            name = toc[q + 4:q + 4 + ln].rstrip(b'\0').decode('latin1')
            q += 4 + ln
            if self.comp:
                off, us, cs, nc = struct.unpack('>IIII', toc[q:q + 16])
                q += 16
                chunks = struct.unpack('>%dI' % nc, toc[q:q + 4 * nc])
                q += 4 * nc
            else:
                off, us = struct.unpack('>II', toc[q:q + 8])
                q += 8
                cs, chunks = us, ()
            self.ents[name.lower()] = (off, us, cs, chunks)
            self.order.append(name)

    def get(self, name):
        off, us, cs, chunks = self.ents[name.lower()]
        raw = self.b[self.base + off:self.base + off + cs]
        if not self.comp:
            return raw
        out = [zlib.decompressobj().decompress(raw[i * 0x8000:(i + 1) * 0x8000], c) for i, c in enumerate(chunks)]
        r = b''.join(out)
        assert len(r) == us, (name, len(r), us)
        return r

    def alignment(self):
        """Largest power of two (<= 0x8000) that divides every entry offset."""
        a = 0x8000
        for off, *_ in self.ents.values():
            while off % a:
                a //= 2
        return a


def _toc_stream(t):
    c = zlib.compressobj(9)
    out = []
    for i in range(0, len(t), 0x10000):
        piece = t[i:i + 0x10000]
        z = c.compress(piece) + c.flush(zlib.Z_SYNC_FLUSH)
        out.append(struct.pack('>II', len(z), len(piece)) + z)
    if len(t) % 0x10000 == 0:      # the reader stops at a piece below 64 KB
        z = c.flush(zlib.Z_SYNC_FLUSH)
        out.append(struct.pack('>II', len(z), 0) + z)
    return b''.join(out)


def _empty_blocks(k):
    """k empty fixed-Huffman blocks, then an empty stored block (byte aligned)."""
    bits = []
    for _ in range(k):
        bits += [0, 1, 0] + [0] * 7
    bits += [0, 0, 0]
    while len(bits) % 8:
        bits.append(0)
    by = bytes(sum(bit << i for i, bit in enumerate(bits[j:j + 8])) for j in range(0, len(bits), 8))
    return by + bytes([0, 0, 0xff, 0xff])


PAD_UNITS = {len(_empty_blocks(k)): _empty_blocks(k) for k in range(3)}  # 5, 6 and 7 bytes


def _pad_ok(n):
    return n == 0 or n in (5, 6, 7) or n >= 10


def pad(n):
    assert _pad_ok(n), n
    out = b''
    while n:
        u = next(u for u in (7, 6, 5) if n >= u and _pad_ok(n - u))
        out += PAD_UNITS[u]
        n -= u
    return out


def pack_entry(data):
    """(stored blob, size, stored size, chunk sizes) for a compressed bank."""
    pieces, sizes, p = [], [], 0
    while p < len(data) or not pieces:
        n = min(len(data) - p, 0x10000)
        while True:
            c = zlib.compressobj(9)
            z = c.compress(data[p:p + n]) + c.flush(zlib.Z_SYNC_FLUSH)
            last = p + n >= len(data)
            if len(z) <= 0x8000 and (last or _pad_ok(0x8000 - len(z))):
                break
            n = int(n * 0x7c00 / len(z)) if len(z) > 0x8000 else n - 64
        pieces.append(z)
        sizes.append(n)
        p += n
    blob = b''.join(z + pad(0x8000 - len(z)) for z in pieces[:-1]) + pieces[-1]
    return blob, len(data), len(blob), sizes


def write_bank(path, names, getdata, comp, entry_align=None, base_align=0x8000):
    """names: entry order; getdata(name) -> the entry's uncompressed bytes."""
    align = entry_align or (16 if comp else 0x8000)
    toc = [struct.pack('>I', len(names))]
    with open(path + '.tmp', 'wb') as f:
        # Entry data first into a temp list of (meta, blob) to learn the TOC size.
        metas = []
        blobs = []
        off = 0
        for nm in names:
            d = getdata(nm)
            if comp:
                blob, us, cs, ch = pack_entry(d)
                meta = struct.pack('>IIII', off, us, cs, len(ch)) + struct.pack('>%dI' % len(ch), *ch)
            else:
                blob, meta = d, struct.pack('>II', off, len(d))
            nb = nm.encode('latin1') + b'\0'
            toc.append(struct.pack('>I', len(nb)) + nb + meta)
            padn = (-len(blob)) % align
            blobs.append((blob, padn))
            off += len(blob) + padn
        ts = _toc_stream(b''.join(toc))
        base = (9 + len(ts) + base_align - 1) // base_align * base_align
        f.write(struct.pack('>IIB', base, 3, 1 if comp else 0))
        f.write(ts)
        f.write(b'\0' * (base - 9 - len(ts)))
        for blob, padn in blobs:
            f.write(blob)
            f.write(b'\0' * padn)
    import os
    os.replace(path + '.tmp', path)
