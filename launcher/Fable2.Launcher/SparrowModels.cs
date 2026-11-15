using System.Buffers.Binary;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Fable2Launcher;

/// <summary>
/// Builds the Sparrow Edition game files on the player's PC from the downloaded
/// model pack (tools/model_pack.py has the format and the reference version of
/// this code). Every .emdl file holds one remade model, encrypted with a key
/// derived from the ORIGINAL model in the player's own game files; this class
/// opens each one with the player's game and rebuilds:
///   data\streaming.bnk                        the level model banks inside it
///   data\Globals\globals_model_headers.bnk    the remade models' headers
///   data\levels.bnk                           baked lighting remapped onto them
/// into ModelPack.PackFolder, which the Sparrow overlay plays from. The game
/// folder is only read.
/// </summary>
public static class SparrowModels
{
    private const string Streaming = @"data\streaming.bnk";
    private const string Headers = @"data\Globals\globals_model_headers.bnk";
    private const string Levels = @"data\levels.bnk";
    private const string StampName = "build-stamp.json";
    private static readonly byte[] FileMagic = "F2MDPK01"u8.ToArray();
    private static readonly byte[] PayloadMagic = "F2MDPL01"u8.ToArray();

    public sealed record Result(int Models, int Failed, int LevelBanks, int LightingRecords);

    /// <summary>
    /// A text that changes whenever the pack files or the game files the build
    /// reads change; the build is current while the stamp it wrote matches.
    /// </summary>
    public static string Stamp(string gameFolder, string modelsFolder)
    {
        var parts = new List<string>();
        foreach (string relative in new[] { Streaming, Headers, Levels })
        {
            var info = new FileInfo(Path.Combine(gameFolder, relative));
            parts.Add(info.Exists ? $"{relative}:{info.Length}:{info.LastWriteTimeUtc.Ticks}" : $"{relative}:missing");
        }
        if (Directory.Exists(modelsFolder))
            foreach (FileInfo file in new DirectoryInfo(modelsFolder).EnumerateFiles("*.emdl").OrderBy(f => f.Name, StringComparer.Ordinal))
                parts.Add($"{file.Name}:{file.Length}:{file.LastWriteTimeUtc.Ticks}");
        return JsonSerializer.Serialize(parts);
    }

    public static bool IsCurrent(string gameFolder, string modelsFolder, string outFolder)
    {
        string path = Path.Combine(outFolder, StampName);
        return File.Exists(path) && File.ReadAllText(path) == Stamp(gameFolder, modelsFolder)
               && new[] { Streaming, Headers, Levels }.All(relative => File.Exists(Path.Combine(outFolder, relative)));
    }

