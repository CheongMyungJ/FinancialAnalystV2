from __future__ import annotations

import hashlib
from pathlib import Path

from .models import GeneratedTest, RiskFinding
from .spec_extract import detect_primary_namespace, extract_functions_from_header, infer_contract_hints


def _stable_id(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def _find_nearby_header(repo_root: Path, finding_path: str) -> Path | None:
    p = (repo_root / finding_path).resolve()
    if p.suffix.lower() in {".h", ".hpp", ".hh", ".hxx"} and p.exists():
        return p
    # Try same stem
    stem = p.stem
    for ext in [".h", ".hpp", ".hh", ".hxx"]:
        cand = p.with_suffix(ext)
        if cand.exists():
            return cand
    # As a last resort, search in repo (bounded)
    for ext in [".h", ".hpp"]:
        for cand in repo_root.rglob(stem + ext):
            return cand
    return None


def _emit_copy_like_tests(qual: str, func_name: str) -> str:
    # Generic contract-oriented tests for (char* dst, size_t dst_size, const char* src)
    suite = func_name.capitalize()
    return f"""
TEST(Generated_{suite}, NullDstOrZeroSize_NoCrash) {{
  EXPECT_EQ({qual}{func_name}(nullptr, 10, "abc"), 0u);
  char buf[4] = {{'x','x','x','\\0'}};
  EXPECT_EQ({qual}{func_name}(buf, 0, "abc"), 0u);
  EXPECT_EQ(buf[0], 'x');
}}

TEST(Generated_{suite}, NullSrc_NullTerminates) {{
  char buf[4] = {{'x','x','x','\\0'}};
  EXPECT_EQ({qual}{func_name}(buf, sizeof(buf), nullptr), 0u);
  EXPECT_EQ(buf[0], '\\0');
}}

TEST(Generated_{suite}, Truncation_NullTerminates_AndReturnBounded) {{
  char buf[4];
  auto n = {qual}{func_name}(buf, sizeof(buf), "abcdef");
  EXPECT_LT(n, sizeof(buf));
  EXPECT_EQ(buf[sizeof(buf) - 1], '\\0');
}}
""".strip()


def _emit_safe_div_like_tests(qual: str, func_name: str, hints: dict[str, str]) -> str:
    suite = func_name.capitalize()
    # If doc explicitly says b==0 returns 0, assert it; otherwise just exercise edge.
    if hints.get("b_eq_0_returns_0") == "true":
        return f"""
TEST(Generated_{suite}, ZeroDivisor_ReturnsZero) {{
  EXPECT_EQ({qual}{func_name}(10, 0), 0);
}}
""".strip()
    return f"""
TEST(Generated_{suite}, ZeroDivisor_NoCrash) {{
  (void){qual}{func_name}(10, 0);
  SUCCEED();
}}
""".strip()


def _emit_idempotent_string_tests(qual: str, func_name: str) -> str:
    suite = func_name.capitalize()
    return f"""
TEST(Generated_{suite}, Idempotent_OnRepeatedApplication) {{
  const std::string in = "  AbC  ";
  const auto once = {qual}{func_name}(in);
  const auto twice = {qual}{func_name}(once);
  EXPECT_EQ(once, twice);
}}
""".strip()


def generate_tests_for_findings(
    repo_root: Path,
    findings: list[RiskFinding],
    max_tests: int,
    out_dir: Path | None = None,
    hints: dict[str, object] | None = None,
) -> tuple[list[GeneratedTest], list[dict[str, str]]]:
    """
    Returns (generated_tests, human_questions).
    Initial version focuses on header-based public APIs and conservative templates.
    """
    out_dir = out_dir or (repo_root / "tests" / "generated")
    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[GeneratedTest] = []
    questions: list[dict[str, str]] = []

    force_header = None
    force_namespace = None
    force_functions: set[str] | None = None
    if hints:
        if isinstance(hints.get("force_header"), str):
            force_header = str(hints.get("force_header"))
        if isinstance(hints.get("force_namespace"), str):
            force_namespace = str(hints.get("force_namespace"))
        ff = hints.get("force_functions")
        if isinstance(ff, list) and all(isinstance(x, str) for x in ff):
            force_functions = set(ff)

    for f in findings:
        if len(generated) >= max_tests:
            break

        header = Path(repo_root / force_header).resolve() if force_header else _find_nearby_header(repo_root, f.path)
        if not header:
            questions.append(
                {
                    "id": f"Q_{_stable_id('no_header:' + f.path)}",
                    "path": f.path,
                    "message": "public header를 찾지 못했습니다. 테스트 대상 API(헤더/심볼)를 지정해 주세요.",
                }
            )
            continue

        text = header.read_text(encoding="utf-8", errors="ignore")
        funcs = extract_functions_from_header(text)
        ns = force_namespace or detect_primary_namespace(text)
        qual = f"{ns}::" if ns else ""
        if not funcs:
            questions.append(
                {
                    "id": f"Q_{_stable_id('parse_fail:' + header.as_posix())}",
                    "path": header.relative_to(repo_root).as_posix(),
                    "message": "함수 선언을 파싱하지 못했습니다. (복잡한 매크로/템플릿이면) 테스트 대상 심볼을 지정해 주세요.",
                }
            )
            continue

        # Very conservative: only generate for a few known patterns.
        body_parts: list[str] = []
        extra_includes: set[str] = set()
        rationale_parts: list[str] = []
        for fn in funcs:
            if force_functions is not None and fn.name not in force_functions:
                continue
            hints = infer_contract_hints(fn.doc)
            param_sig = ",".join([p.type.replace(" ", "") for p in fn.params])
            name_l = fn.name.lower()
            ret = fn.return_type.replace(" ", "")

            if "copy" in name_l and len(fn.params) >= 3 and ("char*" in param_sig and "size_t" in param_sig):
                body_parts.append(_emit_copy_like_tests(qual, fn.name))
                rationale_parts.append(f"{fn.name}: buffer/length contract edge cases")
            elif "div" in name_l and len(fn.params) == 2 and ret in {"int", "long", "longlong"}:
                body_parts.append(_emit_safe_div_like_tests(qual, fn.name, hints))
                rationale_parts.append(f"{fn.name}: divide-by-zero edge/contract")
            elif any(k in name_l for k in ["normalize", "trim", "lower", "upper"]) and len(fn.params) == 1:
                p0 = fn.params[0].type.replace(" ", "")
                if p0 in {"std::string", "string"} and ret in {"std::string", "string"}:
                    extra_includes.add("<string>")
                    body_parts.append(_emit_idempotent_string_tests(qual, fn.name))
                    rationale_parts.append(f"{fn.name}: metamorphic (idempotence)")

        if not body_parts:
            questions.append(
                {
                    "id": f"Q_{_stable_id('no_pattern:' + header.as_posix())}",
                    "path": header.relative_to(repo_root).as_posix(),
                    "message": "자동 생성 가능한 API 패턴을 찾지 못했습니다. 가장 위험한 함수 1~3개 이름(또는 시그니처)을 알려주시면 그걸로 생성하겠습니다.",
                }
            )
            continue

        test_id = _stable_id(f.path + header.as_posix())
        out_path = out_dir / f"agent_{test_id}_generated_test.cpp"

        extra = "".join([f"#include {inc}\n" for inc in sorted(extra_includes)])
        content = f"""\
#include <gtest/gtest.h>
{extra}
#include \"{header.relative_to(repo_root).as_posix()}\"

// NOTE: Generated by tools/test_agent. Focus: contract/edge cases likely to reveal early bugs.

{chr(10).join(body_parts)}
"""
        out_path.write_text(content, encoding="utf-8")
        generated.append(
            GeneratedTest(
                path=out_path.relative_to(repo_root).as_posix(),
                target_hint=f.path,
                rationale="; ".join(rationale_parts),
            )
        )

    return generated, questions

