"""Pure-Python parser and validation helpers for config/shader_prebuild.txt.

This is deliberately limited to the text format consumed by
src/core/shader_prebuild.cpp: it does not rebuild shaders, touch the SDK cache,
or read game data. It is used by tests and QA evidence to catch malformed or
truncated pre-build lists before a build is staged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

FORMAT = 1
TITLE_ID = "4D5307F1"
HEADER_SIZE = 8
RECORD_SIZE = 72
XEX_BASE = 0x82000000


@dataclass(frozen=True)
class ListShader:
    hash: int
    packed: int
    source: str
    bank: str = ""
    entry: int = 0
    offset: int = 0
    xex_address: int = 0
    patches: tuple[tuple[int, int], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ShaderPrebuildList:
    format: int
    title: str
    xsh_header: bytes
    xpso_header: bytes
    shaders: tuple[ListShader, ...]
    pipelines: tuple[bytes, ...]


def parse_list(text: str) -> ShaderPrebuildList:
    format_value: int | None = None
    title: str | None = None
    xsh_header: bytes | None = None
    xpso_header: bytes | None = None
    shaders: list[ListShader] = []
    pipelines: list[bytes] = []

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        fields = raw_line.split()
        if not fields:
            continue
        kind = fields[0]
        if kind == "fable2-shader-prebuild":
            if len(fields) != 2:
                raise ValueError(f"line {line_number}: bad prebuild header")
            format_value = int(fields[1])
            if format_value != FORMAT:
                raise ValueError(f"line {line_number}: unsupported format {format_value}")
        elif kind == "title":
            if len(fields) != 2:
                raise ValueError(f"line {line_number}: bad title")
            title = fields[1]
        elif kind in ("xsh-header", "xpso-header"):
            if len(fields) != 2:
                raise ValueError(f"line {line_number}: bad {kind}")
            try:
                value = bytes.fromhex(fields[1])
            except ValueError as exc:
                raise ValueError(f"line {line_number}: invalid hex in {kind}") from exc
            if kind == "xsh-header":
                if len(value) != HEADER_SIZE:
                    raise ValueError(f"line {line_number}: xsh header must be {HEADER_SIZE} bytes")
                xsh_header = value
            else:
                if len(value) != 12:
                    raise ValueError(f"line {line_number}: xpso header must be 12 bytes")
                xpso_header = value
        elif kind == "shader":
            if len(fields) < 4:
                raise ValueError(f"line {line_number}: truncated shader")
            try:
                hash_value = int(fields[1], 16)
                packed = int(fields[2], 16)
            except ValueError as exc:
                raise ValueError(f"line {line_number}: bad shader hash or packed value") from exc
            source_kind = fields[3]
            rest = fields[4:]
            if source_kind == "bank":
                if len(rest) < 3:
                    raise ValueError(f"line {line_number}: truncated bank shader")
                bank = rest[0]
                try:
                    entry = int(rest[1])
                    offset = int(rest[2])
                except ValueError as exc:
                    raise ValueError(f"line {line_number}: bad bank entry or offset") from exc
                patch_fields = rest[3:]
                xex_address = 0
            elif source_kind == "xex":
                if not rest:
                    raise ValueError(f"line {line_number}: truncated xex shader")
                try:
                    xex_address = int(rest[0], 16)
                except ValueError as exc:
                    raise ValueError(f"line {line_number}: bad xex address") from exc
                if xex_address < XEX_BASE:
                    raise ValueError(f"line {line_number}: xex address below base")
                bank = ""
                entry = 0
                offset = xex_address - XEX_BASE
                patch_fields = rest[1:]
            else:
                raise ValueError(f"line {line_number}: unknown shader source {source_kind!r}")
            patches: list[tuple[int, int]] = []
            for patch in patch_fields:
                if ":" not in patch:
                    raise ValueError(f"line {line_number}: bad patch {patch!r}")
                index_text, xor_text = patch.split(":", 1)
                try:
                    patches.append((int(index_text), int(xor_text, 16)))
                except ValueError as exc:
                    raise ValueError(f"line {line_number}: bad patch {patch!r}") from exc
            shaders.append(
                ListShader(
                    hash=hash_value,
                    packed=packed,
                    source=source_kind,
                    bank=bank,
                    entry=entry,
                    offset=offset,
                    xex_address=xex_address,
                    patches=tuple(patches),
                )
            )
        elif kind == "pipeline":
            if len(fields) != 2:
                raise ValueError(f"line {line_number}: bad pipeline")
            try:
                record = bytes.fromhex(fields[1])
            except ValueError as exc:
                raise ValueError(f"line {line_number}: invalid pipeline hex") from exc
            if len(record) != RECORD_SIZE:
                raise ValueError(
                    f"line {line_number}: pipeline must be {RECORD_SIZE} bytes, got {len(record)}"
                )
            pipelines.append(record)
        else:
            raise ValueError(f"line {line_number}: unknown record {kind!r}")

    if format_value is None:
        raise ValueError("missing fable2-shader-prebuild header")
    if title is None:
        raise ValueError("missing title")
    if title != TITLE_ID:
        raise ValueError(f"unexpected title {title!r}")
    if xsh_header is None:
        raise ValueError("missing xsh-header")
    if xpso_header is None:
        raise ValueError("missing xpso-header")
    if not shaders:
        raise ValueError("prebuild list contains no shaders")
    if not pipelines:
        raise ValueError("prebuild list contains no pipelines")
    return ShaderPrebuildList(
        format=format_value,
        title=title,
        xsh_header=xsh_header,
        xpso_header=xpso_header,
        shaders=tuple(shaders),
        pipelines=tuple(pipelines),
    )


def parse_file(path: str | Path) -> ShaderPrebuildList:
    return parse_list(Path(path).read_text(encoding="utf-8"))


def validate_structure(lst: ShaderPrebuildList) -> list[str]:
    errors: list[str] = []
    if lst.format != FORMAT:
        errors.append(f"unsupported format {lst.format}")
    if lst.title != TITLE_ID:
        errors.append(f"unexpected title {lst.title!r}")
    if len(lst.xsh_header) != HEADER_SIZE:
        errors.append("xsh header has the wrong size")
    if len(lst.xpso_header) != 12:
        errors.append("xpso header has the wrong size")
    if not lst.shaders:
        errors.append("no shaders")
    if not lst.pipelines:
        errors.append("no pipelines")
    seen_hashes: set[int] = set()
    for index, shader in enumerate(lst.shaders):
        if shader.hash in seen_hashes:
            errors.append(f"duplicate shader hash at shader {index}: {shader.hash:016X}")
        seen_hashes.add(shader.hash)
        if shader.source not in ("bank", "xex"):
            errors.append(f"shader {index}: unknown source {shader.source!r}")
        if shader.source == "bank":
            if not shader.bank:
                errors.append(f"shader {index}: missing bank path")
            if shader.entry < 0:
                errors.append(f"shader {index}: negative bank entry")
            if shader.offset < 0:
                errors.append(f"shader {index}: negative bank offset")
        if shader.source == "xex":
            if shader.xex_address < XEX_BASE:
                errors.append(f"shader {index}: xex address below base")
    for index, pipeline in enumerate(lst.pipelines):
        if len(pipeline) != RECORD_SIZE:
            errors.append(f"pipeline {index}: wrong size {len(pipeline)}")
    return errors


def unique_shader_hashes(lst: ShaderPrebuildList) -> set[int]:
    return {shader.hash for shader in lst.shaders}


def source_summary(lst: ShaderPrebuildList) -> dict[str, int]:
    counts: dict[str, int] = {}
    for shader in lst.shaders:
        counts[shader.source] = counts.get(shader.source, 0) + 1
    return counts
