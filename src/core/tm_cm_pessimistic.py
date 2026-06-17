#!/usr/bin/env python3
"""
Calculador de TM/CM "pessimista" (pior caso sequencial) sobre arquivos de instancia .txt.

Esta e a implementacao SEGURA ORIGINAL: assume que cada tarefa leva sua pior duracao
possivel, que todas rodam em serie (sem DAG, sem paralelismo) e que TODAS as VMs ficam
ligadas ociosas do inicio ao fim do horizonte. Gera bounds garantidamente validos, porem
muito folgados -- o TM alto explode a expansao das variaveis binarias e o espaco de busca
do CPLEX. Mantida como referencia historica e opcao configuravel (--strategy pessimistic);
para resolver instancias use de preferencia a estrategia resource-aware.

REGRAS:
    TM (por tarefa) = max sobre todos os recursos permitidos:
        - VM: cpu*slowdown + I/O em SERIE (sum dos reads + sum dos writes);
        - FX: init + cpu + I/O em PARALELO (max dos reads, max dos writes).
      TM_total = SOMA das piores duracoes (escalonamento sequencial, sem DAG).

    CM = SOMA do custo do recurso mais caro por tarefa
       + ociosidade: TODAS as VMs ligadas durante todo o TM_total.

NOTA (piso de tempo): reaproveita detect_time_floor -- piso 1.0 para sinteticas (tempo
    inteiro), 0.0 para reais (segundos continuos). O piso aqui e aplicado por termo de I/O
    (comportamento da implementacao original), o que contribui para o carater pessimista.
"""

from core.tm_cm_resource_aware import parse_instance, detect_time_floor


# ---------- duracoes por tarefa (pior caso, piso por termo) ----------

def worst_task_duration(task, data_map, vms, fx_configs, floor):
    """Pior duracao da tarefa entre todas as VMs e todas as configs FX."""
    io_read_vm = sum(max(floor, data_map[d]['readTime']) for d in task['inputs'])    # VM le em serie
    io_write_vm = sum(max(floor, data_map[d]['writeTime']) for d in task['outputs'])

    io_read_fx = max((max(floor, data_map[d]['readTime']) for d in task['inputs']), default=0.0)
    io_write_fx = max((max(floor, data_map[d]['writeTime']) for d in task['outputs']), default=0.0)

    best = 0.0
    for vm in vms:
        cpu = max(floor, task['vmCpuTime'] * vm['slowdown'])
        best = max(best, max(floor, cpu + io_read_vm + io_write_vm))
    for fx in fx_configs.get(task['id'], []):
        best = max(best, max(floor, fx['timeInit'] + fx['timeCpu'] + io_read_fx + io_write_fx))
    return best


def worst_task_cost(task, data_map, vms, fx_configs, floor):
    """Custo do recurso mais caro permitido para a tarefa (VM com I/O serial ou config FX)."""
    io_read_vm = sum(max(floor, data_map[d]['readTime']) for d in task['inputs'])
    io_write_vm = sum(max(floor, data_map[d]['writeTime']) for d in task['outputs'])

    best = 0.0
    for vm in vms:
        cpu = max(floor, task['vmCpuTime'] * vm['slowdown'])
        dur = max(floor, cpu + io_read_vm + io_write_vm)
        best = max(best, dur * vm['costPerSecond'])
    for fx in fx_configs.get(task['id'], []):
        best = max(best, fx['cost'])
    return best


# ---------- API ----------

def compute_bounds(path, margin=0.0, num_vms_override=None):
    """Retorna dict com TM/CM pessimistas. margin default 0.0 (o bound ja e folgado)."""
    inst = parse_instance(path)
    floor = detect_time_floor(inst)
    vms = inst['vms']
    fx = inst['fx']
    data_map = inst['data_map']

    tm_raw = sum(worst_task_duration(t, data_map, vms, fx, floor) for t in inst['tasks'])
    base_cost = sum(worst_task_cost(t, data_map, vms, fx, floor) for t in inst['tasks'])
    idle_penalty = sum(vm['costPerSecond'] for vm in vms) * tm_raw   # todas as VMs ociosas o horizonte todo
    cm_raw = base_cost + idle_penalty

    tm_final = tm_raw * (1.0 + margin)
    cm_final = cm_raw * (1.0 + margin)

    return {'n_tasks': len(inst['tasks']), 'n_vms': inst['nVMs'], 'floor': floor,
            'tm_raw': tm_raw, 'tm_final': tm_final,
            'base_cost': base_cost, 'idle_penalty': idle_penalty, 'cm_final': cm_final}
