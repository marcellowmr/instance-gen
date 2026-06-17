# Guia de Uso: Módulo TM/CM Resource-Aware

## Localização
- **Biblioteca**: `src/core/tm_cm_resource_aware.py` (reutilizável)
- **Wrapper CLI**: `src/instances_cm_tm_updates_resource_aware.py`

## Uso como Biblioteca

```python
from pathlib import Path
from core.tm_cm_resource_aware import parse_instance, compute_bounds, detect_time_floor

# Opção 1: Usar parse_instance + compute_bounds (recomendado)
filepath = Path("../data/synthetic/cplex/Synthetic_007_T3_C2_D4_VM2.txt")
bounds = compute_bounds(filepath, margin=0.30, num_vms_override=None)

print(f"TM final: {bounds['tm_final']:.4f}")
print(f"CM final: {bounds['cm_final']:.10f}")
print(f"Detalhes: TM_seq={bounds['tm_seq']}, TM_listsched={bounds['tm_ls']}")

# Opção 2: Usar parse_instance para inspecionar estrutura
inst = parse_instance(filepath)
print(f"Tarefas: {len(inst['tasks'])}, VMs: {inst['nVMs']}")

floor = detect_time_floor(inst)
print(f"Tipo de instância (piso): {floor} (1.0=sintética, 0.0=real)")
```

## Uso via CLI

```bash
# Atualizar TM/CM de uma instância
cd src
python instances_cm_tm_updates_resource_aware.py \
    --instances-dir ../data/synthetic/user \
    --patterns "Synthetic_*.txt" \
    --margin 0.30 \
    --verbose

# Ou uma única instância
python instances_cm_tm_updates_resource_aware.py \
    --instances-dir ../data/synthetic/cplex \
    --patterns "Synthetic_007*.txt"
```

## Comparação: Pessimista vs Resource-Aware

Para comparar as duas estratégias em um arquivo:

```python
from pathlib import Path
from instances_cm_tm_updates_pessimista import update_file_bounds as update_pessimista
from core.tm_cm_resource_aware import compute_bounds

filepath = Path("../data/synthetic/cplex/Synthetic_007_T3_C2_D4_VM2.txt")

# Ler arquivo e fazer backup
import shutil
backup = Path(str(filepath) + ".backup")
shutil.copy(filepath, backup)

# Calcular com resource-aware
bounds_ra = compute_bounds(filepath, margin=0.30)
print(f"Resource-Aware: TM={bounds_ra['tm_final']:.4f}, CM={bounds_ra['cm_final']:.10f}")

# Restaurar e calcular com pessimista
shutil.copy(backup, filepath)
from instances_cm_tm_updates_pessimista import parse_instance_data
with open(filepath) as f:
    parsed = parse_instance_data(f.readlines())
from instances_cm_tm_updates_pessimista import calculate_tm_cm
tm_pess, cm_pess = calculate_tm_cm(parsed[0], parsed[1], parsed[2], parsed[3])
print(f"Pessimista:     TM={tm_pess:.4f}, CM={cm_pess:.10f}")

print(f"\nRedução TM:  {(1 - bounds_ra['tm_final']/tm_pess)*100:.1f}%")
print(f"Redução CM:  {(1 - bounds_ra['cm_final']/cm_pess)*100:.1f}%")
```

## Estrutura de compute_bounds() - Retorno

```python
{
    'n_tasks': int,              # número de tarefas
    'n_vms': int,                # número de VMs
    'floor': float,              # 1.0 (sintética) ou 0.0 (real)
    
    'tm_seq': float,             # TM sequencial (antigo, para comparação)
    'tm_ls': float,              # TM list scheduling
    'tm_final': float,           # TM com margem = tm_ls * (1 + margin)
    
    'cm_tasks': float,           # Custo das tarefas tipo 1
    'cm_vm_idle': float,         # Custo de ociosidade VM (tipo 0)
    'cm_final': float,           # CM com margem = (cm_tasks + cm_vm_idle) * (1 + margin)
}
```

## Importação em Novos Scripts

Se você quer usar a lógica de cálculo em outro script:

```python
# ❌ ERRADO - arquivo foi removido
from tm_cm_resource_aware import compute_bounds

# ✅ CORRETO - importar de core
from core.tm_cm_resource_aware import compute_bounds
```

## Notas Importantes

1. **Piso de tempo**: Detectado automaticamente
   - Sintéticas: piso 1.0 (tempo em unidades inteiras)
   - Reais: piso 0.0 (tempo em segundos contínuos)

2. **Tipo 0 vs Tipo 1**:
   - Tipo 1: Pode rodar em FX (ilimitado) ou VM
   - Tipo 0: Exclusiva de VM (limitada a num_vms)

3. **Margem**: Folga de segurança, padrão 30% (0.30)
   - Tipicamente 0.20-0.30 para problemas com CPLEX

4. **List Scheduling**: Heurística polinomial que estima makespan viável
   - Limite superior válido do ótimo
   - Mais apertado que pessimista para workflows paralelos

## Compatibilidade

| Função | Antes | Depois | Nota |
|--------|-------|--------|------|
| `parse_instance(path)` | ✓ | ✓ core | Compatível |
| `compute_bounds(path, margin)` | ✓ | ✓ core | Compatível |
| `update_file_bounds(path, margin)` | ✓ | ✓ wrapper | Compatível (CLI) |
| `detect_time_floor(inst)` | ✓ | ✓ core | Novo em core (antes privado) |
| Funções `_*` (privadas) | N/A | ✓ core | Internas (não usar) |