    /// <summary>Rebuilds the three banks. progress gets (what, fraction 0..1).</summary>
    public static Result Build(string gameFolder, string modelsFolder, string outFolder,
                               IProgress<(string Step, double Fraction)>? progress, CancellationToken cancel)
    {
        string stamp = Stamp(gameFolder, modelsFolder);
        Directory.CreateDirectory(outFolder);
        File.Delete(Path.Combine(outFolder, StampName));

        Dictionary<string, string> wanted = new(StringComparer.OrdinalIgnoreCase);
        foreach (string file in Directory.EnumerateFiles(modelsFolder, "*.emdl"))
            wanted[ReadName(file)] = file;
        if (wanted.Count == 0) throw new InvalidOperationException("The Sparrow model pack has no models.");

        // 1. Level model banks inside streaming.bnk.
        Dictionary<string, Payload?> models = new(StringComparer.OrdinalIgnoreCase);
        Dictionary<string, byte[]> rebuilt = new(StringComparer.OrdinalIgnoreCase);
        using (Bank outer = Bank.Open(Path.Combine(gameFolder, Streaming)))
        {
            List<string> levelBanks = outer.Order.Where(n => n.EndsWith("_models.bnk", StringComparison.OrdinalIgnoreCase)).ToList();
            for (int i = 0; i < levelBanks.Count; i++)
            {
                cancel.ThrowIfCancellationRequested();
                progress?.Report(("Remaking level models", 0.45 * i / levelBanks.Count));
                using Bank level = Bank.FromBytes(outer.Get(levelBanks[i]));
                List<string> hits = level.Order.Where(wanted.ContainsKey).ToList();
                if (hits.Count == 0) continue;
                foreach (string name in hits)
                    if (!models.ContainsKey(name))
                        models[name] = Open(wanted[name], name, level.Get(name));
                if (!hits.Any(name => models[name] is not null)) continue;
                rebuilt[levelBanks[i]] = BankWriter.BuildCompressed(level.Order,
                    name => models.TryGetValue(name, out Payload? m) && m is not null ? m.Mdl : level.Get(name));
            }
            progress?.Report(("Writing streaming.bnk", 0.45));
            BankWriter.WriteUncompressed(Path.Combine(outFolder, Streaming), outer.Order,
                name => rebuilt.TryGetValue(name, out byte[]? data) ? data.Length : outer.Entries[name].Size,
                name => rebuilt.TryGetValue(name, out byte[]? data) ? data : outer.Get(name), 0x8000, cancel);
        }
        Dictionary<string, Payload> opened = models.Where(pair => pair.Value is not null)
            .ToDictionary(pair => pair.Key, pair => pair.Value!, StringComparer.OrdinalIgnoreCase);
        if (opened.Count == 0)
            throw new InvalidOperationException("None of the remade models open with your game files. The pack may be for a different version of Fable II.");

        // 2. Model headers.
        progress?.Report(("Updating model headers", 0.6));
        using (Bank headers = Bank.Open(Path.Combine(gameFolder, Headers)))
        {
            Dictionary<string, byte[]> patched = new(StringComparer.OrdinalIgnoreCase);
            foreach (string name in headers.Order)
                if (opened.TryGetValue(name, out Payload? m)) patched[name] = PatchHeader(headers.Get(name), m);
            BankWriter.WriteUncompressed(Path.Combine(outFolder, Headers), headers.Order,
                name => patched.TryGetValue(name, out byte[]? h) ? h.Length : headers.Entries[name].Size,
                name => patched.TryGetValue(name, out byte[]? h) ? h : headers.Get(name), 1, cancel);
        }

        // 3. Baked lighting.
        Dictionary<uint, Payload> byId = opened.ToDictionary(pair => ModelId(pair.Key), pair => pair.Value);
        int records = 0;
        using (Bank levels = Bank.Open(Path.Combine(gameFolder, Levels)))
        {
            Dictionary<string, byte[]> lighting = new(StringComparer.OrdinalIgnoreCase);
            List<string> lmps = levels.Order.Where(n => n.EndsWith(".lmp", StringComparison.OrdinalIgnoreCase)).ToList();
            for (int i = 0; i < lmps.Count; i++)
            {
                cancel.ThrowIfCancellationRequested();
                progress?.Report(("Relighting", 0.62 + 0.18 * i / lmps.Count));
                (byte[]? data, int count) = Lighting.Patch(levels.Get(lmps[i]), byId);
                if (data is not null) { lighting[lmps[i]] = data; records += count; }
            }
            progress?.Report(("Writing levels.bnk", 0.8));
            BankWriter.WriteUncompressed(Path.Combine(outFolder, Levels), levels.Order,
                name => lighting.TryGetValue(name, out byte[]? data) ? data.Length : levels.Entries[name].Size,
                name => lighting.TryGetValue(name, out byte[]? data) ? data : levels.Get(name), levels.Alignment(), cancel);
        }

        File.WriteAllText(Path.Combine(outFolder, StampName), stamp);
        progress?.Report(("Done", 1));
        return new Result(opened.Count, models.Count - opened.Count, rebuilt.Count, records);
    }

    // ------------------------------------------------------------ pack files

    private sealed record Payload(int Delta, float[] Lo, float[] Hi, int OriginalVertices, byte[] Mdl, uint[] Corners, ushort[] Weights);

