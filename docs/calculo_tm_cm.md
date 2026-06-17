# Cálculo de `max_running_time` (TM) e `max_financial_cost` (CM)

Documento técnico sobre como os limites `max_running_time` (TM) e `max_financial_cost` (CM)
do cabeçalho (Seção 1) das instâncias são calculados: a primeira versão (pior caso sequencial),
os problemas que ela trouxe, e a proposta atual *resource-aware* com margem de segurança.

---

## 1. Papel de TM e CM no modelo

TM e CM cumprem **dois papéis simultâneos** no MILP time-indexed:

1. **Horizonte / limite das restrições.** O conjunto de instantes é $T = \{1, \dots, TM\}$ e o custo
   é restringido por CM. Para que o solver represente o ótimo, é obrigatório que:
   - $TM \ge z$, onde $z$ é o `makespan` da solução **ótima da função objetivo biobjetivo**;
   - $CM \ge$ custo da solução ótima.
   Se TM ou CM ficarem abaixo desses valores, o ótimo é **truncado** (cortado do espaço viável).

2. **Normalizador da função objetivo biobjetivo.** A função objetivo combina tempo e custo
   normalizados e ponderados por $\alpha$:

   $$FO = \alpha \cdot \frac{z}{TM} + (1-\alpha) \cdot \frac{\text{custo}}{CM}$$

Como o solver **minimiza a FO** (e não o `makespan` isoladamente), o ótimo varia ao longo da
fronteira de Pareto conforme $\alpha$:

- **$\alpha$ baixo (foco em custo):** o ótimo é a solução **mais lenta** (mais barata). É o `makespan`
  **máximo** que o solver produz — logo, é o ponto que **TM precisa cobrir**.
- **$\alpha$ alto (foco em tempo):** o ótimo é a solução **mais cara** (mais rápida). É o custo
  **máximo** que o solver produz — logo, é o ponto que **CM precisa cobrir**.

> **Observação fundamental:** TM amarra no extremo de **custo** (lento); CM amarra no extremo de
> **tempo** (caro). As duas réguas são **duais** — esse fato orienta toda a versão 2.

---

## 2. Versão 1 — pior caso sequencial

A primeira versão (`calculate_tm_cm`) calculava limites **conservadores** assumindo o pior cenário
absoluto: tudo executado em série, no recurso de pior desempenho.

### 2.1. TM v1

$$TM_{v1} = \sum_{i \in T} \max\Big( d_i^{\,vm,\text{pior}},\; d_i^{\,fx,\text{pior}} \Big)$$

onde, por tarefa $i$:

| Componente | Cálculo |
|---|---|
| Duração VM (pior) | $\;vm\_cpu\_time \cdot cpu\_slowdown \;+\; \sum \text{read} \;+\; \sum \text{write}\;$ (I/O **somado**, em série) |
| Duração FX (pior) | $\;t\_init + t\_cpu + \max(\text{read}) + \max(\text{write})\;$ na config mais lenta (I/O **paralelo**) |

O `max_running_time` é a **soma sobre todas as tarefas** — ou seja, um cenário 100% sequencial,
que **ignora o paralelismo do DAG** e o `task_type`.

### 2.2. CM v1

$$CM_{v1} = \underbrace{\sum_{i \in T} \max_r c_i^r}_{\text{custo base por tarefa}}
\;+\; \underbrace{\Big(\sum_{j \in M} c_j^{vm}\Big) \cdot TM}_{\text{ociosidade: todas as VMs ligadas pelo horizonte inteiro}}$$

O termo de ociosidade assume **todas as VMs ligadas do instante 0 até TM**.

---

## 3. Problemas encontrados

### 3.1. TM cresce com o número de tarefas, não com o paralelismo

Como TM v1 é uma **soma sobre todas as tarefas**, workflows muito paralelos recebem um horizonte
gigante mesmo tendo `makespan` real curto. O fator `fx_slowdown` (FX mais lento que a VM) ainda
multiplica a contribuição de cada tarefa.

Ilustração com instâncias propostas (tempos do gerador, mediana de 15 sementes). A coluna
"resource-aware" é o `makespan` de um escalonamento paralelo viável:

