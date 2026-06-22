import os
import re
import sys
import shutil

# --- CONFIGURATION PARAMETERS ---
#n1
# USER_TARGET_WORKFLOW_IDS = ["Synthetic_007", "Synthetic_011", "Synthetic_012", "Synthetic_013", "Synthetic_022"]

#n2
# USER_TARGET_WORKFLOW_IDS = ["Synthetic_015", "Synthetic_016", "Synthetic_020", "Synthetic_025", "Synthetic_029"]

#n3
USER_TARGET_WORKFLOW_IDS = ["Synthetic_032", "Synthetic_042", "Synthetic_060"]

INPUT_FILE = "data/instances_definition.txt"
OUTPUT_DIR = "data/mermaid"
DEFAULT_FONT_SIZE = "20px"
DEFAULT_STROKE_WIDTH = None #"3px"
LINK_STROKE_WIDTH = None #"2px"
# --------------------------------

def main():
    target_workflows = sys.argv[1:] if len(sys.argv) > 1 else USER_TARGET_WORKFLOW_IDS

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(INPUT_FILE, 'r') as f:
        content = f.read()

    workflows = content.split('--------------------------------')

    found_ids = set()

    for wf in workflows:
        wf = wf.strip()
        if not wf:
            continue

        lines = wf.split('\n')
        wf_id_line = lines[0]

        # Example line: WORKFLOW_ID: Synthetic_007
        if ':' not in wf_id_line:
            continue

        wf_id = wf_id_line.split(':')[1].strip()

        if target_workflows and wf_id not in target_workflows:
            continue

        found_ids.add(wf_id)

        try:
            num_str = wf_id.split('_')[1]
            num = int(num_str)
        except Exception:
            continue

        prefix = f"S{num}"

        # Extract tasks and data
        tasks = set()
        data = set()

        edges_from_data = {} # dX -> list of tY
        edges_from_task = {} # tX -> list of dY

        pattern_val = None
        comment_val = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('---') or line.startswith('WORKFLOW_ID') or line.startswith('TASKS') or line.startswith('DATA'):
                continue

            if line.startswith('PATTERN:'):
                pattern_val = line.split(':', 1)[1].strip()
                continue

            if line.startswith('COMMENT:'):
                comment_val = line.split(':', 1)[1].strip()
                continue

            # e.g., t0: d0,d1 -> d2
            if ':' in line and '->' in line:
                task_part, rest = line.split(':')
                t_id = task_part.strip()
                tasks.add(t_id)

                in_data_str, out_data_str = rest.split('->')
                in_data = [d.strip() for d in in_data_str.split(',') if d.strip()]
                out_data = [d.strip() for d in out_data_str.split(',') if d.strip()]

                for d in in_data:
                    data.add(d)
                    if d not in edges_from_data:
                        edges_from_data[d] = []
                    edges_from_data[d].append(t_id)

                for d in out_data:
                    data.add(d)
                    if t_id not in edges_from_task:
                        edges_from_task[t_id] = []
                    edges_from_task[t_id].append(d)

        output_path = os.path.join(OUTPUT_DIR, f"Synthetic_{num:03d}.mermaid")
        backup_path = output_path + ".bak"

        custom_styles = []
        nodes_match = False
        old_file_existed = False

        if os.path.exists(output_path):
            old_file_existed = True
            shutil.copy2(output_path, backup_path)

            with open(output_path, 'r') as f:
                old_content = f.read()

            old_nodes = set(re.findall(rf"({prefix}_[dt]\d+)", old_content))
            new_nodes = {f"{prefix}_{d}" for d in data} | {f"{prefix}_{t}" for t in tasks}

            if old_nodes == new_nodes:
                nodes_match = True
                for line in old_content.split('\n'):
                    # Extract specific style and linkStyle
                    if re.match(rf"^\s*style\s+{prefix}_[dt]\d+\s+", line):
                        custom_styles.append(line)
                    elif re.match(r"^\s*linkStyle\s+(?!default\b).+", line):
                        custom_styles.append(line)

        # Generate Mermaid
        mermaid_lines = []
        mermaid_lines.append("---")
        mermaid_lines.append("config:")
        mermaid_lines.append("  layout: dagre")
        mermaid_lines.append("  theme: redux")
        mermaid_lines.append("  look: classic")
        mermaid_lines.append("---")
        if pattern_val:
            mermaid_lines.append(f"%% PATTERN: {pattern_val}")
        if comment_val:
            mermaid_lines.append(f"%% COMMENT: {comment_val}")
        mermaid_lines.append("flowchart LR")

        # Apply default classes
        classDef_props = []
        if DEFAULT_FONT_SIZE is not None:
            classDef_props.append(f"font-size:{DEFAULT_FONT_SIZE}")
        if DEFAULT_STROKE_WIDTH is not None:
            classDef_props.append(f"stroke-width:{DEFAULT_STROKE_WIDTH}")
        if classDef_props:
            mermaid_lines.append(f"    classDef default {', '.join(classDef_props)};")
        if LINK_STROKE_WIDTH is not None:
            mermaid_lines.append(f"    linkStyle default stroke-width:{LINK_STROKE_WIDTH};")

        mermaid_lines.append(f'    subgraph Synthetic_{num}["{wf_id}"]')
        mermaid_lines.append("        direction LR")

        # Note: formatting dX and tX
        for d in sorted(data, key=lambda x: int(x[1:])):
            d_num = int(d[1:])
            mermaid_lines.append(f'            {prefix}_{d}(("d_{d_num + 900}"))')

        for t in sorted(tasks, key=lambda x: int(x[1:])):
            t_num = int(t[1:])
            mermaid_lines.append(f'            {prefix}_{t}("t_{t_num + 100}")')

        mermaid_lines.append("    end")

        for d in sorted(edges_from_data.keys(), key=lambda x: int(x[1:])):
            targets = edges_from_data[d]
            targets_str = " & ".join([f"{prefix}_{t}" for t in targets])
            mermaid_lines.append(f"    {prefix}_{d} --> {targets_str}")

        for t in sorted(edges_from_task.keys(), key=lambda x: int(x[1:])):
            targets = edges_from_task[t]
            targets_str = " & ".join([f"{prefix}_{d}" for d in targets])
            mermaid_lines.append(f"    {prefix}_{t} --> {targets_str}")

        if nodes_match and custom_styles:
            mermaid_lines.append("")
            mermaid_lines.append("    %% Custom Styles")
            mermaid_lines.extend(custom_styles)

        with open(output_path, 'w') as f:
            f.write('\n'.join(mermaid_lines))
            f.write('\n')

        if old_file_existed:
            if nodes_match:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                print(f"Generated {output_path} (Restored custom styles and removed backup)")
            else:
                print(f"Generated {output_path} (Nodes diverged. Backup kept at {backup_path})")
        else:
            print(f"Generated {output_path}")

    for wf_id in target_workflows:
        if wf_id not in found_ids:
            print(f"ERROR: workflow '{wf_id}' not found in {INPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
