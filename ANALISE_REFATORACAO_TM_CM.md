# Análise e Proposta de Refatoração TM/CM

## Status Atual

### 3 Implementações Existentes

| Arquivo | Propósito | Tipo | Problema |
|---------|-----------|------|---------|
| `instances_cm_tm_updates_pessimista.py` | Cálculo TM/CM pessimista (pior caso sequencial) | Script CLI | Gera valores **MUITO ALTOS** → CPLEX não consegue lidar |
| `tm_cm_resource_aware.py` | Cálculo TM/CM inteligente (list scheduling) | **Biblioteca** | ✅ Correto, mas está em `src/` em vez de `src/core/` |
| `instances_cm_tm_updates_resource_aware.py` | CLI p/ atualizar instâncias | Wrapper | ❌ Duplica código de v1 com funções prefixadas `_` |

---

## Análise Comparativa: Resource-Aware v1 vs v2

### Estrutura Atual

```
tm_cm_resource_aware.py (194 linhas)
├── Parsing: parse_instance(), _parse_int_list(), _parse_value()
├── Lógica: worst_vm_duration(), worst_fx_duration(), task_durations()
├── Escalonamento: list_schedule(), predecessors(), tm_sequential()
├── Custos: per_task_max_cost()
└── API: compute_bounds() → retorna {"tm_final", "cm_final", ...}

instances_cm_tm_updates_resource_aware.py (281 linhas)
├── Parsing: parse_instance_data() [DUPLICA v1]
├── Lógica: _worst_vm_duration(), _worst_fx_duration(), _task_durations() [DUPLICA v1]
├── Escalonamento: _list_schedule(), _predecessors() [DUPLICA v1]
├── Custos: _per_task_max_cost() [DUPLICA v1]
├── Wrapper: calculate_tm_cm(), update_file_bounds()
└── CLI: main()
```

### Duplicação Exata

As funções são **idênticas em lógica**, apenas com nomes diferentes:

| v1 (público) | v2 (privado) | Diferença |
|-------------|------------|-----------|
| `worst_vm_duration()` | `_worst_vm_duration()` | Nenhuma |
| `worst_fx_duration()` | `_worst_fx_duration()` | Nenhuma |
| `task_durations()` | `_task_durations()` | Nenhuma |
| `list_schedule()` | `_list_schedule()` | Nenhuma |
| `predecessors()` | `_predecessors()` | Nenhuma |
| `per_task_max_cost()` | `_per_task_max_cost()` | Nenhuma |
| `parse_instance()` | `parse_instance_data()` | Parâmetros: `path` vs `lines` |

---

## Validação da Lógica (sua explicação)

✅ **CORRETO**. O código implementa:

### Tipo 1 (VM/FX flexível)
```python
if t['type'] == 1:
    dur_assigned[t['id']] = d_fx          # FX com paralelismo máximo ilimitado ✓
    dur_worst[t['id']] = max(d_vm, d_fx)  # Pior caso: max(VM, FX) ✓
```

### Tipo 0 (exclusiva de VM)
```python
else:
    dur_assigned[t['id']] = d_vm          # Sempre VM ✓
    dur_worst[t['id']] = d_vm
```

### CM (dual do TM)
```python
# Tipo 1: max(custos FX configs, custos VMs)
if task['type'] == 1:
    for fx in inst['fx'].get(task['id'], []):
        costs.append(fx['cost'])  # Config FX ✓
    # ... depois adiciona custos de VMs
    for vm in inst['vms']:
        costs.append(dur * vm['costPerSecond'])  # VMs ✓
    return max(costs)

# Tipo 0: custo VM ligada do início ao fim
vm_costs_desc = sorted((vm['costPerSecond'] for vm in inst['vms']), reverse=True)
cm_vm_idle = sum(vm_costs_desc[:n_vm_type0]) * tm_ls  # Sigma VMs usadas * TM ✓
```

---

## Proposta de Refatoração

### Objetivo
- ✅ Eliminar duplicação
- ✅ Mover lógica para `src/core/` (biblioteca)
- ✅ Manter apenas wrapper leve em `src/`

### Estrutura Proposta

```
src/core/tm_cm_resource_aware.py (NOVO)
├── Parsing genérico
├── Lógica de cálculo
├── List scheduling
└── API: compute_bounds()

src/instances_cm_tm_updates_resource_aware.py (REFATORADO)
├── import from core
├── wrapper: update_file_bounds()
└── CLI: main()
```

### Passos

1. **Copiar** `src/tm_cm_resource_aware.py` → `src/core/tm_cm_resource_aware.py`
   - Manter como biblioteca pública (sem underscore)
   - Sem mudanças na lógica

2. **Refatorar** `src/instances_cm_tm_updates_resource_aware.py`
   - Remover funções duplicadas
   - Importar de `core.tm_cm_resource_aware`
   - Manter apenas: `parse_instance_data()`, `update_file_bounds()`, `main()`

3. **Deletar** `src/tm_cm_resource_aware.py` (original) — copiado para core

4. **Verificar** imports em:
   - `generate_instances_random.py`
   - `generate_instances_user.py`
   - `generate_instances_mermaid.py`
   - Qualquer outro que use TM/CM

---

## Benefícios

| Benefício | Impacto |
|-----------|--------|
| Sem duplicação | Manutenção centralizada |
| Biblioteca clara | Fácil reutilizar em novos scripts |
| CLI desacoplado | Poder usar lógica sem CLI |
| Compatível com pessimista | Poder comparar estratégias lado a lado |

---

## Próximos Passos (Implementação)

1. Criar `src/core/tm_cm_resource_aware.py`
2. Refatorar `src/instances_cm_tm_updates_resource_aware.py`
3. Verificar e atualizar imports
4. Remover original `src/tm_cm_resource_aware.py`
5. Testar atualização de instâncias
