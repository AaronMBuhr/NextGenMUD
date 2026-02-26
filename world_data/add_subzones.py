import sys
import re
import os

def update_world_yaml(file_path):
    # 1. Read all room_id,subzone_id pairs from stdin
    # Logic assumes input order matches file order as per instructions
    targets = []
    for line in sys.stdin:
        line = line.strip()
        if not line or ',' not in line:
            continue
        targets.append(line.split(',', 1))

    if not targets:
        print("No input pairs found on stdin.", file=sys.stderr)
        return

    target_idx = 0
    temp_file = file_path + ".tmp"

    try:
        with open(file_path, 'r') as f_in, open(temp_file, 'w') as f_out:
            for line in f_in:
                # Always write the original line first
                f_out.write(line)

                # Check if we still have targets to find
                if target_idx < len(targets):
                    curr_room_id, curr_subzone = targets[target_idx]
                    
                    # Pattern: match start of line, any whitespace, the room_id, and a colon.
                    # This avoids partial matches (e.g., 'forest' matching 'forest_road').
                    # We also allow for potential trailing whitespace or comments.
                    pattern = rf'^(\s*){re.escape(curr_room_id)}:(?:\s*|$|#)'
                    match = re.match(pattern, line)

                    if match:
                        indent = match.group(1)
                        # In your YAML structure, properties are indented 2 spaces further 
                        # than their parent key.
                        new_indent = indent + "  "
                        f_out.write(f"{new_indent}subzone: {curr_subzone}\n")
                        
                        # Move to the next target pair
                        target_idx += 1

        # Replace original file with the modified version
        os.replace(temp_file, file_path)
        print(f"Successfully updated {file_path}. Processed {target_idx} updates.")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: cat subzone_list.txt | python add_subzones.py <world_file.yaml>")
    else:
        update_world_yaml(sys.argv[1])