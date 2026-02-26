#!/usr/bin/env python3
"""
One-off script: Move top-level CHARACTERS and OBJECTS into ZONES.<zone_id>.characters
and ZONES.<zone_id>.objects so world files follow the correct hierarchy:
  ZONES -> <zone_id> -> characters | objects | rooms | ...
"""
import sys
import os
from pathlib import Path

# Add project root for imports if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ruamel.yaml import YAML

def process_file(path: str) -> bool:
    """Load YAML, move CHARACTERS/OBJECTS into zones, save. Returns True if changed."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # avoid line wrapping
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)
    if not isinstance(data, dict):
        return False
    changed = False
    if "CHARACTERS" in data and isinstance(data["CHARACTERS"], list):
        for entry in data["CHARACTERS"]:
            if not isinstance(entry, dict) or "zone" not in entry or "characters" not in entry:
                continue
            zone_id = entry["zone"]
            if "ZONES" not in data or zone_id not in data["ZONES"]:
                print(f"  Warning: zone '{zone_id}' not in ZONES, skipping CHARACTERS")
                continue
            zone = data["ZONES"][zone_id]
            if "characters" not in zone:
                zone["characters"] = []
            zone["characters"].extend(entry["characters"])
            changed = True
        del data["CHARACTERS"]
    if "OBJECTS" in data and isinstance(data["OBJECTS"], list):
        for entry in data["OBJECTS"]:
            if not isinstance(entry, dict) or "zone" not in entry or "objects" not in entry:
                continue
            zone_id = entry["zone"]
            if "ZONES" not in data or zone_id not in data["ZONES"]:
                print(f"  Warning: zone '{zone_id}' not in ZONES, skipping OBJECTS")
                continue
            zone = data["ZONES"][zone_id]
            if "objects" not in zone:
                zone["objects"] = []
            zone["objects"].extend(entry["objects"])
            changed = True
        del data["OBJECTS"]
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
    return changed

def main():
    world_dir = Path(__file__).resolve().parent.parent / "world_data"
    if not world_dir.is_dir():
        print("world_data not found")
        return 1
    count = 0
    for p in sorted(world_dir.glob("*.yaml")) + sorted(world_dir.glob("*.yml")):
        if process_file(str(p)):
            print(f"Updated: {p.name}")
            count += 1
    print(f"Done. Updated {count} file(s).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
