from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CppParam:
    type: str
    name: str


@dataclass(frozen=True)
class CppFunction:
    namespace: str | None
    return_type: str
    name: str
    params: list[CppParam]
    doc: str


_FUNC_RE = re.compile(
    r"^(?P<ret>[\w:\<\>\s\*&]+?)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^)]*)\)\s*;",
    re.MULTILINE,
)


def _parse_params(s: str) -> list[CppParam]:
    s = s.strip()
    if not s or s == "void":
        return []
    parts = [p.strip() for p in s.split(",")]
    out: list[CppParam] = []
    for p in parts:
        # Very lightweight: split last token as name.
        tokens = p.replace("\t", " ").split()
        if len(tokens) < 2:
            out.append(CppParam(type=p, name=f"arg{len(out)}"))
            continue
        name = tokens[-1]
        typ = " ".join(tokens[:-1])
        out.append(CppParam(type=typ.strip(), name=name.strip()))
    return out


def extract_functions_from_header(text: str) -> list[CppFunction]:
    lines = text.splitlines()

    funcs: list[CppFunction] = []

    # Precompute doc blocks: consecutive // lines immediately above.
    doc_above: dict[int, str] = {}
    buf: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            buf.append(stripped.lstrip("/").strip())
        else:
            if buf:
                doc_above[i] = "\n".join(buf).strip()
                buf = []
    # If file ends with comment, ignore.

    # Regex over full text to pick functions; then locate doc near match.
    for m in _FUNC_RE.finditer(text):
        ret = " ".join(m.group("ret").split())
        name = m.group("name")
        params = _parse_params(m.group("params"))

        # Determine doc: find line index of match start and look up doc_above
        prefix = text[: m.start()]
        line_idx = prefix.count("\n")
        doc = doc_above.get(line_idx, "")

        funcs.append(CppFunction(namespace=None, return_type=ret, name=name, params=params, doc=doc))

    return funcs


def detect_primary_namespace(text: str) -> str | None:
    """
    Best-effort: if the header declares exactly one simple namespace, return it.
    This is intentionally conservative to avoid generating uncompilable code.
    """
    names = re.findall(r"^\s*namespace\s+([A-Za-z_]\w*)\s*\{", text, flags=re.MULTILINE)
    uniq = sorted(set(names))
    if len(uniq) == 1:
        return uniq[0]
    return None


def infer_contract_hints(doc: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    d = doc.lower()
    if "if b == 0" in d and "returns 0" in d:
        hints["b_eq_0_returns_0"] = "true"
    if "always null-terminates" in d or "always null terminates" in d:
        hints["always_null_terminate"] = "true"
    if "does nothing" in d:
        hints["does_nothing_on_invalid"] = "true"
    return hints

