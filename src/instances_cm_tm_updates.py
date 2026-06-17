#!/usr/bin/env python3
"""
Wrapper CLI para recalcular TM (max_running_time) e CM (max_financial_cost) das instâncias.

Suporta duas estratégias de cálculo, ambas centralizadas em core/ e reutilizáveis:

  resource_aware (padrão) -- core.tm_cm_resource_aware
      List scheduling + custo do recurso mais caro. Bounds apertados que o CPLEX consegue
      resolver. Tipo 1 (VM/FX) → FX paralelo ilimitado; tipo 0 (só VM) → disputam num_vms VMs.
      CM é o dual: tipo 1 = max(FX, VM) por tarefa; tipo 0 = VM ligada todo o workflow.
      Margem padrão 0.25.

  pessimistic -- core.tm_cm_pessimistic
      Pior caso sequencial (implementação segura original): soma das piores durações, sem
      DAG nem paralelismo, com TODAS as VMs ociosas o horizonte todo. Bounds válidos porém
      muito folgados (TM alto explode o espaço de busca do CPLEX). Margem padrão 0.0.

NOTA (piso de tempo): instâncias sintéticas usam tempo inteiro (piso 1.0); reais usam
    segundos contínuos (piso 0.0). Detectado automaticamente.

Uso:
    python instances_cm_tm_updates.py --instances-dir ../data/synthetic/user
    python instances_cm_tm_updates.py --instances-dir ../data/synthetic/user --strategy pessimistic
"""

import argparse
import sys
from pathlib import Path

from core import tm_cm_resource_aware, tm_cm_pessimistic

# Estratégias disponíveis: nome -> (módulo, margem padrão)
STRATEGIES = {
    'resource_aware': (tm_cm_resource_aware, 0.25),
    'pessimistic': (tm_cm_pessimistic, 0.0),
}
DEFAULT_STRATEGY = 'resource_aware'


def update_file_bounds(filepath: Path, verbose: bool = False, margin: float = None,
                       strategy: str = DEFAULT_STRATEGY) -> None:
    """
    Recalcula TM/CM e reescreve a linha de cabeçalho do arquivo, preservando o formato.

    Args:
        filepath: Caminho do arquivo de instância.
        verbose: Imprimir diagnósticos intermediários do cálculo.
        margin: Folga aplicada a TM e CM. Se None, usa a margem padrão da estratégia.
        strategy: 'resource_aware' (padrão) ou 'pessimistic'.
    """
    module, default_margin = STRATEGIES[strategy]
    if margin is None:
        margin = default_margin

    try:
        bounds = module.compute_bounds(filepath, margin=margin)
    except Exception as e:
        print(f"  Erro ao processar {filepath.name}: {e}")
        return

    new_tm = bounds['tm_final']
    new_cm = bounds['cm_final']

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith('#'):
            parts = line.strip().split()
            if len(parts) >= 8:
                # Posições 6 e 7 são TM e CM
                parts[6] = f"{new_tm:.4f}"
                parts[7] = f"{new_cm:.10f}"
                lines[i] = "\t".join(parts) + "\n"
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print(f"  {filepath.name}: TM={new_tm:.4f}  CM={new_cm:.10f}")
                if verbose:
                    _print_diagnostics(bounds)
                break


def _print_diagnostics(bounds: dict) -> None:
    """Imprime as chaves de diagnóstico presentes (variam por estratégia)."""
    if 'tm_ls' in bounds:        # resource_aware
        print(f"    TM_seq={bounds['tm_seq']:.4f}, TM_listsched={bounds['tm_ls']:.4f}")
        print(f"    CM_tasks={bounds['cm_tasks']:.10f}, CM_vm_idle={bounds['cm_vm_idle']:.10f}")
    elif 'tm_raw' in bounds:     # pessimistic
        print(f"    TM_raw={bounds['tm_raw']:.4f}")
        print(f"    base_cost={bounds['base_cost']:.10f}, idle_penalty={bounds['idle_penalty']:.10f}")


def main():
    parser = argparse.ArgumentParser(
        description="Atualiza TM e CM nas instâncias .txt (resource-aware ou pessimista)"
    )
    parser.add_argument(
        "--instances-dir", type=Path, default=Path(""),
        help="Diretório (relativo a este script ou absoluto) com as instâncias"
    )
    parser.add_argument(
        "--patterns", nargs="+", default=["*.txt"],
        help="Padrões de arquivo (ex: Synthetic_007*.txt). Use * como curinga."
    )
    parser.add_argument(
        "--strategy", choices=sorted(STRATEGIES), default=DEFAULT_STRATEGY,
        help=f"Estratégia de cálculo (padrão {DEFAULT_STRATEGY})"
    )
    parser.add_argument(
        "--margin", type=float, default=None,
        help="Folga aplicada a TM e CM. Se omitido, usa o padrão da estratégia "
             "(resource_aware=0.25, pessimistic=0.0)."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Imprimir diagnósticos intermediários de cálculo"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    target_dir = (script_dir / args.instances_dir).resolve()

    if not target_dir.exists():
        print(f"Erro: Diretório {target_dir} não encontrado.")
        sys.exit(1)

    matched = set()
    for pattern in args.patterns:
        matched.update(target_dir.glob(pattern))
    matched = sorted(matched)

    if not matched:
        print(f"Nenhum arquivo encontrado em {target_dir} com os padrões: {args.patterns}")
        return

    eff_margin = args.margin if args.margin is not None else STRATEGIES[args.strategy][1]
    print(f"Encontrados {len(matched)} arquivos "
          f"(estratégia={args.strategy}, margem={eff_margin:.0%}).\n")
    for filepath in matched:
        update_file_bounds(filepath, verbose=args.verbose, margin=args.margin,
                           strategy=args.strategy)
        print("=" * 60)


if __name__ == "__main__":
    main()
