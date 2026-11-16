"""cffi API-mode builder for libagentops."""

from __future__ import annotations

from pathlib import Path

from cffi import FFI

_ROOT = Path(__file__).resolve().parents[2]
_HEADER = _ROOT / "include" / "agentops.h"

ffibuilder = FFI()
_HEADER_TEXT = _HEADER.read_text(encoding="utf-8")
_HEADER_CDEF = "\n".join(
    line for line in _HEADER_TEXT.splitlines() if not line.lstrip().startswith("#")
)
ffibuilder.cdef(_HEADER_CDEF)
ffibuilder.set_source(
    "agentops_engine._cext",
    '#include "agentops.h"',
    include_dirs=["include", "csrc"],
    sources=[
        "csrc/engine.c",
        "csrc/policy.c",
        "csrc/glob.c",
        "csrc/ratelimit.c",
        "csrc/agent_table.c",
        "csrc/blob.c",
    ],
    extra_compile_args=["-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion"],
    extra_link_args=["-pthread"],
    libraries=["pthread"],
)
