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
                'task_defs': task_defs
            })
        i += 1
    return workflows