    private static string ReadName(string path)
    {
        using FileStream stream = File.OpenRead(path);
        Span<byte> head = stackalloc byte[10];
        stream.ReadExactly(head);
        if (!head[..8].SequenceEqual(FileMagic)) throw new InvalidDataException($"{Path.GetFileName(path)} is not a Sparrow model file.");
        byte[] name = new byte[BinaryPrimitives.ReadUInt16BigEndian(head[8..])];
        stream.ReadExactly(name);
        return Encoding.Latin1.GetString(name);
    }

    /// <summary>Decrypts one model with the player's original; null when it doesn't open with this game.</summary>
    private static Payload? Open(string path, string name, byte[] original)
    {
        byte[] file = File.ReadAllBytes(path);
        int nameLength = BinaryPrimitives.ReadUInt16BigEndian(file.AsSpan(8));
        int p = 10 + nameLength;
        byte[] key = SHA256.HashData([.. FileMagic, .. original]);
        byte[] plain = new byte[file.Length - p - 28];
        try
        {
            using var aes = new AesGcm(key, 16);
            aes.Decrypt(file.AsSpan(p, 12), file.AsSpan(p + 28), file.AsSpan(p + 12, 16), plain,
                        Encoding.Latin1.GetBytes(name.ToLowerInvariant()));
        }
        catch (AuthenticationTagMismatchException) { return null; }
        if (!plain.AsSpan(0, 8).SequenceEqual(PayloadMagic)) return null;
        ReadOnlySpan<byte> s = plain;
        int delta = BinaryPrimitives.ReadInt32LittleEndian(s[8..]);
        float[] lo = new float[3], hi = new float[3];
        for (int i = 0; i < 3; i++)
        {
            lo[i] = BinaryPrimitives.ReadSingleLittleEndian(s[(12 + 4 * i)..]);
            hi[i] = BinaryPrimitives.ReadSingleLittleEndian(s[(24 + 4 * i)..]);
        }
        int originalVertices = BinaryPrimitives.ReadInt32LittleEndian(s[36..]);
        int newVertices = BinaryPrimitives.ReadInt32LittleEndian(s[40..]);
        int mdlLength = BinaryPrimitives.ReadInt32LittleEndian(s[44..]);
        byte[] mdl = s.Slice(48, mdlLength).ToArray();
        int q = 48 + mdlLength;
        uint[] corners = new uint[newVertices * 3];
        ushort[] weights = new ushort[newVertices * 3];
        for (int i = 0; i < corners.Length; i++) corners[i] = BinaryPrimitives.ReadUInt32LittleEndian(s[(q + 4 * i)..]);
        q += 4 * corners.Length;
        for (int i = 0; i < weights.Length; i++) weights[i] = BinaryPrimitives.ReadUInt16LittleEndian(s[(q + 2 * i)..]);
        return new Payload(delta, lo, hi, originalVertices, mdl, corners, weights);
    }

    /// <summary>104-byte MeshFile header: part 1 grows by delta, bounds become the new mesh's.</summary>
    private static byte[] PatchHeader(byte[] header, Payload m)
    {
        byte[] h = (byte[])header.Clone();
        uint part1 = BinaryPrimitives.ReadUInt32BigEndian(h.AsSpan(60));
        BinaryPrimitives.WriteUInt32BigEndian(h.AsSpan(60), (uint)(part1 + m.Delta));
        double sum = 0;
        for (int i = 0; i < 3; i++)
        {
            double c = ((double)m.Lo[i] + m.Hi[i]) / 2;
            BinaryPrimitives.WriteSingleBigEndian(h.AsSpan(16 + 4 * i), (float)c);
            double d = (double)m.Hi[i] - m.Lo[i];
            sum += d * d;
            BinaryPrimitives.WriteSingleBigEndian(h.AsSpan(32 + 4 * i), m.Lo[i]);
            BinaryPrimitives.WriteSingleBigEndian(h.AsSpan(44 + 4 * i), m.Hi[i]);
        }
        double r = Math.Sqrt(sum) / 2;
        BinaryPrimitives.WriteSingleBigEndian(h.AsSpan(28), (float)r);
        BinaryPrimitives.WriteSingleBigEndian(h.AsSpan(72), (float)(2 * r));
        return h;
    }

