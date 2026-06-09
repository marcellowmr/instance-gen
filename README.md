# instance-gen

Gerador de instâncias sintéticas para o problema de escalonamento de workflows híbridos (VM + FX/serverless). As instâncias descrevem um DAG de tarefas, artefatos de dados, máquinas virtuais disponíveis, perfis de execução serverless e faixas de custo de bucket.

O formato completo das instâncias está documentado em [docs/instance_format.md](docs/instance_format.md).

---

## Geração de instâncias

Execute os scripts a partir do diretório `src/`.

### Modo user — topologia definida manualmente

Gera instâncias a partir de workflows descritos em `data/instances_definition.txt`.

```bash
cd src

# Gera os workflows listados em DEFAULT_WORKFLOW_IDS (configurado no topo do script)
python generate_instances_user.py

# Ou passa os IDs diretamente
python generate_instances_user.py Synthetic_011 Synthetic_030
```

Os arquivos são salvos em `data/synthetic/user/`.

### Modo random — topologia aleatória

Gera uma instância com DAG criado aleatoriamente a cada execução.

```bash
cd src
python generate_instances_random.py
```

Os arquivos são salvos em `data/synthetic/random/` com nome sequencial automático.

---

## Parâmetros

Os parâmetros de cada modo ficam no topo do respectivo script e podem ser editados diretamente:

| Parâmetro          | Descrição                                                       |
| ------------------ | --------------------------------------------------------------- |
| `NUM_VMS`          | Número de VMs incluídas na instância (máx. 5)                   |
| `NUM_CONFIGS`      | Número de configurações FX por tarefa                           |
| `USE_INTEGER_TIME` | Usa tempos inteiros (facilita leitura e depuração)              |
| `FX_SLOWDOWN_MIN`  | Fator mínimo de lentidão do FX em relação à VM base             |
| `FX_SLOWDOWN_MAX`  | Fator máximo de lentidão do FX em relação à VM base             |

O script `generate_user.py` ainda expõe `TASK_ID_OFFSET` / `DATA_ID_OFFSET` para renomear IDs ao escrever o arquivo final.

Após gerar cada arquivo, ambos os scripts recalculam automaticamente os limites `max_running_time` (TM) e `max_financial_cost` (CM) no cabeçalho da instância.

---

## Definindo topologias (modo user)

Edite `data/instances_definition.txt`. Cada bloco descreve um workflow:

```text
WORKFLOW_ID: Synthetic_007
TASKS: 3
DATA: 4
PATTERN: Map, Split
COMMENT:
---
t0: d0 -> d1
t1: d1 -> d2
t2: d1 -> d3
```

As linhas após `---` seguem o padrão `task_id: [inputs] -> [outputs]`. As dependências do DAG são implícitas: uma tarefa só pode executar quando todos os seus dados de entrada estiverem disponíveis.

---

## Recalcular limites TM/CM em instâncias existentes

```bash
cd src

python instances_cm_tm_updates.py --instances-dir ../data/synthetic/user
python instances_cm_tm_updates.py --instances-dir ../data/synthetic/user --patterns "Synthetic_030*.txt"
```

---

## Formato das instâncias

Veja [docs/instance_format.md](docs/instance_format.md) para a especificação completa das 6 seções do arquivo `.txt`, incluindo convenção de nomenclatura e semântica de cada campo.
