import os, random
import re
from .workflow_generator_model import WorkflowGeneratorModel

class WorkflowGeneratorUser(WorkflowGeneratorModel):
    def __init__(self, workflow_id, num_tasks, num_data, task_defs, output_dir, num_vms=2, num_configs=2, num_bucket_ranges=3, use_integer_time=True, task_prefix_replace=None, data_prefix_replace=None, task_id_offset=0, data_id_offset=0, fx_slowdown_min=2.0, fx_slowdown_max=70.0, task_type=1, cpu_time_range=None, read_time_range=None, write_time_range=None):
        super().__init__(
            num_tasks=num_tasks,
            num_data=num_data,
            num_vms=num_vms,
            num_configs=num_configs,
            num_bucket_ranges=num_bucket_ranges,
            use_integer_time=use_integer_time,
            fx_slowdown_min=fx_slowdown_min,
            fx_slowdown_max=fx_slowdown_max,
            task_type=task_type,
        )
        self.workflow_id = workflow_id
        self.task_defs = task_defs
        self.output_dir = output_dir
        self.task_prefix_replace = task_prefix_replace  # Dict: {'old': 't', 'new': '1'}
        self.data_prefix_replace = data_prefix_replace  # Dict: {'old': 'd', 'new': '9'}
        self.task_id_offset = task_id_offset
        self.data_id_offset = data_id_offset
        # Faixas de sorteio (min, max). Se None, usa o default do modo:
        #   inteiro  -> cpu [1,10], read [1,5], write [1,3]
        #   contínuo -> cpu [0.01,0.5], read [0.1,0.5], write [0.05,0.2]
        if use_integer_time:
            self.cpu_time_range = cpu_time_range or (1, 10)
            self.read_time_range = read_time_range or (1, 5)
            self.write_time_range = write_time_range or (1, 3)
        else:
            self.cpu_time_range = cpu_time_range or (0.01, 0.5)
            self.read_time_range = read_time_range or (0.1, 0.5)
            self.write_time_range = write_time_range or (0.05, 0.2)

    def _process_id(self, id_str, prefix_config, offset):
        """Replace ID prefix and apply offset if configured"""
        result = id_str
        if prefix_config:
            old_prefix = prefix_config.get('old')
            new_prefix = prefix_config.get('new')
            if old_prefix is not None and new_prefix is not None and result.startswith(old_prefix):
                result = new_prefix + result[len(old_prefix):]
        
        if offset:
            match = re.search(r"(\d+)$", result)
            if match:
                num = int(match.group(1)) + offset
                result = result[:match.start()] + str(num)
        return result

    def _build_tasks_and_data_model(self):
        tasks = []
        data_artifacts = {}
        used_data_ids = set()
        produced_data_ids = set()
        
        # Tasks
        for task in self.task_defs:
            cpu_time = self._get_time(*self.cpu_time_range)
            orig_match = re.search(r"(\d+)$", task['id'])
            orig_num = int(orig_match.group(1)) if orig_match else None
            activity_id = (orig_num // 2) + 1 if orig_num is not None else 1

            task_id = self._process_id(task['id'], self.task_prefix_replace, self.task_id_offset)
            
            # Replace prefixes in inputs and outputs
            inputs = [self._process_id(d, self.data_prefix_replace, self.data_id_offset) for d in task['inputs']]
            outputs = [self._process_id(d, self.data_prefix_replace, self.data_id_offset) for d in task['outputs']]
            
            tasks.append({
                'id': task_id,
                'activity_id': activity_id,
                'cpu_time': cpu_time,
                'inputs': inputs,
                'outputs': outputs
            })

            used_data_ids.update(inputs)
            used_data_ids.update(outputs)
            produced_data_ids.update(outputs)

        # Constrói os metadados com semântica explícita:
        # dados produzidos -> dinâmicos (write_time>0)
        # dados apenas consumidos -> estáticos (write_time=None)
        # IMPORTANTE: iterar em ordem determinística (sorted), e não sobre o set cru, para
        # que o consumo de random fique acoplado a um id específico. A ordem de iteração de
        # um set depende de PYTHONHASHSEED (aleatório por processo); sem o sorted, os tempos
        # sorteados se embaralham entre os dados a cada execução e o TM/CM muda mesmo com a
        # mesma random.seed. Com o sorted, basta a seed para reprodutibilidade total.
        for did in self._sort_ids(used_data_ids):
            read_time = self._get_time(*self.read_time_range)
            write_time = (
                self._get_time(*self.write_time_range)
            ) if did in produced_data_ids else None
            data_artifacts[did] = {
                "size_bytes": random.randint(100, 2000),
                "read_time": read_time,
                "write_time": write_time,
            }

        return tasks, data_artifacts
