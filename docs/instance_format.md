# Formato dos Arquivos de Instância

Os arquivos de instância (`.txt`) descrevem o problema de escalonamento que o Stratus deve resolver. Cada arquivo define um workflow (DAG), os recursos disponíveis e os limites do problema.

## Convenção de Nomenclatura

```text
{Prefixo}_{NNN}_T{tasks}_C{configs}_D{data}_VM{vms}.txt
```

| Prefixo           | Significado                                              |
| ----------------- | -------------------------------------------------------- |
| `I{NNN}`          | Instância real derivada do benchmark DENETHOR            |
| `Synthetic_{NNN}` | Instância sintética criada manualmente                   |
| `INVALID_…`       | Instância intencionalmente corrompida (testes negativos) |

Exemplo: `Synthetic_007_T3_C2_D4_VM2.txt` → 3 tarefas, 2 configs FX, 4 dados, 2 VMs.

---

## Estrutura Geral

O arquivo é dividido em **6 seções**, cada uma iniciada por uma linha de comentário `#...`. Linhas em branco entre seções são ignoradas.

```text
Seção 1 — Metadados Gerais
Seção 2 — Tarefas (nós do DAG)
Seção 3 — Artefatos de Dados
Seção 4 — Máquinas Virtuais (VMs)
Seção 5 — Perfis de Execução FX (matriz nTasks × nConfigs)
Seção 6 — Faixas de Custo do Bucket
```

---

## Seção 1 — Metadados Gerais

```text
#<#tasks> <#config> <#data> <#vms> <#buckets> <#bucket_ranges> <max_running_time> <max_financial_cost>
3  2  4  2  1  3  34.0000  0.0042266060
```

| Campo                | Tipo     | Descrição                                                   |
| -------------------- | -------- | ----------------------------------------------------------- |
| `#tasks`             | `int`    | Número de tarefas no workflow                               |
| `#config`            | `int`    | Número de configurações FX (níveis de memória serverless)   |
| `#data`              | `int`    | Número de artefatos de dados                                |
| `#vms`               | `int`    | Número de máquinas virtuais disponíveis                     |
| `#buckets`           | `int`    | Número de buckets de armazenamento (atualmente sempre `1`)  |
| `#bucket_ranges`     | `int`    | Número de faixas de preço do bucket (atualmente sempre `3`) |
| `max_running_time`   | `double` | Limite superior de makespan (TM), em segundos               |
| `max_financial_cost` | `double` | Limite superior de custo financeiro (CM), em USD            |

> **Nota:** `max_running_time` e `max_financial_cost` são usados como normalizadores da função objetivo. Valores muito baixos podem tornar a instância inviável.

---

## Seção 2 — Tarefas (nós do DAG)

```text
#<task_id> <activity_id> <task_type__0-VM__1-VM_FX> <vm_cpu_time> <n_input> [<id_input>...] <n_output> [<id_output>...]
10  1  1  3.0000  1  [90]  1  [91]
11  1  1  4.0000  1  [91]  1  [92]
12  2  1  1.0000  1  [91]  1  [93]
```

| Campo         | Tipo     | Descrição                                                                          |
| ------------- | -------- | ---------------------------------------------------------------------------------- |
| `task_id`     | `int`    | Identificador único da tarefa                                                      |
| `activity_id` | `int`    | Grupo funcional ao qual a tarefa pertence (agrupa réplicas de uma mesma atividade) |
| `task_type`   | `int`    | `0` = executa somente em VM; `1` = pode executar em VM ou FX                       |
| `vm_cpu_time` | `double` | Tempo de CPU base da tarefa em uma VM de slowdown 1.0, em segundos                 |
| `n_input`     | `int`    | Número de dados de entrada                                                         |
| `[id_input]`  | lista    | IDs dos dados de entrada, entre colchetes e separados por vírgula                  |
| `n_output`    | `int`    | Número de dados de saída                                                           |
| `[id_output]` | lista    | IDs dos dados de saída, entre colchetes e separados por vírgula                    |