| Instância | Tarefas | Profundidade do DAG | TM v1 (Σ sequencial) | `makespan` resource-aware | Redução |
|---|---|---|---|---|---|
| `Synthetic_032` | 8 | 2 | 310 | 122 | 61 % |
| `Synthetic_060` | 12 | 3 | 553 | 206 | 63 % |
| `Synthetic_064` | 22 | 3 | 991 | 215 | **78 %** |
| `Synthetic_042` | 20 | 19 | 800 | 759 | 5 % |

A `Synthetic_064` (22 tarefas, profundidade 3) chega a $TM_{v1} \approx 991\,s$ apesar de ser rasa
e altamente paralela — perto do limiar em que o CPLEX se torna inviável no ambiente de testes
(~1000 unidades de tempo). Já a cadeia profunda `Synthetic_042` quase não reduz: ela é
intrinsecamente de horizonte longo (caminho crítico ≈ soma).

### 3.2. CM estoura em instâncias com muitas VMs

O termo de ociosidade $\big(\sum_j c_j^{vm}\big)\cdot TM$ soma **todas** as VMs ligadas pelo
horizonte inteiro. Em instâncias reais com 5 VMs (uma delas cara), isso infla o CM em ~370×: aplicar
a regra v1 à `I002_T7_C5_D14_VM5` produz $CM \approx \$0.043$ contra o $\$0.000115$ realista.

### 3.3. Cortes manuais e truncamento do ótimo de custo

Como TM v1 ficava alto demais, foi necessário **cortar manualmente** o horizonte para o CPLEX
fechar. Na `Synthetic_022`, o valor calculado ($108\,s$) foi reduzido à mão para $50\,s$. O resultado
do CPLEX em $\alpha = 0.05$ deu `makespan` $= 50\,s$ — **saturando o teto**, sinal de que uma solução
melhor (mais barata e mais lenta) foi cortada.

---

## 4. Versão 2 — *resource-aware* com margem

A proposta atual substitui a soma sequencial por um **escalonamento viável** que respeita o
paralelismo e o `task_type`, e adiciona uma **margem de segurança**.

### 4.1. TM v2

$$TM_{v2} = \text{makespan}\big(\text{ListSchedule}\big) \cdot (1 + \delta), \qquad \delta = 0.25$$

O `ListSchedule` constrói **um** escalonamento factível e toma seu `makespan`:

| `task_type` | Atribuição no escalonamento | Paralelismo |
|---|---|---|
| `1` (VM ou FX) | FX na config mais lenta | ilimitado (funções independentes) |
| `0` (somente VM) | VM | no máximo `num_vms` em paralelo |

Como é o `makespan` de um escalonamento factível, $TM_{v2}$ permanece um **limite superior válido**
sobre o ótimo (não corta nenhuma solução). Ele **degrada corretamente** conforme a composição de
tipos:

- todas `task_type=1` → `makespan` ≈ caminho crítico (FX paralelo);
- todas `task_type=0`, 1 VM → soma sequencial (= TM v1);
- caso misto → valor intermediário.

> **Por que não usar o caminho crítico puro?** Com tarefas `task_type=0`, o paralelismo é limitado
> a `num_vms`; o `makespan` viável pode **exceder** o caminho crítico ingênuo, que então deixa de ser
> um limite superior válido. O `ListSchedule` cobre os dois casos.

### 4.2. CM v2 — o dual do TM

$$CM_{v2} = \Big( \underbrace{\sum_{i:\,type=1} \max_r c_i^r}_{\text{tipo 1: recurso mais caro (FX ou VM)}}
\;+\; \underbrace{\sum_{j \in M_0} c_j^{vm} \cdot TM_{ls}}_{\text{tipo 0: VM ligada do início ao fim}} \Big)\cdot(1+\delta)$$

onde $M_0$ são as VMs usadas por tarefas `task_type=0`.

