import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from .instance_io import (
    BucketRangeRow,
    ConfigRow,
    DataRow,
    InstanceParser,
    ParsedInstance,
    TaskRow,
)


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str


class CountConsistencyValidator:
    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        if instance.header.num_tasks != len(instance.tasks):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.1",
                    f"#tasks={instance.header.num_tasks} mas linhas de tasks={len(instance.tasks)}",
                )
            )

        if instance.header.num_data != len(instance.data):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.2",
                    f"#data={instance.header.num_data} mas linhas de data={len(instance.data)}",
                )
            )

        if instance.header.num_vms != len(instance.vms):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.3",
                    f"#vms={instance.header.num_vms} mas linhas de vm={len(instance.vms)}",
                )
            )

        if instance.header.num_bucket_ranges != len(instance.bucket_ranges):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.4",
                    f"#bucket_ranges={instance.header.num_bucket_ranges} mas linhas de bucket_ranges={len(instance.bucket_ranges)}",
                )
            )

        conf_ids = {c.conf_id for c in instance.configs}
        if instance.header.num_configs != len(conf_ids):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.5",
                    f"#config={instance.header.num_configs} mas conf_id distintos={len(conf_ids)}",
                )
            )

        expected_combinations = instance.header.num_tasks * instance.header.num_configs
        if len(instance.configs) != expected_combinations:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "V1.6",
                    f"linhas seção config={len(instance.configs)} mas esperado={expected_combinations}",
                )
            )

        return issues


class ReferentialIntegrityValidator:
    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        data_ids = [d.data_id for d in instance.data]
        task_ids = [t.task_id for t in instance.tasks]
        vm_ids = [v.vm_id for v in instance.vms]

        duplicates = self._find_duplicates(data_ids)
        if duplicates:
            issues.append(ValidationIssue("ERROR", "V2.3", f"data_id duplicado(s): {duplicates}"))

        duplicates = self._find_duplicates(task_ids)
        if duplicates:
            issues.append(ValidationIssue("ERROR", "V2.4", f"task_id duplicado(s): {duplicates}"))

        duplicates = self._find_duplicates(vm_ids)
        if duplicates:
            issues.append(ValidationIssue("ERROR", "V2.5", f"vm_id duplicado(s): {duplicates}"))

        pair_list = [f"{c.task_id}::{c.conf_id}" for c in instance.configs]
        duplicates = self._find_duplicates(pair_list)
        if duplicates:
            issues.append(ValidationIssue("ERROR", "V2.6", f"(task_id,conf_id) duplicado(s): {duplicates}"))

        defined_data = set(data_ids)
        used_data = set()
        for t in instance.tasks:
            used_data.update(t.input_ids)
            used_data.update(t.output_ids)

        missing_data = sorted(used_data - defined_data)
        if missing_data:
            issues.append(ValidationIssue("ERROR", "V2.1", f"data_id referenciado e ausente na seção data: {missing_data}"))

        orphan_data = sorted(defined_data - used_data)
        if orphan_data:
            issues.append(ValidationIssue("ERROR", "V2.2", f"data_id órfão na seção data: {orphan_data}"))

        return issues

    @staticmethod
    def _find_duplicates(items: List[str]) -> List[str]:
        seen: Set[str] = set()
        dup: Set[str] = set()
        for item in items:
            if item in seen:
                dup.add(item)
            seen.add(item)
        return sorted(dup)


class StaticDynamicConsistencyValidator:
    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        output_count: Dict[str, int] = {}
        for t in instance.tasks:
            for d in t.output_ids:
                output_count[d] = output_count.get(d, 0) + 1

        for d in instance.data:
            produced_times = output_count.get(d.data_id, 0)

            if produced_times == 0:
                if d.is_static != 1:
                    issues.append(ValidationIssue("ERROR", "V3.1", f"{d.data_id} nunca produzido, mas is_static={d.is_static}"))
                if d.write_time_avg is not None:
                    issues.append(ValidationIssue("ERROR", "V3.1", f"{d.data_id} estático deve ter write_time_avg=None"))
                if d.n_source_devices < 1:
                    issues.append(ValidationIssue("ERROR", "V3.1", f"{d.data_id} estático deve ter n_source_devices>=1"))

            if produced_times > 0:
                if d.is_static != 0:
                    issues.append(ValidationIssue("ERROR", "V3.2", f"{d.data_id} produzido, mas is_static={d.is_static}"))
                if d.write_time_avg is None or d.write_time_avg <= 0:
                    issues.append(ValidationIssue("ERROR", "V3.2", f"{d.data_id} dinâmico deve ter write_time_avg>0"))
                if d.n_source_devices != 0:
                    issues.append(ValidationIssue("ERROR", "V3.2", f"{d.data_id} dinâmico deve ter n_source_devices=0"))

            if produced_times > 1:
                issues.append(ValidationIssue("ERROR", "V3.3", f"{d.data_id} possui {produced_times} produtores"))

            if d.is_static == 1 and produced_times > 0:
                issues.append(ValidationIssue("ERROR", "V3.4", f"{d.data_id} marcado estático mas aparece em output"))

        return issues


