#!/usr/bin/env python3
"""
Calculador de TM/CM "resource-aware" que opera sobre arquivos de instancia .txt ja gerados.

INTUICAO (TM_listsched):
    O TM_listsched estima o makespan do escalonamento mais barato -- tudo em FX na config
    mais lenta/barata, com paralelismo maximo. Por isso ele acompanha POR CIMA o makespan da
    solucao de foco em custo, e a aproximacao e mais apertada justamente em workflows muito
    paralelos e I/O-bound, onde o FX de fato vence a VM. Usar TM_listsched * (1 + margem) da
    a folga necessaria para nao truncar o otimo de custo (alpha baixo).

INTUICAO (CM) -- a regra e o DUAL do TM:
    O TM amarra no extremo de CUSTO (alpha baixo, solucao lenta) -> usa o recurso mais lento.
    O CM amarra no extremo de TEMPO (alpha alto, solucao cara)   -> usa o recurso mais CARO.
    Por isso, para tarefas tipo 1, o custo por tarefa e o MAXIMO entre configs FX e VMs
    (nao so o FX barato, que subdimensionaria o limite). Tarefas tipo 0 sao cobradas como
    VM ligada do inicio ao fim do workflow (Sigma_VMs_usadas custo/s * TM).

NOTA sobre piso de tempo: instancias sinteticas usam tempo inteiro (piso 1.0); reais usam
    segundos continuos (sub-1, piso 0.0). O piso e aplicado so no TOTAL da duracao, nunca por
    termo de I/O (isso era um bug que inflava as reais).
"""

from pathlib import Path


# ---------- parsing ----------

def _parse_int_list(s):
    s = s.strip().strip('[]')
    return [int(x) for x in s.split(',')] if s else []

def _parse_value(s):
    s = s.strip()
    return 0.0 if s == 'None' else float(s)

def parse_instance(path):
    lines = [l.strip() for l in Path(path).read_text(encoding='utf-8').splitlines()
             if l.strip() and not l.strip().startswith('#')]
    idx = 0
    p = lines[idx].split(); idx += 1
    nTasks, nConfigs, nData, nVMs = int(p[0]), int(p[1]), int(p[2]), int(p[3])

    tasks = []
    for _ in range(nTasks):
        p = lines[idx].split(); idx += 1
        tasks.append({'id': int(p[0]), 'type': int(p[2]), 'vmCpuTime': float(p[3]),
                      'inputs': _parse_int_list(p[5]), 'outputs': _parse_int_list(p[7])})

    data_map = {}
    for _ in range(nData):
        p = lines[idx].split(); idx += 1
        data_map[int(p[0])] = {'readTime': _parse_value(p[2]), 'writeTime': _parse_value(p[3])}

    vms = []
    for _ in range(nVMs):
        p = lines[idx].split(); idx += 1
        vms.append({'slowdown': float(p[1]), 'costPerSecond': float(p[2])})

    fx_configs = {}
    for _ in range(nTasks * nConfigs):
        p = lines[idx].split(); idx += 1
        fx_configs.setdefault(int(p[0]), []).append(
            {'cost': float(p[3]), 'timeInit': float(p[5]), 'timeCpu': float(p[6])})

    return {'nVMs': nVMs, 'tasks': tasks, 'data_map': data_map, 'vms': vms, 'fx': fx_configs}


def detect_time_floor(inst):
    """1.0 se todos os tempos sao inteiros (sintetica); 0.0 se ha tempo continuo (real)."""
    vals = [t['vmCpuTime'] for t in inst['tasks']]
    vals += [d['readTime'] for d in inst['data_map'].values()]
    vals += [d['writeTime'] for d in inst['data_map'].values()]
    vals += [fx['timeInit'] for cfgs in inst['fx'].values() for fx in cfgs]
    vals += [fx['timeCpu'] for cfgs in inst['fx'].values() for fx in cfgs]
    for v in vals:
        if abs(v - round(v)) > 1e-9:
            return 0.0
    return 1.0


# ---------- duracoes por tarefa (piso so no total) ----------

def worst_vm_duration(task, data_map, vms, floor):
    io_read = sum(data_map[d]['readTime'] for d in task['inputs'])      # VM le em serie
    io_write = sum(data_map[d]['writeTime'] for d in task['outputs'])
    best = 0.0
    for vm in vms:
        cpu = task['vmCpuTime'] * vm['slowdown']
        best = max(best, max(floor, cpu + io_read + io_write))
    return best

