#!/usr/bin/env python3
"""
Gera instâncias sintéticas a partir de topologias definidas em data/instances_definition.txt.

Dois grupos:
  - FX_WORKFLOWS: instâncias normais (task_type=1, VM ou FX).
  - VMONLY_WORKFLOWS: gêmeos VM-only (task_type=0) da MESMA topologia, com sufixo
    "_VMonly" no nome, para comparar FX-elástico vs. VM-limitado no CPLEX/heurística.

Parâmetros de tempo: cpu_time sorteado em [1,10] e slowdown FX em [3,10] (regime de
realismo escolhido). O TM resultante é recalculado pela regra resource-aware (teto por
componente) no momento da escrita do cabeçalho.
"""

import os
import re
import sys
import random
import argparse
from pathlib import Path

from core.workflow_def_io import load_workflows
from model.workflow_generator_user import WorkflowGeneratorUser
from instances_cm_tm_updates import update_file_bounds

# ==========================================
# PARÂMETROS
# ==========================================
INPUT_FILE = "data/instances_definition.txt"
OUTPUT_DIR = "data/synthetic/user"

# Topologias a gerar em cada modo. Edite estas listas para mudar o conjunto.
FX_WORKFLOWS = ["Synthetic_015", "Synthetic_025", "Synthetic_029",
                "Synthetic_032", "Synthetic_042", "Synthetic_060"]
VMONLY_WORKFLOWS = ["Synthetic_007", "Synthetic_022", "Synthetic_032", "Synthetic_060"]
# Geradas por último (mesmo task_type=1 do FX), para não deslocar o fluxo aleatório das
# instâncias acima ao serem adicionadas depois. São topologias rasas (TM menor), úteis
# como casos em que o CPLEX fecha mais rápido.
EXTRA_FX_WORKFLOWS = ["Synthetic_016", "Synthetic_020"]

NUM_VMS = 3
NUM_CONFIGS = 5
NUM_BUCKET_RANGES = 3
USE_INTEGER_TIME = True
FX_SLOWDOWN_MIN = 3.0
FX_SLOWDOWN_MAX = 10.0
SEED = 42  # reprodutibilidade; None = aleatório a cada execução

TASK_PREFIX_REPLACE = {"old": "t", "new": ""}
DATA_PREFIX_REPLACE = {"old": "d", "new": ""}
TASK_ID_OFFSET = 100
DATA_ID_OFFSET = 900


def build_filename(base_id, num_tasks, num_configs, num_data, num_vms, suffix=""):
    match = re.search(r"\d+", str(base_id))
    num_id = int(match.group(0)) if match else 0
    return f"Synthetic_{num_id:03d}_T{num_tasks}_C{num_configs}_D{num_data}_VM{num_vms}{suffix}.txt"


def generate_one(wf, output_dir, task_type, suffix):
    generator = WorkflowGeneratorUser(
        workflow_id=wf["workflow_id"], num_tasks=wf["num_tasks"], num_data=wf["num_data"],
        task_defs=wf["task_defs"], output_dir=output_dir,
        num_vms=NUM_VMS, num_configs=NUM_CONFIGS, num_bucket_ranges=NUM_BUCKET_RANGES,
        use_integer_time=USE_INTEGER_TIME,
        task_prefix_replace=TASK_PREFIX_REPLACE, data_prefix_replace=DATA_PREFIX_REPLACE,
        task_id_offset=TASK_ID_OFFSET, data_id_offset=DATA_ID_OFFSET,
        fx_slowdown_min=FX_SLOWDOWN_MIN, fx_slowdown_max=FX_SLOWDOWN_MAX,
        task_type=task_type,
        cpu_time_range=wf.get("cpu_time_range"),
        read_time_range=wf.get("read_time_range"),
        write_time_range=wf.get("write_time_range"),
    )
    content = generator.generate_workflow_file_content()
    file_name = build_filename(wf["workflow_id"], generator.num_tasks, generator.num_configs,
                               generator.num_data, generator.num_vms, suffix=suffix)
    output_path = os.path.join(output_dir, file_name)
    with open(output_path, "w") as f:
        f.write(content)
    update_file_bounds(Path(output_path))
    tag = "VM-only" if task_type == 0 else "VM/FX"
    print(f"Gerado [{tag}]: {output_path}  T={generator.num_tasks} C={generator.num_configs} "
          f"D={generator.num_data} VM={generator.num_vms}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Gera instâncias sintéticas (VM/FX e gêmeos VM-only).")
    parser.add_argument("--fx", nargs="*", default=FX_WORKFLOWS,
                        help="IDs gerados como VM/FX (task_type=1). Padrão: " + str(FX_WORKFLOWS))
    parser.add_argument("--vmonly", nargs="*", default=VMONLY_WORKFLOWS,
                        help="IDs gerados como gêmeos VM-only (task_type=0). Padrão: " + str(VMONLY_WORKFLOWS))
    parser.add_argument("--extra-fx", nargs="*", default=EXTRA_FX_WORKFLOWS,
                        help="IDs VM/FX gerados por último (não deslocam o fluxo aleatório). Padrão: " + str(EXTRA_FX_WORKFLOWS))
    parser.add_argument("--seed", type=int, default=SEED,
                        help=f"Seed para reprodutibilidade (padrão {SEED}; use -1 para aleatório).")
    args = parser.parse_args()

    if args.seed is not None and args.seed >= 0:
        random.seed(args.seed)

    if not os.path.exists(INPUT_FILE):
        print(f"Erro: arquivo de entrada '{INPUT_FILE}' não encontrado. Execute a partir de src/.")
        sys.exit(1)

    workflows = {wf["workflow_id"]: wf for wf in load_workflows(INPUT_FILE)}
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = 0
    for wid in args.fx:
        if wid not in workflows:
            print(f"  (ignorado, não está no definition) {wid}"); continue
        generate_one(workflows[wid], OUTPUT_DIR, task_type=1, suffix="")
        generated += 1
    for wid in args.vmonly:
        if wid not in workflows:
            print(f"  (ignorado, não está no definition) {wid}"); continue
        generate_one(workflows[wid], OUTPUT_DIR, task_type=0, suffix="_VMonly")
        generated += 1
    for wid in args.extra_fx:
        if wid not in workflows:
            print(f"  (ignorado, não está no definition) {wid}"); continue
        generate_one(workflows[wid], OUTPUT_DIR, task_type=1, suffix="")
        generated += 1

    print(f"\nTotal gerado: {generated} arquivo(s) em {OUTPUT_DIR}.")
    if args.seed is not None and args.seed >= 0:
        print(f"(seed={args.seed} — regenerável de forma idêntica)")


if __name__ == "__main__":
    main()