    /// <summary>Lighting-record model id: FNV-1 32 of the lowercase bank path.</summary>
    private static uint ModelId(string path)
    {
        uint h = 0x811c9dc5;
        foreach (byte c in Encoding.Latin1.GetBytes(path.ToLowerInvariant())) h = (h * 0x01000193) ^ c;
        return h;
    }

    // -------------------------------------------------------------- lighting

    private static class Lighting
    {
        /// <summary>
        /// Remaps the vertex-colour records of replaced models in one level's
        /// LightmapFile (gzip). Layout: "LightmapFile", u32 version, [u32 if >= 12];
        /// static lightmaps u32 N {u64 key, u32 w, u32 h, u32 size, data}; variant
        /// u32 N {u8 kind, u64 key, u32 n, kind 0: n colours, else n bytes}; words
        /// u32 N {u64 key, u32 n, n colours}; [v >= 11: u32 N, N * 56]. Key = model
        /// id + instance id. Returns null when nothing in it changed.
        /// </summary>
        public static (byte[]? Data, int Records) Patch(byte[] gz, Dictionary<uint, Payload> models)
        {
            byte[] raw;
            using (var input = new GZipStream(new MemoryStream(gz), CompressionMode.Decompress))
            using (var buffer = new MemoryStream())
            {
                input.CopyTo(buffer);
                raw = buffer.ToArray();
            }
            if (raw.Length < 16 || Encoding.ASCII.GetString(raw, 0, 12) != "LightmapFile") return (null, 0);
            uint version = U32(raw, 12);
            int p = 16 + (version >= 12 ? 4 : 0);
            uint n = U32(raw, p); p += 4;
            for (uint i = 0; i < n; i++) p += 20 + (int)U32(raw, p + 16);

            var output = new MemoryStream(raw.Length + 1024);
            int last = 0, replaced = 0;
            void Remap(int keyAt, int body, int count)
            {
                if (!models.TryGetValue(U32(raw, keyAt), out Payload? m) || count != m.OriginalVertices) return;
                int vertices = m.Weights.Length / 3;
                output.Write(raw, last, body - 4 - last);
                Span<byte> head = stackalloc byte[4];
                BinaryPrimitives.WriteUInt32BigEndian(head, (uint)vertices);
                output.Write(head);
                byte[] colours = new byte[vertices * 4];
                for (int v = 0; v < vertices; v++)
                    for (int ch = 0; ch < 4; ch++)
                    {
                        ulong acc = 0;
                        for (int k = 0; k < 3; k++)
                            acc += (ulong)raw[body + 4 * (int)m.Corners[3 * v + k] + ch] * m.Weights[3 * v + k];
                        colours[4 * v + ch] = (byte)Math.Min(255UL, (acc + 32767) / 65535);
                    }
                output.Write(colours);
                last = body + 4 * count;
                replaced++;
            }
            n = U32(raw, p); p += 4;
            for (uint i = 0; i < n; i++)
            {
                byte kind = raw[p];
                int count = (int)U32(raw, p + 9), body = p + 13;
                if (kind == 0) Remap(p + 1, body, count);
                p = body + (kind == 0 ? 4 * count : count);
            }
            n = U32(raw, p); p += 4;
            for (uint i = 0; i < n; i++)
            {
                int count = (int)U32(raw, p + 8), body = p + 12;
                Remap(p, body, count);
                p = body + 4 * count;
            }
            if (replaced == 0) return (null, 0);
            output.Write(raw, last, raw.Length - last);
            return (Gzip(output.ToArray(), GzipName(gz)), replaced);
        }

        private static uint U32(byte[] d, int p) => BinaryPrimitives.ReadUInt32BigEndian(d.AsSpan(p));

        private static byte[]? GzipName(byte[] gz)
        {
            if (gz.Length < 10 || (gz[3] & 8) == 0) return null;
            int end = Array.IndexOf(gz, (byte)0, 10);
            return end < 0 ? null : gz[10..end];
        }

