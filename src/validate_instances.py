import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.instance_io import InstanceParser
from core.instance_validation import InstanceValidator, MatrixTimeCoherenceValidator, ValidationIssue


def _collect_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]

    candidates = sorted(path.glob("*.txt"))
    return [p for p in candidates if _looks_like_instance_file(p)]


def _looks_like_instance_file(path: Path) -> bool:
    name = path.name
    name_matches = ("_T" in name and "_C" in name and "_D" in name) or name.startswith("I")
    if not name_matches:
        return False

    try:
        with path.open("r", encoding="utf-8") as f:
            first_non_empty = next((line.strip() for line in f if line.strip()), "")
        return first_non_empty.startswith("#<#tasks>")
    except OSError:
        return False


def _print_issues(file_path: Path, issues: List[ValidationIssue]) -> int:
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    print(f"\n[{file_path}]")
    if not issues:
        print("OK - sem inconsistências")
        return 0

    for i in issues:
        print(f"{i.severity:<7} {i.code:<5} {i.message}")

    print(f"Resumo: {len(errors)} erro(s), {len(warnings)} warning(s)")
    return len(errors)


def _build_file_result(file_path: Path, issues: List[ValidationIssue], parse_error: Optional[str] = None) -> Dict[str, Any]:
    if parse_error is not None:
        return {
            "file": str(file_path),
            "status": "parse_error",
            "error_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "PARSE",
                    "message": parse_error,
                }
            ],
        }

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]
    return {
        "file": str(file_path),
        "status": "ok" if not issues else "invalid",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(i) for i in issues],
    }


def _write_json_output(json_target: str, payload: Dict[str, Any]) -> None:
    content = json.dumps(payload, indent=2, ensure_ascii=True)
    if json_target == "-":
        print(content)
        return

    out_path = Path(json_target)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida arquivos de instância")
    parser.add_argument(
        "path",
        nargs="?",
        default="data/synthetic_user_defined",
        help="Arquivo .txt ou diretório com arquivos de instância",
    )
    parser.add_argument(
        "--sum-tolerance-percent",
        type=float,
        default=MatrixTimeCoherenceValidator.DEFAULT_SUM_TOLERANCE_PERCENT,
        help="Tolerância relativa para validação dos somatórios da matriz de tempo (ex: 0.10 = 10%)",
    )
    parser.add_argument(
        "--output-json",
        nargs="?",
        const="-",
        default=None,
        help="Gera saída JSON. Se informado sem valor, imprime no stdout; se informado com caminho, grava no arquivo.",
    )

    args = parser.parse_args()
    target = Path(args.path)
    files = _collect_files(target)
    if not files:
        print(f"Nenhum arquivo encontrado em: {target}")
        return 1

    validator = InstanceValidator()

    total_errors = 0
    file_results: List[Dict[str, Any]] = []
    for file_path in files:
        try:
            parsed = InstanceParser.parse_file(file_path)
            issues = validator.validate(parsed, sum_tolerance_percent=args.sum_tolerance_percent)
            file_results.append(_build_file_result(file_path, issues))
            total_errors += _print_issues(file_path, issues)
        except Exception as exc:
            total_errors += 1
            file_results.append(_build_file_result(file_path, [], parse_error=f"Falha ao validar arquivo: {exc}"))
            print(f"\n[{file_path}]\nERROR   PARSE Falha ao validar arquivo: {exc}")

    if args.output_json is not None:
        payload = {
            "path": str(target),
            "sum_tolerance_percent": args.sum_tolerance_percent,
            "files": file_results,
            "summary": {
                "file_count": len(file_results),
                "invalid_file_count": sum(1 for x in file_results if x["status"] != "ok"),
                "total_error_count": sum(int(x["error_count"]) for x in file_results),
                "total_warning_count": sum(int(x["warning_count"]) for x in file_results),
            },
            "status": "ok" if total_errors == 0 else "invalid",
        }
        _write_json_output(args.output_json, payload)

    if total_errors > 0:
        print(f"\nFinalizado com inconsistências. Total de erros: {total_errors}")
        return 2

    print("\nFinalizado sem erros.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