As dependências do DAG são implícitas: uma tarefa só pode ser executada após todos os dados de entrada estarem disponíveis, ou seja, após todas as tarefas que produzem esses dados terem concluído.

---

## Seção 3 — Artefatos de Dados

```text
#<data_id> <data_size_bytes> <read_time_avg> <write_time_avg> <is_static> <n_source_devices> [<device_id>...]
90   111  2.0000  None  1  1  [denethor_bucket]
91  1033  2.0000  3.0000  0  0  [denethor_bucket]
```

| Campo              | Tipo               | Descrição                                                                                     |
| ------------------ | ------------------ | --------------------------------------------------------------------------------------------- |
| `data_id`          | `int`              | Identificador único do artefato de dado                                                       |
| `data_size_bytes`  | `int`              | Tamanho do dado em bytes                                                                      |
| `read_time_avg`    | `double` ou `None` | Tempo médio de leitura desse dado do bucket, em segundos. `None` se não aplicável             |
| `write_time_avg`   | `double` ou `None` | Tempo médio de escrita desse dado no bucket, em segundos. `None` se não aplicável             |
| `is_static`        | `int`              | `1` = dado pré-existente no bucket (arquivo de entrada do workflow); `0` = gerado em execução |
| `n_source_devices` | `int`              | Número de dispositivos de origem (geralmente `1` para estáticos, `0` para gerados)            |
| `[device_id]`      | lista              | Identificador do bucket de origem (ex.: `[denethor_bucket]`)                                  |

### Regras

- Dados `is_static = 1` já estão disponíveis no início da execução e tipicamente têm `write_time_avg = None`.
- O loader trata `None` como `0.0` internamente.

---

## Seção 4 — Máquinas Virtuais (VMs)

```text
#<vm_id> <cpu_slowdown> <cost_per_second> <storage_bytes> <bandwidth_mbps>
1  1.00000  0.0000051670  8589934592  1250
3  0.25000  0.0000826720  8589934592  5000
```

| Campo             | Tipo          | Descrição                                                                                                      |
| ----------------- | ------------- | -------------------------------------------------------------------------------------------------------------- |
| `vm_id`           | `int`         | Identificador único da VM                                                                                      |
| `cpu_slowdown`    | `double`      | Fator multiplicativo sobre `vm_cpu_time`. Slowdown menor = VM mais rápida. VM de referência tem slowdown `1.0` |
| `cost_per_second` | `long double` | Custo de manter a VM ativa por segundo, em USD                                                                 |
| `storage_bytes`   | `long long`   | Capacidade de armazenamento local da VM, em bytes                                                              |
| `bandwidth_mbps`  | `int`         | Largura de banda de rede da VM, em Mbps                                                                        |

O tempo efetivo de CPU de uma tarefa em uma VM é `vm_cpu_time × cpu_slowdown`.

---

## Seção 5 — Perfis de Execução FX (nTasks × nConfigs linhas)

Esta seção define o desempenho de cada tarefa em cada configuração de memória serverless (FX). Há exatamente `nTasks × nConfigs` linhas, ordenadas por tarefa e depois por configuração.

```text
#<task_id> <activity_id> <conf_id> <task_cost> <task_time_duration> <task_time_init> <task_time_cpu> <task_time_read> <task_time_write> <task_count>
10  1  1  0.0000200000  13.000  0.0000  8.0000  2.0000  3.0000  1
10  1  2  0.0000465911   8.8512  0.0000  3.8512  2.0000  3.0000  4
11  1  1  0.0000400000  15.000  0.0000  12.0000  2.0000  1.0000  1
```