        /// <summary>gzip with the original file name in the header, like the shipped files.</summary>
        private static byte[] Gzip(byte[] data, byte[]? name)
        {
            var output = new MemoryStream();
            output.Write([0x1f, 0x8b, 8, (byte)(name is null ? 0 : 8), 0, 0, 0, 0, 2, 0xff]);
            if (name is not null) { output.Write(name); output.WriteByte(0); }
            using (var deflate = new DeflateStream(output, CompressionLevel.SmallestSize, leaveOpen: true))
                deflate.Write(data);
            Span<byte> tail = stackalloc byte[8];
            BinaryPrimitives.WriteUInt32LittleEndian(tail, Crc32(data));
            BinaryPrimitives.WriteUInt32LittleEndian(tail[4..], (uint)data.Length);
            output.Write(tail);
            return output.ToArray();
        }

        private static readonly uint[] CrcTable = Enumerable.Range(0, 256).Select(i =>
        {
            uint c = (uint)i;
            for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320 ^ (c >> 1) : c >> 1;
            return c;
        }).ToArray();

        private static uint Crc32(byte[] data)
        {
            uint c = 0xffffffff;
            foreach (byte b in data) c = CrcTable[(c ^ b) & 0xff] ^ (c >> 8);
            return c ^ 0xffffffff;
        }
    }
}

/// <summary>
/// A Fable II .bnk archive (big-endian): u32 data base, u32 3, u8 compressed
/// flag, a table of contents as one zlib stream cut into 64 KB pieces, then the
/// entry data from the base. See tools/sparrow_bnk.py.
/// </summary>
internal sealed class Bank : IDisposable
{
    public sealed record Entry(long Offset, int Size, int Stored, int[] Chunks);

    private readonly Stream _stream;
    private readonly long _base;
    public bool Compressed { get; }
    public List<string> Order { get; } = new();
    public Dictionary<string, Entry> Entries { get; } = new(StringComparer.OrdinalIgnoreCase);

    private Bank(Stream stream)
    {
        _stream = stream;
        byte[] head = Read(0, 9);
        _base = BinaryPrimitives.ReadUInt32BigEndian(head);
        Compressed = head[8] != 0;
        byte[] toc = ReadToc();
        int q = 0;
        int count = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q)); q += 4;
        for (int i = 0; i < count; i++)
        {
            int length = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q));
            string name = Encoding.Latin1.GetString(toc, q + 4, length).TrimEnd('\0');
            q += 4 + length;
            Entry entry;
            if (Compressed)
            {
                uint offset = BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q));
                int size = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q + 4));
                int stored = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q + 8));
                int chunks = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q + 12));
                q += 16;
                int[] sizes = new int[chunks];
                for (int c = 0; c < chunks; c++) sizes[c] = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q + 4 * c));
                q += 4 * chunks;
                entry = new Entry(offset, size, stored, sizes);
            }
            else
            {
                uint offset = BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q));
                int size = (int)BinaryPrimitives.ReadUInt32BigEndian(toc.AsSpan(q + 4));
                q += 8;
                entry = new Entry(offset, size, size, []);
            }
            Entries[name] = entry;
            Order.Add(name);
        }
    }

    public static Bank Open(string path) =>
        new(new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20));

    public static Bank FromBytes(byte[] data) => new(new MemoryStream(data, writable: false));

    private byte[] Read(long offset, int count)
    {
        byte[] buffer = new byte[count];
        _stream.Position = offset;
        _stream.ReadExactly(buffer);
        return buffer;
    }

    private byte[] ReadToc()
    {
        // Gather the pieces' data into one zlib stream; the last piece is below 64 KB.
        var compressed = new MemoryStream();
        long p = 9, total = 0;
        while (true)
        {
            byte[] head = Read(p, 8);
            int stored = (int)BinaryPrimitives.ReadUInt32BigEndian(head);
            int size = (int)BinaryPrimitives.ReadUInt32BigEndian(head.AsSpan(4));
            compressed.Write(Read(p + 8, stored));
            total += size;
            p += 8 + stored;
            if (size < 0x10000) break;
        }
        compressed.Position = 0;
        return Inflate(compressed, (int)total);
    }

    private static byte[] Inflate(Stream compressed, int size)
    {
        byte[] output = new byte[size];
        using var zlib = new ZLibStream(compressed, CompressionMode.Decompress);
        int got = 0, read;
        while (got < size && (read = zlib.Read(output, got, size - got)) > 0) got += read;
        if (got != size) throw new InvalidDataException("A bank entry is shorter than its table of contents says.");
        return output;
    }

    public byte[] Get(string name)
    {
        Entry entry = Entries[name];
        byte[] raw = Read(_base + entry.Offset, entry.Stored);
        if (!Compressed) return raw;
        byte[] output = new byte[entry.Size];
        int at = 0;
        for (int i = 0; i < entry.Chunks.Length; i++)
        {
            int start = i * 0x8000;
            byte[] piece = Inflate(new MemoryStream(raw, start, Math.Min(0x8000, raw.Length - start)), entry.Chunks[i]);
            piece.CopyTo(output, at);
            at += piece.Length;
        }
        if (at != entry.Size) throw new InvalidDataException($"{name} unpacked to the wrong size.");
        return output;
    }

    /// <summary>Largest power of two (up to 0x8000) dividing every entry offset.</summary>
    public int Alignment()
    {
        int align = 0x8000;
        foreach (Entry entry in Entries.Values)
            while (entry.Offset % align != 0) align /= 2;
        return align;
    }

    public void Dispose() => _stream.Dispose();
}