class NumericDomainValidator:
    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        for t in instance.tasks:
            if t.task_type not in {0, 1}:
                issues.append(ValidationIssue("ERROR", "V4.1", f"{t.task_id} task_type inválido={t.task_type}"))
            if t.vm_cpu_time <= 0:
                issues.append(ValidationIssue("ERROR", "V4.2", f"{t.task_id} vm_cpu_time deve ser >0"))
            if t.activity_id <= 0:
                issues.append(ValidationIssue("ERROR", "V4.3", f"{t.task_id} activity_id deve ser >0"))
            if t.n_input != len(t.input_ids):
                issues.append(ValidationIssue("ERROR", "V4.4", f"{t.task_id} n_input={t.n_input} mas lista tem {len(t.input_ids)}"))
            if t.n_output != len(t.output_ids):
                issues.append(ValidationIssue("ERROR", "V4.4", f"{t.task_id} n_output={t.n_output} mas lista tem {len(t.output_ids)}"))

        for d in instance.data:
            if d.data_size_bytes <= 0:
                issues.append(ValidationIssue("ERROR", "V4.5", f"{d.data_id} data_size_bytes deve ser >0"))
            if d.is_static not in {0, 1}:
                issues.append(ValidationIssue("ERROR", "V4.7", f"{d.data_id} is_static inválido={d.is_static}"))

        for v in instance.vms:
            if v.cpu_slowdown <= 0 or v.cpu_slowdown > 1:
                issues.append(ValidationIssue("ERROR", "V4.8", f"vm_id={v.vm_id} cpu_slowdown fora de (0,1]"))
            if v.cost_per_second <= 0:
                issues.append(ValidationIssue("ERROR", "V4.9", f"vm_id={v.vm_id} cost_per_second deve ser >0"))
            if v.storage_bytes <= 0:
                issues.append(ValidationIssue("ERROR", "V4.9", f"vm_id={v.vm_id} storage_bytes deve ser >0"))
            if v.bandwidth_mbps <= 0:
                issues.append(ValidationIssue("ERROR", "V4.9", f"vm_id={v.vm_id} bandwidth_mbps deve ser >0"))

        for c in instance.configs:
            if c.task_cost <= 0:
                issues.append(ValidationIssue("ERROR", "V4.10", f"{c.task_id}/conf={c.conf_id} task_cost deve ser >0"))
            if c.task_time_duration <= 0:
                issues.append(ValidationIssue("ERROR", "V4.10", f"{c.task_id}/conf={c.conf_id} task_time_duration deve ser >0"))
            if c.task_count <= 0:
                issues.append(ValidationIssue("ERROR", "V5.4", f"{c.task_id}/conf={c.conf_id} task_count deve ser >0"))

        return issues