Para `task_type=1`, o custo por tarefa é o **máximo entre as configs FX e as VMs** (o recurso mais
caro), e **não** o custo da config FX mais barata. O limite superior de CM precisa olhar para os
recursos **rápidos** — VMs e configs FX rápidas, em geral mais caros — porque CM amarra no extremo de
**tempo** ($\alpha$ alto), onde o ótimo escolhe justamente esses recursos. É o espelho do TM, cujo
limite superior olha para recursos **lentos** (em geral mais baratos). Usar apenas o custo FX barato
subdimensionaria o CM e cortaria o ótimo de $\alpha$ alto: na `Synthetic_022`, o custo ótimo em
$\alpha = 0.95$ excede a soma do custo FX na config mais cara, precisamente porque esse ótimo usa
VMs rápidas.

### 4.3. Nota sobre o piso de tempo

O piso de $1.0$ é aplicado **apenas ao total** da duração, nunca por termo de I/O. Instâncias
sintéticas usam tempo inteiro (piso $1.0$); instâncias reais usam segundos contínuos sub-1 (piso
$0.0$, detectado automaticamente). Aplicar o piso por termo de I/O inflava as instâncias reais (uma
leitura de $0.12\,s$ virava $1.0\,s$).

### 4.4. Princípio do TM resource-aware

> O `TM_listsched` estima o `makespan` do escalonamento mais barato — todas as tarefas em FX na
> configuração mais lenta (e mais barata), com paralelismo máximo. Por construção, ele **acompanha
> por cima** o `makespan` da solução de foco em custo ($\alpha$ baixo), e a aproximação é mais
> apertada justamente em workflows muito paralelos e *I/O-bound*, onde o FX de fato vence a VM
> (porque o FX paraleliza I/O — usa $\max(\text{read})$ — enquanto a VM o serializa — usa
> $\sum \text{read}$).

---

## 5. Motivação da margem (folga)

O `TM_listsched` aproxima o `makespan` do **extremo de custo**, mas com folga muito pequena: em
instâncias justas ele iguala o ótimo de $\alpha = 0.05$ (ver `Synthetic_013` na Tabela 6.1, onde
$TM_{ls} = 31 = z_{\alpha=0.05}$). Sem folga, qualquer instância nova cujo ótimo de custo seja
ligeiramente mais lento teria o horizonte truncado.

A margem $\delta = 0.25$ resolve isso de forma uniforme e defensável:

- garante que o ótimo de $\alpha$ baixo (TM) e o de $\alpha$ alto (CM) **caibam com folga** (na
  instância mais justa, a `Synthetic_013`, a folga resultante é de +25%);
- mantém a régua **consistente entre instâncias** (escala uniforme → FO comparável);
- preserva a tratabilidade (fica bem abaixo da soma sequencial v1).

Para instâncias novas, a recomendação metodológica é **verificar e ajustar**: usar $TM_{v2}$ como
ponto de partida e, se o `makespan` ótimo em $\alpha$ baixo saturar o teto, aumentar o horizonte e
re-resolver — formalizando o que antes era feito à mão.

---

## 6. Tabelas comparativas — instâncias que rodaram no CPLEX

Instâncias validadas: `Synthetic_007`, `Synthetic_011`, `Synthetic_012`, `Synthetic_013`,
`Synthetic_022`. Para 007–013, o `max_running_time` do arquivo coincide com TM v1 (foi assim que
foram geradas); a `Synthetic_022` teve corte manual de $108\,s$ para $50\,s$.

### 6.1. `max_running_time` (TM) e validação contra o `makespan` de foco em custo

| Instância | Tarefas | TM no arquivo | TM v1 (Σ) | `TM_listsched` | TM v2 (×1.25) | `makespan` ótimo $\alpha{=}0.05$ | TM v2 $\ge z_{0.05}$ ? |
|---|---|---|---|---|---|---|---|
| `Synthetic_007` | 3 | 34.0 s | 34 | 28 | 35.0 s | 15 s | ✅ |
| `Synthetic_011` | 4 | 66.0 s | 66 | 29 | 36.3 s | 24 s | ✅ |
| `Synthetic_012` | 5 | 61.0 s | 61 | 28 | 35.0 s | 25 s | ✅ |
| `Synthetic_013` | 5 | 49.0 s | 49 | 31 | 38.8 s | 31 s | ✅ |
| `Synthetic_022` | 8 | 50.0 s* | 108 | 54 | 67.5 s | 50 s | ✅ |

