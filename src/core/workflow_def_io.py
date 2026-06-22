def _parse_range(text):
    """'1,5' -> (1, 5) como int se inteiro, senão float. Retorna None se vazio/invalido."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != 2:
        return None
    def num(s):
        return int(s) if ("." not in s and "e" not in s.lower()) else float(s)
    return (num(parts[0]), num(parts[1]))


def load_workflows(input_file: str) -> list:
    workflows = []
    with open(input_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    i = 0
    while i < len(lines):
        if lines[i].startswith("WORKFLOW_ID:"):
            workflow_id = lines[i].split(":", 1)[1].strip()
            i += 1

            num_tasks = 0
            num_data = 0
            pattern = ""
            comment_lines = []
            cpu_time_range = None
            read_time_range = None
            write_time_range = None

            in_comment = False
            while i < len(lines) and lines[i] != "---":
                line = lines[i]
                if line.startswith("TASKS:"):
                    num_tasks = int(line.split(":", 1)[1].strip())
                    in_comment = False
                elif line.startswith("DATA:"):
                    num_data = int(line.split(":", 1)[1].strip())
                    in_comment = False
                elif line.startswith("PATTERN:"):
                    pattern = line.split(":", 1)[1].strip()
                    in_comment = False
                elif line.startswith("CPU_TIME:"):
                    cpu_time_range = _parse_range(line.split(":", 1)[1])
                    in_comment = False
                elif line.startswith("READ_TIME:"):
                    read_time_range = _parse_range(line.split(":", 1)[1])
                    in_comment = False
                elif line.startswith("WRITE_TIME:"):
                    write_time_range = _parse_range(line.split(":", 1)[1])
                    in_comment = False
                elif line.startswith("COMMENT:"):
                    comment_text = line.split(":", 1)[1].strip()
                    if comment_text:
                        comment_lines.append(comment_text)
                    in_comment = True
                elif in_comment:
                    comment_lines.append(line)
                i += 1

            comment = "\n".join(comment_lines)

            if i < len(lines) and lines[i] == "---":
                i += 1

            task_defs = []
            while i < len(lines) and not lines[i].startswith("--------------------------------"):
                line = lines[i]
                if line:
                    tid, rest = line.split(":")
                    tid = tid.strip()
                    inputs, outputs = rest.split("->")
                    inputs = [x.strip() for x in inputs.strip().split(",") if x.strip()]
                    outputs = [x.strip() for x in outputs.strip().split(",") if x.strip()]
                    task_defs.append({'id': tid, 'inputs': inputs, 'outputs': outputs})
                i += 1
            workflows.append({
                'workflow_id': workflow_id,
                'num_tasks': num_tasks,
                'num_data': num_data,
                'pattern': pattern,
                'comment': comment,
                'cpu_time_range': cpu_time_range,
                'read_time_range': read_time_range,
                'write_time_range': write_time_range,
                'task_defs': task_defs
            })
        i += 1
    return workflows