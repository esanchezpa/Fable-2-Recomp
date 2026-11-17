#!/usr/bin/env python3
"""Embed a binary file as a C++ byte array with external linkage.

Used by the root CMakeLists.txt to bake the keycap prompt font
(src/gui/keycap_render.cpp, LoadFont) into fable_2 so the glyphs render even
when the staged assets/fonts/ copy is missing next to the exe (for example a
manually copied deploy). Usage:

    embed_file.py <input> <output.cpp> <namespace> <array_name>
"""
import sys


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: embed_file.py <input> <output.cpp> <namespace> <array_name>", file=sys.stderr)
        return 2
    src, dst, namespace, array_name = sys.argv[1:]
    with open(src, "rb") as fh:
        data = fh.read()
    size = len(data)
    out = []
    out.append("// Generated from %s by tools/embed_file.py; do not edit.\n" % src.replace("\\", "/"))
    out.append("#include <cstdint>\n\n")
    out.append("namespace %s {\n\n" % namespace)
    out.append("extern const uint8_t %s[%d];\n" % (array_name, size))
    out.append("extern const uint32_t %s_size;\n" % array_name)
    out.append("\nconst uint8_t %s[%d] = {\n" % (array_name, size))
    for i in range(0, size, 20):
        chunk = data[i:i + 20]
        out.append("    " + ",".join("0x%02X" % b for b in chunk) + ",\n")
    out.append("};\n\n")
    out.append("const uint32_t %s_size = %d;\n" % (array_name, size))
    out.append("\n}  // namespace %s\n" % namespace)
    with open(dst, "w", encoding="ascii", newline="\n") as fh:
        fh.write("".join(out))
    print("embedded %s (%d bytes) -> %s" % (src, size, dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
