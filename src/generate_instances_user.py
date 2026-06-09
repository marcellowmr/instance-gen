#!/usr/bin/env python3
"""
Gera instâncias sintéticas a partir de topologias definidas em data/instances_definition.txt.
"""

import os
import re
import sys
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

# IDs dos workflows a gerar. Usado quando nenhum argumento é passado via CLI.
DEFAULT_WORKFLOW_IDS = ["Synthetic_030"]

NUM_VMS = 2
NUM_CONFIGS = 2
NUM_BUCKET_RANGES = 3
USE_INTEGER_TIME = True
FX_SLOWDOWN_MIN = 3.0
FX_SLOWDOWN_MAX = 10.0

TASK_PREFIX_REPLACE = {"old": "t", "new": ""}
DATA_PREFIX_REPLACE = {"old": "d", "new": ""}
TASK_ID_OFFSET = 100
DATA_ID_OFFSET = 900


def build_filename(base_id, num_tasks, num_configs, num_data, num_vms):
    match = re.search(r"\d+", str(base_id))
    num_id = int(match.group(0)) if match else 0
    return f"Synthetic_{num_id:03d}_T{num_tasks}_C{num_configs}_D{num_data}_VM{num_vms}.txt"


def main():
    parser = argparse.ArgumentParser(description="Gera instâncias sintéticas a partir de topologias definidas pelo usuário.")
    parser.add_argument("workflows", nargs="*", default=DEFAULT_WORKFLOW_IDS,
                        help="IDs dos workflows a gerar (ex: Synthetic_011 Synthetic_012). Padrão: " + str(DEFAULT_WORKFLOW_IDS))
    args = parser.parse_args()
    target_ids = args.workflows

    if not os.path.exists(INPUT_FILE):
        print(f"Erro: arquivo de entrada '{INPUT_FILE}' não encontrado. Execute a partir de src/.")
        sys.exit(1)

    workflows = load_workflows(INPUT_FILE)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = 0
    for wf in workflows:
        if wf["workflow_id"] not in target_ids:
            continue

        generator = WorkflowGeneratorUser(
            workflow_id=wf["workflow_id"],
            num_tasks=wf["num_tasks"],
            num_data=wf["num_data"],
            task_defs=wf["task_defs"],
            output_dir=OUTPUT_DIR,
            num_vms=NUM_VMS,
            num_configs=NUM_CONFIGS,
            num_bucket_ranges=NUM_BUCKET_RANGES,
            use_integer_time=USE_INTEGER_TIME,
            task_prefix_replace=TASK_PREFIX_REPLACE,
            data_prefix_replace=DATA_PREFIX_REPLACE,
            task_id_offset=TASK_ID_OFFSET,
            data_id_offset=DATA_ID_OFFSET,
            fx_slowdown_min=FX_SLOWDOWN_MIN,
            fx_slowdown_max=FX_SLOWDOWN_MAX,
        )
        content = generator.generate_workflow_file_content()
        file_name = build_filename(wf["workflow_id"], generator.num_tasks, generator.num_configs, generator.num_data, generator.num_vms)
        output_path = os.path.join(OUTPUT_DIR, file_name)

        with open(output_path, "w") as f:
            f.write(content)
        update_file_bounds(Path(output_path))
        print(f"Gerado: {output_path}  T={generator.num_tasks} C={generator.num_configs} D={generator.num_data} VM={generator.num_vms}")
        generated += 1

    if generated == 0:
        available = [wf["workflow_id"] for wf in workflows]
        print(f"Nenhum workflow gerado. IDs solicitados: {target_ids}")
        print(f"IDs disponíveis em '{INPUT_FILE}': {available}")
    else:
        print(f"\nTotal gerado: {generated} arquivo(s).")


if __name__ == "__main__":
    main()