internal static class BankWriter
{
    // Empty deflate blocks used to pad a compressed chunk to 32 KB: the game
    // hangs on zero padding after a finished stream.
    private static readonly byte[][] PadUnits =
    [
        [0x00, 0x00, 0x00, 0xFF, 0xFF],
        [0x02, 0x00, 0x00, 0x00, 0xFF, 0xFF],
        [0x02, 0x08, 0x00, 0x00, 0x00, 0xFF, 0xFF],
    ];

    private static bool PadOk(int n) => n == 0 || n is 5 or 6 or 7 || n >= 10;

    private static void Pad(Stream output, int n)
    {
        while (n > 0)
        {
            int unit = new[] { 7, 6, 5 }.First(u => n >= u && PadOk(n - u));
            output.Write(PadUnits[unit - 5]);
            n -= unit;
        }
    }

    /// <summary>zlib-compresses data with a sync flush and no end of stream.</summary>
    private static byte[] SyncFlushed(ReadOnlySpan<byte> data)
    {
        var buffer = new MemoryStream();
        var zlib = new ZLibStream(buffer, CompressionLevel.SmallestSize, leaveOpen: true);
        zlib.Write(data);
        zlib.Flush();
        byte[] result = buffer.ToArray();
        zlib.Dispose();   // writes the end of stream into the buffer, after it was copied
        return result;
    }

    private static byte[] TocStream(byte[] toc)
    {
        var output = new MemoryStream();
        var buffer = new MemoryStream();
        var zlib = new ZLibStream(buffer, CompressionLevel.SmallestSize, leaveOpen: true);
        byte[] head = new byte[8];
        void Piece(int start, int length)
        {
            long before = buffer.Length;
            zlib.Write(toc, start, length);
            zlib.Flush();
            int stored = (int)(buffer.Length - before);
            BinaryPrimitives.WriteUInt32BigEndian(head, (uint)stored);
            BinaryPrimitives.WriteUInt32BigEndian(head.AsSpan(4), (uint)length);
            output.Write(head);
            output.Write(buffer.GetBuffer(), (int)before, stored);
        }
        for (int i = 0; i < toc.Length; i += 0x10000) Piece(i, Math.Min(0x10000, toc.Length - i));
        if (toc.Length % 0x10000 == 0) Piece(toc.Length, 0);
        zlib.Dispose();
        return output.ToArray();
    }