class MatrixTimeCoherenceValidator:
    DEFAULT_SUM_TOLERANCE_PERCENT = 0.10

    def validate(self, instance: ParsedInstance, sum_tolerance_percent: Optional[float] = None) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        tolerance = self.DEFAULT_SUM_TOLERANCE_PERCENT if sum_tolerance_percent is None else sum_tolerance_percent

        data_by_id: Dict[str, DataRow] = {d.data_id: d for d in instance.data}
        task_by_id: Dict[str, TaskRow] = {t.task_id: t for t in instance.tasks}

        for c in instance.configs:
            parts_sum = c.task_time_init + c.task_time_cpu + c.task_time_read + c.task_time_write
            if not self._within_tolerance(c.task_time_duration, parts_sum, tolerance):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "V5.1",
                        (
                            f"{c.task_id}/conf={c.conf_id} duration={c.task_time_duration:.6f} "
                            f"difere do somatório={parts_sum:.6f} com tolerância={tolerance:.2%}"
                        ),
                    )
                )

            task = task_by_id.get(c.task_id)
            if not task:
                continue

            expected_read = 0.0
            for did in task.input_ids:
                drow = data_by_id.get(did)
                if drow and drow.read_time_avg is not None:
                    expected_read += drow.read_time_avg

            expected_write = 0.0
            for did in task.output_ids:
                drow = data_by_id.get(did)
                if drow and drow.write_time_avg is not None:
                    expected_write += drow.write_time_avg

            if not self._within_tolerance(c.task_time_read, expected_read, tolerance):
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "V5.2",
                        (
                            f"{c.task_id}/conf={c.conf_id} task_time_read={c.task_time_read:.6f} "
                            f"difere do esperado={expected_read:.6f} com tolerância={tolerance:.2%}"
                        ),
                    )
                )

            if not self._within_tolerance(c.task_time_write, expected_write, tolerance):
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "V5.3",
                        (
                            f"{c.task_id}/conf={c.conf_id} task_time_write={c.task_time_write:.6f} "
                            f"difere do esperado={expected_write:.6f} com tolerância={tolerance:.2%}"
                        ),
                    )
                )

        return issues

    @staticmethod
    def _within_tolerance(actual: float, expected: float, tolerance_percent: float) -> bool:
        if math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
            return True

        base = abs(expected)
        if base < 1e-9:
            return abs(actual - expected) <= 1e-6

        allowed = base * tolerance_percent
        return abs(actual - expected) <= allowed


class BucketRangeValidator:
    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        buckets = instance.bucket_ranges

        if not buckets:
            issues.append(ValidationIssue("ERROR", "V6.0", "nenhuma faixa de bucket encontrada"))
            return issues

        if buckets[0].size1_bytes != 0:
            issues.append(ValidationIssue("ERROR", "V6.1", "primeira faixa de bucket deve iniciar em 0"))

        for idx, b in enumerate(buckets):
            if b.size2_bytes <= b.size1_bytes:
                issues.append(ValidationIssue("ERROR", "V6.3", f"faixa {b.bucket_range_id} com size2<=size1"))
            if b.cost_per_byte <= 0:
                issues.append(ValidationIssue("ERROR", "V6.4", f"faixa {b.bucket_range_id} com cost_per_byte<=0"))
            if idx > 0 and buckets[idx - 1].size2_bytes != b.size1_bytes:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "V6.2",
                        (
                            f"faixas não contíguas entre {buckets[idx - 1].bucket_range_id} "
                            f"e {b.bucket_range_id}"
                        ),
                    )
                )

        return issues


class FileNameConsistencyValidator:
    FILENAME_PATTERN = re.compile(r"_T(?P<tasks>\d+)_C(?P<configs>\d+)_D(?P<data>\d+)_")

    def validate(self, instance: ParsedInstance) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        m = self.FILENAME_PATTERN.search(instance.file_path.name)
        if not m:
            return issues

        expected_tasks = int(m.group("tasks"))
        expected_configs = int(m.group("configs"))
        expected_data = int(m.group("data"))

        if instance.header.num_tasks != expected_tasks:
            issues.append(ValidationIssue("ERROR", "V7.1", f"nome arquivo T={expected_tasks} mas header #tasks={instance.header.num_tasks}"))
        if instance.header.num_configs != expected_configs:
            issues.append(ValidationIssue("ERROR", "V7.1", f"nome arquivo C={expected_configs} mas header #config={instance.header.num_configs}"))
        if instance.header.num_data != expected_data:
            issues.append(ValidationIssue("ERROR", "V7.1", f"nome arquivo D={expected_data} mas header #data={instance.header.num_data}"))

        return issues


class InstanceValidator:
    def __init__(self) -> None:
        self.count_validator = CountConsistencyValidator()
        self.ref_integrity_validator = ReferentialIntegrityValidator()
        self.static_dynamic_validator = StaticDynamicConsistencyValidator()
        self.numeric_domain_validator = NumericDomainValidator()
        self.matrix_time_validator = MatrixTimeCoherenceValidator()
        self.bucket_validator = BucketRangeValidator()
        self.filename_validator = FileNameConsistencyValidator()

    def validate(self, instance: ParsedInstance, sum_tolerance_percent: Optional[float] = None) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        issues.extend(self.count_validator.validate(instance))
        issues.extend(self.ref_integrity_validator.validate(instance))
        issues.extend(self.static_dynamic_validator.validate(instance))
        issues.extend(self.numeric_domain_validator.validate(instance))
        issues.extend(self.matrix_time_validator.validate(instance, sum_tolerance_percent=sum_tolerance_percent))
        issues.extend(self.bucket_validator.validate(instance))
        issues.extend(self.filename_validator.validate(instance))
        return issues
