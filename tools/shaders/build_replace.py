"""Compile the Modern-graphics shader rewrites (shaders/*.hlsl) to the DXBC
files the SDK swaps in for the game's own shaders (cvar shader_replace_dir,
seeded from [graphics] shader_rewrites).

    python tools/shaders/build_replace.py [--out DIR]

Default output: shaders/replace in the repo (checked in; CMake stages it next
to the exe as shaders/replace at build time). Each entry in
SHADERS is (source, defines, ucode hash): the SDK replaces the translated
shader whose ucode hash matches the file name. See shaders/README.md for how
hashes are found.

Shaders that read the pixel position (GuestPixelPosition / RES_SCALE) bake
the resolution scale in, so they are built once per scale as
<hash>.x<scale>.dxbc; the SDK picks the one for the running scale.
"""
import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'shaders')
DEFAULT_OUT = os.path.join(SRC, 'replace')

# (source file, profile, extra defines, ucode hash)
SHADERS = [
    ('water.ps.hlsl', 'ps_5_1', [], 'A17D8AEC3A817D45'),            # open water
    ('water.ps.hlsl', 'ps_5_1', ['EDGE=1'], 'F6D98C7B4D98438B'),    # shore edge
    ('foliage.ps.hlsl', 'ps_5_1', [], '7CD57B81550F19E3'),          # tree leaves
    ('sky.ps.hlsl', 'ps_5_1', [], '61976295517D7015'),              # sun-lit cloud layer
    ('lit.ps.hlsl', 'ps_5_1', [], '8D900846800943C8'),              # lit opaque: rocks, stone, skin, cloth
    ('lit_shadow.ps.hlsl', 'ps_5_1', [], '648B965C200A5113'),  # lit + shadow map: pillars, ruins, dead trees
    ('trunk.ps.hlsl', 'ps_5_1', [], '00E09D1BC5295D52'),            # tree trunks, second foliage layer
    ('fern.ps.hlsl', 'ps_5_1', [], '165EDCD2CB963868'),             # ferns and bushes
    ('tonemap.ps.hlsl', 'ps_5_1', [], '37B186F4BD3288F7'),          # final composite: bloom + tone curve
    ('terrain.ps.hlsl', 'ps_5_1', [], '9C2144E42E95A76F'),          # ground + cliff rock blend
    ('grass.ps.hlsl', 'ps_5_1', [], '2F8A0341E8C09698'),            # near ground (grass, forest floor)
    ('ground.ps.hlsl', 'ps_5_1', [], '7DDAD5C29B3F56EE'),           # far lightmapped terrain
    ('splat.ps.hlsl', 'ps_5_1', [], '4755A2E4A05BA678'),            # dirt / path splats over the ground
]


# Resolution scales the launcher offers (1x, 2x, 3x).
SCALES = (1, 2, 3)


def find_fxc():
    env = os.environ.get('FXC')
    if env and os.path.isfile(env):
        return env
    pattern = r'C:\Program Files (x86)\Windows Kits\10\bin\10.*\x64\fxc.exe'
    found = sorted(glob.glob(pattern))
    if not found:
        sys.exit('fxc.exe not found (Windows SDK); set FXC=<path>')
    return found[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=DEFAULT_OUT)
    args = parser.parse_args()
    fxc = find_fxc()
    os.makedirs(args.out, exist_ok=True)
    for source, profile, defines, hash_ in SHADERS:
        text = open(os.path.join(SRC, source), encoding='utf-8').read()
        scaled = 'GuestPixelPosition' in text or 'RES_SCALE' in text
        variants = [(f'.x{n}', [f'RES_SCALE={n}.0']) for n in SCALES] if scaled else [('', [])]
        stale = os.path.join(args.out, hash_ + '.dxbc')
        if scaled and os.path.exists(stale):
            os.remove(stale)
        for suffix, extra in variants:
            out = os.path.join(args.out, hash_ + suffix + '.dxbc')
            cmd = [fxc, '/nologo', '/T', profile, '/E', 'main', '/O3',
                   '/enable_unbounded_descriptor_tables', '/Fo', out]
            for d in defines + extra:
                cmd += ['/D', d]
            cmd.append(os.path.join(SRC, source))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode:
                print(result.stdout, result.stderr, file=sys.stderr)
                sys.exit(f'{source} ({defines + extra}) failed')
            print(f'{source:20} {",".join(defines + extra) or "-":24} -> {out}')


if __name__ == '__main__':
    main()