    private static (byte[] Blob, int[] Chunks) PackEntry(byte[] data)
    {
        var pieces = new List<byte[]>();
        var sizes = new List<int>();
        int p = 0;
        while (p < data.Length || pieces.Count == 0)
        {
            int n = Math.Min(data.Length - p, 0x10000);
            byte[] z;
            while (true)
            {
                z = SyncFlushed(data.AsSpan(p, n));
                bool last = p + n >= data.Length;
                if (z.Length <= 0x8000 && (last || PadOk(0x8000 - z.Length))) break;
                n = z.Length > 0x8000 ? (int)((long)n * 0x7c00 / z.Length) : n - 64;
            }
            pieces.Add(z);
            sizes.Add(n);
            p += n;
        }
        var blob = new MemoryStream();
        for (int i = 0; i < pieces.Count; i++)
        {
            blob.Write(pieces[i]);
            if (i < pieces.Count - 1) Pad(blob, 0x8000 - pieces[i].Length);
        }
        return (blob.ToArray(), sizes.ToArray());
    }

    private static byte[] NameBytes(string name) => [.. Encoding.Latin1.GetBytes(name), 0];

    private static void Header(Stream output, byte[] tocStream, bool compressed, out long dataBase, int baseAlign = 0x8000)
    {
        dataBase = (9 + tocStream.Length + baseAlign - 1) / baseAlign * baseAlign;
        Span<byte> head = stackalloc byte[9];
        BinaryPrimitives.WriteUInt32BigEndian(head, (uint)dataBase);
        BinaryPrimitives.WriteUInt32BigEndian(head[4..], 3);
        head[8] = (byte)(compressed ? 1 : 0);
        output.Write(head);
        output.Write(tocStream);
        output.Write(new byte[dataBase - 9 - tocStream.Length]);
    }

    /// <summary>A compressed bank (the level model banks) built in memory.</summary>
    public static byte[] BuildCompressed(IReadOnlyList<string> names, Func<string, byte[]> dataOf, int align = 16)
    {
        var toc = new MemoryStream();
        var blobs = new List<(byte[] Blob, int Pad)>();
        byte[] u32 = new byte[4];
        void Put(uint value) { BinaryPrimitives.WriteUInt32BigEndian(u32, value); toc.Write(u32); }
        Put((uint)names.Count);
        long offset = 0;
        foreach (string name in names)
        {
            byte[] data = dataOf(name);
            (byte[] blob, int[] chunks) = PackEntry(data);
            byte[] nb = NameBytes(name);
            Put((uint)nb.Length); toc.Write(nb);
            Put((uint)offset); Put((uint)data.Length); Put((uint)blob.Length); Put((uint)chunks.Length);
            foreach (int c in chunks) Put((uint)c);
            int pad = (int)((align - blob.Length % align) % align);
            blobs.Add((blob, pad));
            offset += blob.Length + pad;
        }
        var output = new MemoryStream();
        Header(output, TocStream(toc.ToArray()), compressed: true, out _);
        foreach ((byte[] blob, int pad) in blobs) { output.Write(blob); output.Write(new byte[pad]); }
        return output.ToArray();
    }

    /// <summary>An uncompressed bank streamed to disk (streaming.bnk, levels.bnk, headers).</summary>
    public static void WriteUncompressed(string path, IReadOnlyList<string> names, Func<string, int> sizeOf,
                                         Func<string, byte[]> dataOf, int align, CancellationToken cancel)
    {
        var toc = new MemoryStream();
        byte[] u32 = new byte[4];
        void Put(uint value) { BinaryPrimitives.WriteUInt32BigEndian(u32, value); toc.Write(u32); }
        Put((uint)names.Count);
        long offset = 0;
        foreach (string name in names)
        {
            int size = sizeOf(name);
            byte[] nb = NameBytes(name);
            Put((uint)nb.Length); toc.Write(nb);
            Put((uint)offset); Put((uint)size);
            offset += size + (align - size % align) % align;
        }
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temp = path + ".tmp";
        using (var output = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
        {
            Header(output, TocStream(toc.ToArray()), compressed: false, out _);
            foreach (string name in names)
            {
                cancel.ThrowIfCancellationRequested();
                byte[] data = dataOf(name);
                if (data.Length != sizeOf(name)) throw new InvalidOperationException($"{name} changed size while writing.");
                output.Write(data);
                output.Write(new byte[(align - data.Length % align) % align]);
            }
        }
        File.Move(temp, path, overwrite: true);
    }
}