\* valor cortado manualmente (TM v1 era $108\,s$).

### 6.2. `max_financial_cost` (CM) e validação contra o custo de foco em tempo

| Instância | CM no arquivo (v1) | CM v2 (×1.25) | custo ótimo $\alpha{=}0.95$ | CM v2 $\ge$ custo ? |
|---|---|---|---|---|
| `Synthetic_007` | \$0.004227 | \$0.001447 | \$0.000884 | ✅ |
| `Synthetic_011` | \$0.009662 | \$0.004805 | \$0.001013 | ✅ |
| `Synthetic_012` | \$0.016228 | \$0.007001 | \$0.003228 | ✅ |
| `Synthetic_013` | \$0.007280 | \$0.003514 | \$0.001365 | ✅ |
| `Synthetic_022` | \$0.004536 | \$0.002183 | \$0.000657 | ✅ |

CM v2 é simultaneamente **mais justo** que o v1 (na 022: \$0.00218 vs \$0.00454) e **válido** como
limite superior (≥ custo de $\alpha = 0.95$ em todas).

### 6.3. `makespan` ótimo do CPLEX por $\alpha$ (contexto)

| Instância | $z$ em $\alpha{=}0.05$ (custo) | $z$ em $\alpha{=}0.50$ | $z$ em $\alpha{=}0.95$ (tempo) |
|---|---|---|---|
| `Synthetic_007` | 15 s | 15 s | 11 s |
| `Synthetic_011` | 24 s | 24 s | 23 s |
| `Synthetic_012` | 25 s | 24 s | 19 s |
| `Synthetic_013` | 31 s | 28 s | 26 s |
| `Synthetic_022` | 50 s | 43 s | 42 s |

O `makespan` de foco em custo ($\alpha = 0.05$) é sempre $\ge$ o de foco em tempo ($\alpha = 0.95$) —
confirmando que o extremo de custo é o ponto que TM precisa cobrir.

---

## 7. Instâncias reais (DENETHOR)

Nas instâncias reais, o cabeçalho foi montado por uma régua diferente (consultas SQL): TM = **soma
sequencial** das durações FX na config mais lenta; CM = **soma** dos custos FX na config mais cara —
ambos **ignorando VM e paralelismo**. Por exemplo, na `I002_T7_C5_D14_VM5`, $TM_{arq} = 7.85\,s$ é
exatamente a soma das durações da `conf_id=1`, e $CM_{arq} = \$0.000115$ é a soma dos custos da
`conf_id=5`.

Esses valores são **placeholders**: a recomendação é **recalcular TM e CM na leitura** — tanto pela
heurística GRASP+VND quanto antes de alimentar o MILP time-indexed — usando a mesma regra
*resource-aware* das sintéticas. Aplicando-a, o horizonte das reais grandes encolhe drasticamente
(ex.: `I010_T31_C5_D97_VM5` sai de $TM_{arq} = 204\,s$ para $TM_{v2} \approx 21\,s$), o que viabiliza
a execução exata.

---

## 8. Resumo

| Aspecto | Versão 1 (pior caso sequencial) | Versão 2 (*resource-aware* + margem) |
|---|---|---|
| TM | Σ das piores durações de todas as tarefas | `makespan` de escalonamento viável × $(1+\delta)$ |
| CM | custo base + todas as VMs ociosas × TM | custo do recurso mais caro (tipo 1) + VM do tipo 0 × TM, × $(1+\delta)$ |
| Paralelismo | ignorado | respeitado (FX ilimitado, VM ≤ `num_vms`) |
| `task_type` | ignorado | tratado (0 = VM limitada, 1 = FX) |
| Validade como limite superior | sim (muito frouxo) | sim (justo, com folga $\delta = 0.25$) |
| Tratabilidade no CPLEX | ruim (TM na casa das centenas/milhares) | boa (horizonte próximo do ótimo + folga) |

TM e CM continuam sendo **limites superiores conservadores** — a versão 2 apenas troca o pessimismo
cego por um limite *resource-aware* justo, com margem explícita para preservar a fidelidade nos
extremos de $\alpha$.