| Campo                | Tipo          | Descrição                                                             |
| -------------------- | ------------- | --------------------------------------------------------------------- |
| `task_id`            | `int`         | ID da tarefa (deve existir na Seção 2)                                |
| `activity_id`        | `int`         | Grupo funcional da tarefa                                             |
| `conf_id`            | `int`         | ID da configuração FX (de `1` a `nConfigs`)                           |
| `task_cost`          | `long double` | Custo financeiro estimado da execução nessa configuração, em USD      |
| `task_time_duration` | `double`      | Duração total observada na execução, em segundos (ver nota abaixo)    |
| `task_time_init`     | `double`      | Tempo de inicialização da função serverless (cold start), em segundos |
| `task_time_cpu`      | `double`      | Tempo de CPU puro da tarefa nessa configuração, em segundos           |
| `task_time_read`     | `double`      | Tempo total de leitura dos dados de entrada, em segundos              |
| `task_time_write`    | `double`      | Tempo total de escrita dos dados de saída, em segundos                |
| `task_count`         | `int`         | Número de invocações paralelas usadas para gerar essas métricas       |

### Cálculo de Duração Usado pelo Solver

O campo `task_time_duration` do arquivo **não é usado diretamente**. O loader recalcula a duração efetiva considerando que em ambiente FX as operações de I/O são paralelizadas entre invocações:

```text
fx_duration = max(1.0, t_init + t_cpu + max(read_time dos inputs) + max(write_time dos outputs))
```

Esse valor recalculado substitui `task_time_duration` no `ExecutionProfile` armazenado na tarefa.

---

## Seção 6 — Faixas de Custo do Bucket

```text
#<bucket_range_id> <size1_bytes> <size2_bytes> <cost_per_byte>
1  0                    54975581388800   0.0000000000377185642719268799
2  54975581388800      494780232499200   0.0000000000363215804100036621
3  494780232499200  107374182399998...   0.0000000000344589352607727051
```

| Campo             | Tipo     | Descrição                                         |
| ----------------- | -------- | ------------------------------------------------- |
| `bucket_range_id` | `int`    | ID sequencial da faixa (começa em `1`)            |
| `size1_bytes`     | `double` | Limite inferior do intervalo de tamanho, em bytes |
| `size2_bytes`     | `double` | Limite superior do intervalo de tamanho, em bytes |
| `cost_per_byte`   | `float`  | Custo por byte armazenado nessa faixa, em USD     |

As faixas são mutuamente exclusivas e cobrem todo o espaço de tamanho possível. Instâncias reais da DENETHOR expressam essas faixas em GB com custo por GB; instâncias sintéticas usam bytes com custo por byte.

---

## Exemplo Completo Anotado

O arquivo `instances/synthetic/Synthetic_007_T3_C2_D4_VM2.txt` é a instância de referência dos testes. Representa um workflow linear simples:

```text
[90] → task10(act=1) → [91] → task11(act=1) → [92]
                         ↓
                      task12(act=2) → [93]
```

- Dado `90` é estático (pré-existente no bucket, `is_static=1`).
- `task10` e `task11` são réplicas de activity `1`; `task12` pertence a activity `2`.
- Todas as tarefas suportam execução em VM ou FX (`task_type=1`).
- Há 2 VMs (IDs 1 e 3) com velocidades muito diferentes (slowdown 1.0 vs 0.25).
- Cada tarefa tem 2 perfis FX (conf_id 1 e 2).

---

## Notas de Implementação

- O loader lê as seções na ordem fixa acima; qualquer desvio resulta em `runtime_error`.
- As tarefas da Seção 2 são armazenadas temporariamente e populadas com objetos `Data` completos apenas após a leitura da Seção 3.
- O campo `[device_id]` inclui os colchetes como parte do valor armazenado (ex.: `"[denethor_bucket]"`).
- O número de perfis de uma tarefa após o carregamento sempre iguala `nConfigs`.
- Referências de código: [`src/core/InstanceLoader.cpp`](../src/core/InstanceLoader.cpp), [`tests/loading_tests/synthetic/`](../tests/loading_tests/synthetic/).