def worst_fx_duration(task, data_map, fx_configs, floor):
    io_read = max((data_map[d]['readTime'] for d in task['inputs']), default=0.0)   # FX paraleliza I/O
    io_write = max((data_map[d]['writeTime'] for d in task['outputs']), default=0.0)
    best = 0.0
    for fx in fx_configs.get(task['id'], []):
        best = max(best, max(floor, fx['timeInit'] + fx['timeCpu'] + io_read + io_write))
    return best

def task_durations(inst, floor):
    dur_assigned, dur_worst, fx_eligible = {}, {}, {}
    for t in inst['tasks']:
        d_vm = worst_vm_duration(t, inst['data_map'], inst['vms'], floor)
        d_fx = worst_fx_duration(t, inst['data_map'], inst['fx'], floor)
        if t['type'] == 1:
            fx_eligible[t['id']] = True
            dur_assigned[t['id']] = d_fx          # tipo 1 -> FX (paralelo)
            dur_worst[t['id']] = max(d_vm, d_fx)
        else:
            fx_eligible[t['id']] = False
            dur_assigned[t['id']] = d_vm          # tipo 0 -> VM (limitado)
            dur_worst[t['id']] = d_vm
    return dur_assigned, dur_worst, fx_eligible


# ---------- grafo e escalonamento ----------

def predecessors(tasks):
    producer = {}
    for t in tasks:
        for o in t['outputs']:
            producer[o] = t['id']
    preds = {t['id']: set() for t in tasks}
    for t in tasks:
        for i in t['inputs']:
            if i in producer:
                preds[t['id']].add(producer[i])
    return preds

def tm_sequential(dur_worst):
    return sum(dur_worst.values())

def list_schedule(tasks, dur_assigned, fx_eligible, num_vms):
    """Makespan de escalonamento viavel (FX ilimitado, VM <= num_vms). Retorna (makespan, n_vms_tipo0)."""
    preds = predecessors(tasks)
    finish = {}
    vm_free = [0.0] * num_vms
    vm_used = set()
    remaining = {t['id'] for t in tasks}
    done = set()
    while remaining:
        ready = [tid for tid in remaining if preds[tid] <= done]
        rt = lambda tid: max([finish[p] for p in preds[tid]], default=0.0)
        ready.sort(key=rt)
        tid = ready[0]; r = rt(tid)
        if fx_eligible[tid]:
            finish[tid] = r + dur_assigned[tid]
        else:
            j = min(range(num_vms), key=lambda k: vm_free[k])
            start = max(r, vm_free[j])
            finish[tid] = start + dur_assigned[tid]
            vm_free[j] = finish[tid]; vm_used.add(j)
        done.add(tid); remaining.discard(tid)
    return max(finish.values()), len(vm_used)


# ---------- CM (dual do TM) ----------

def per_task_max_cost(task, inst, floor):
    """Custo do recurso MAIS CARO permitido (tipo1: FX configs + VMs; tipo0: VMs)."""
    costs = []
    if task['type'] == 1:
        for fx in inst['fx'].get(task['id'], []):
            costs.append(fx['cost'])
    io_read = sum(inst['data_map'][d]['readTime'] for d in task['inputs'])
    io_write = sum(inst['data_map'][d]['writeTime'] for d in task['outputs'])
    for vm in inst['vms']:
        dur = max(floor, task['vmCpuTime'] * vm['slowdown'] + io_read + io_write)
        costs.append(dur * vm['costPerSecond'])
    return max(costs) if costs else 0.0


# ---------- API ----------

def compute_bounds(path, margin=0.25, num_vms_override=None):
    inst = parse_instance(path)
    floor = detect_time_floor(inst)
    nv = num_vms_override or inst['nVMs']
    da, dw, el = task_durations(inst, floor)

    tm_seq = tm_sequential(dw)
    tm_ls, n_vm_type0 = list_schedule(inst['tasks'], da, el, nv)
    tm_final = tm_ls * (1.0 + margin)

    # CM: tipo1 -> max(FX,VM) por tarefa; tipo0 -> VM ligada do inicio ao fim (Sigma VMs usadas * TM_ls)
    cm_tasks = sum(per_task_max_cost(t, inst, floor) for t in inst['tasks'] if t['type'] == 1)
    vm_costs_desc = sorted((vm['costPerSecond'] for vm in inst['vms']), reverse=True)
    cm_vm_idle = sum(vm_costs_desc[:n_vm_type0]) * tm_ls
    cm_final = (cm_tasks + cm_vm_idle) * (1.0 + margin)

    return {'n_tasks': len(inst['tasks']), 'n_vms': inst['nVMs'], 'floor': floor,
            'tm_seq': tm_seq, 'tm_ls': tm_ls, 'tm_final': tm_final,
            'cm_tasks': cm_tasks, 'cm_vm_idle': cm_vm_idle, 'cm_final': cm_final}
