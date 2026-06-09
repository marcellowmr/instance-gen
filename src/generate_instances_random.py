#!/usr/bin/env python3
"""
Gera uma instância sintética com topologia de DAG aleatória.
"""

import os
from pathlib import Path

from model.workflow_generator_random import WorkflowGeneratorRandom
from instances_cm_tm_updates import update_file_bounds

# ==========================================
# PARÂMETROS
# ==========================================
OUTPUT_DIR = "data/synthetic/random"

NUM_TASKS = 6
NUM_DATA_ARTIFACTS = 8
NUM_VMS = 2
NUM_CONFIGS = 2
NUM_BUCKET_RANGES = 3
USE_INTEGER_TIME = True
FX_SLOWDOWN_MIN = 3.0
FX_SLOWDOWN_MAX = 10.0


def resolve_output_path(output_dir, num_tasks, num_configs, num_data, num_vms):
    """Retorna o caminho do arquivo, adicionando sufixo sequencial em caso de colisão."""
    def make_name(suffix=""):
        instance_id = num_tasks + num_data
        suffix_str = f"_{suffix:03d}" if suffix else ""
        return f"Synthetic_{instance_id:03d}_T{num_tasks}_C{num_configs}_D{num_data}_VM{num_vms}{suffix_str}.txt"

    name = make_name()
    seq = 2
    while os.path.exists(os.path.join(output_dir, name)):
        name = make_name(suffix=seq)
        seq += 1
    return os.path.join(output_dir, name)


def main():
    generator = WorkflowGeneratorRandom(
        num_tasks=NUM_TASKS,
        num_data=NUM_DATA_ARTIFACTS,
        num_vms=NUM_VMS,
        num_configs=NUM_CONFIGS,
        num_bucket_ranges=NUM_BUCKET_RANGES,
        use_integer_time=USE_INTEGER_TIME,
        fx_slowdown_min=FX_SLOWDOWN_MIN,
        fx_slowdown_max=FX_SLOWDOWN_MAX,
    )
    content = generator.generate_workflow_file_content()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = resolve_output_path(OUTPUT_DIR, generator.num_tasks, generator.num_configs, generator.num_data, generator.num_vms)
    with open(output_path, "w") as f:
        f.write(content)
    update_file_bounds(Path(output_path))
    print(f"Gerado: {output_path}  T={generator.num_tasks} C={generator.num_configs} D={generator.num_data} VM={generator.num_vms}")


if __name__ == "__main__":
    main()
