#!/usr/bin/env python3
"""
MUD Zone File Merger

Merges revision YAML files into base zone files with support for:
- Comment preservation (using ruamel.yaml)
- Deep dictionary merging
- Smart character/object updates by ID
- List extension or replacement
- Field removal via `-fieldname` syntax
- All room fields (exits, triggers, characters, objects, etc.)

Usage:
    python merge_mud_files.py <base_file> <revisions_file> [output_file]
    
Example:
    python merge_mud_files.py world_data/gloomy_graveyard.yaml revisions_gloomy_graveyard.yaml world_data/gloomy_graveyard_merged.yaml

Requirements:
    pip install ruamel.yaml
"""

import sys
import copy
import argparse
from pathlib import Path

import yaml
import re
import io

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False
    # Fallback types for when ruamel isn't available
    CommentedMap = dict
    CommentedSeq = list


# Custom YAML Dumper that properly indents list items with mappings
class IndentedDumper(yaml.SafeDumper):
    """Custom YAML dumper that properly indents sequences of mappings."""
    pass


def _str_representer(dumper, data):
    """Use literal block style for multi-line strings, otherwise default."""
    if '\n' in data:
        # Use literal block style (|) for multi-line strings
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


IndentedDumper.add_representer(str, _str_representer)


def extract_comments(file_path: str):
    """
    Extract comments from a YAML file for later restoration.
    
    Returns two dicts:
    - full_line_comments: {next_line_content_stripped: (indent, comment_lines)}
      Maps the content of the line following a comment block to the comment(s)
    - inline_comments: {line_content_stripped: comment}
      Maps line content (without comment) to its inline comment
    """
    full_line_comments = {}  # next_line_content -> (indent, [comment_lines])
    inline_comments = {}     # line_content -> comment
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return full_line_comments, inline_comments
    
    pending_comments = []  # Accumulate full-line comments
    pending_indent = ""
    
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n\r')
        
        # Check if this is a full-line comment (only whitespace before #)
        full_comment_match = re.match(r'^(\s*)#(.*)$', stripped)
        if full_comment_match:
            indent = full_comment_match.group(1)
            comment_text = '#' + full_comment_match.group(2)
            pending_comments.append(comment_text)
            if not pending_indent:
                pending_indent = indent
            continue
        
        # Check for inline comment (content followed by # comment)
        # Be careful not to match # inside quoted strings
        inline_match = re.match(r'^([^#]*[^#\s])\s+(#.*)$', stripped)
        if inline_match:
            content = inline_match.group(1).strip()
            comment = inline_match.group(2)
            # Use a normalized key (strip whitespace variations)
            inline_comments[content] = comment
        
        # If we have pending comments and hit a non-comment line, record them
        if pending_comments and stripped.strip():
            # Get the content portion of this line (strip inline comments if any)
            content_only = stripped
            if inline_match:
                content_only = inline_match.group(1)
            key = content_only.strip()
            if key:
                full_line_comments[key] = (pending_indent, pending_comments.copy())
            pending_comments = []
            pending_indent = ""
    
    return full_line_comments, inline_comments


def deduplicate_consecutive_comments(lines: list) -> list:
    """
    Remove consecutive duplicate comment lines.
    This handles cases where merges might introduce repeated comments.
    """
    result = []
    prev_line = None
    
    for line in lines:
        stripped = line.strip()
        # Check if this is a comment line
        if stripped.startswith('#'):
            # Skip if it's identical to the previous line
            if stripped == prev_line:
                continue
        prev_line = stripped
        result.append(line)
    
    return result


def restore_comments(yaml_output: str, full_line_comments: dict, inline_comments: dict) -> str:
    """
    Restore comments to YAML output.
    
    Args:
        yaml_output: The YAML string from PyYAML
        full_line_comments: {next_line_content: (indent, [comment_lines])}
        inline_comments: {line_content: comment}
    
    Returns:
        YAML string with comments restored where possible
    """
    if not full_line_comments and not inline_comments:
        return yaml_output
    
    lines = yaml_output.split('\n')
    result_lines = []
    
    for line in lines:
        stripped = line.rstrip()
        content_stripped = stripped.strip()
        
        # Check if we should insert full-line comments before this line
        if content_stripped in full_line_comments:
            indent, comment_lines = full_line_comments[content_stripped]
            # Use the indent from the current line if it makes more sense
            current_indent = re.match(r'^(\s*)', stripped).group(1)
            use_indent = current_indent if current_indent else indent
            # Deduplicate comment lines before adding
            seen_comments = set()
            for comment in comment_lines:
                if comment not in seen_comments:
                    seen_comments.add(comment)
                    result_lines.append(use_indent + comment)
        
        # Check if this line should have an inline comment
        if content_stripped in inline_comments:
            comment = inline_comments[content_stripped]
            # Add the inline comment with proper spacing
            result_lines.append(stripped + '  ' + comment)
        else:
            result_lines.append(stripped)
    
    # Final pass: remove any consecutive duplicate comment lines
    result_lines = deduplicate_consecutive_comments(result_lines)
    
    return '\n'.join(result_lines)


def create_yaml_handler():
    """Create a ruamel.yaml handler for loading (preserves comments)."""
    if RUAMEL_AVAILABLE:
        yaml_handler = YAML()
        yaml_handler.preserve_quotes = True
        yaml_handler.width = 4096
        return yaml_handler
    else:
        return None


def to_plain_python(obj):
    """
    Recursively convert ruamel.yaml CommentedMap/CommentedSeq to plain Python
    dict/list to strip all formatting metadata. Also converts ruamel's special
    scalar types to plain Python types.
    """
    if not RUAMEL_AVAILABLE:
        return obj
    
    from ruamel.yaml.comments import CommentedSeq, CommentedMap
    
    if isinstance(obj, CommentedMap):
        return {to_plain_python(key): to_plain_python(value) for key, value in obj.items()}
    elif isinstance(obj, CommentedSeq):
        return [to_plain_python(item) for item in obj]
    elif isinstance(obj, bool):
        # bool must be checked before int since bool is subclass of int
        return bool(obj)
    elif isinstance(obj, int) and type(obj) is not int:
        # Convert ruamel's special int types to plain int
        return int(obj)
    elif isinstance(obj, float) and type(obj) is not float:
        # Convert ruamel's special float types (ScalarFloat, etc.) to plain float
        return float(obj)
    elif isinstance(obj, str) and type(obj) is not str:
        # Convert ruamel's special string types (FoldedScalarString, LiteralScalarString, etc.)
        # to plain Python str
        return str(obj)
    else:
        return obj


def load_yaml(path: str, yaml_handler=None):
    """Load a YAML file, preserving comments if ruamel.yaml is available."""
    with open(path, 'r', encoding='utf-8') as f:
        if yaml_handler and RUAMEL_AVAILABLE:
            return yaml_handler.load(f)
        else:
            return yaml.safe_load(f)


def save_yaml(data, path: str, yaml_handler=None, original_path: str = None):
    """Save a YAML file with consistent formatting using PyYAML.
    
    Args:
        data: The data to save
        path: Output file path
        yaml_handler: Unused, kept for API compatibility
        original_path: Path to original file for comment extraction (optional)
    """
    output_dir = Path(path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract comments from original file if provided
    full_line_comments = {}
    inline_comments = {}
    if original_path:
        full_line_comments, inline_comments = extract_comments(original_path)
    
    # Convert to plain Python types to strip any ruamel formatting metadata
    plain_data = to_plain_python(data)
    
    # Dump to string first so we can restore comments
    string_output = io.StringIO()
    yaml.dump(
        plain_data, 
        string_output, 
        Dumper=IndentedDumper,
        sort_keys=False, 
        indent=2, 
        default_flow_style=False, 
        allow_unicode=True,
        width=4096
    )
    
    yaml_str = string_output.getvalue()
    
    # Restore comments
    if full_line_comments or inline_comments:
        yaml_str = restore_comments(yaml_str, full_line_comments, inline_comments)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(yaml_str)


def is_mapping(obj) -> bool:
    """Check if object is a dict-like mapping (handles both dict and CommentedMap)."""
    return isinstance(obj, (dict, CommentedMap)) if RUAMEL_AVAILABLE else isinstance(obj, dict)


def is_sequence(obj) -> bool:
    """Check if object is a list-like sequence (handles both list and CommentedSeq)."""
    if RUAMEL_AVAILABLE:
        return isinstance(obj, (list, CommentedSeq)) and not isinstance(obj, str)
    return isinstance(obj, list)


def create_mapping():
    """Create a new mapping (CommentedMap if ruamel available, else dict)."""
    return CommentedMap() if RUAMEL_AVAILABLE else {}


def create_sequence():
    """Create a new sequence (CommentedSeq if ruamel available, else list)."""
    return CommentedSeq() if RUAMEL_AVAILABLE else []


def copy_item(item):
    """
    Deep copy an item, preserving ruamel.yaml types and comments.
    """
    if RUAMEL_AVAILABLE:
        if isinstance(item, CommentedMap):
            result = CommentedMap()
            # Copy comments from the original
            if hasattr(item, 'ca'):
                result.ca.comment = copy.copy(item.ca.comment) if item.ca.comment else None
                result.ca.items.update(copy.copy(item.ca.items))
            for key, value in item.items():
                result[key] = copy_item(value)
            return result
        elif isinstance(item, CommentedSeq):
            result = CommentedSeq()
            if hasattr(item, 'ca'):
                result.ca.comment = copy.copy(item.ca.comment) if item.ca.comment else None
                result.ca.items.update(copy.copy(item.ca.items))
            for value in item:
                result.append(copy_item(value))
            return result
    
    # Fall back to regular copy for non-ruamel types
    if is_mapping(item):
        result = create_mapping()
        for key, value in item.items():
            result[key] = copy_item(value)
        return result
    elif is_sequence(item):
        result = create_sequence()
        for value in item:
            result.append(copy_item(value))
        return result
    else:
        return copy.copy(item) if hasattr(item, '__copy__') else item


def deep_merge(base, revision, list_strategy: str = "extend"):
    """
    Recursively merge revision dict into base dict, preserving comments.
    
    Args:
        base: The original dictionary
        revision: The revision dictionary with updates
        list_strategy: How to handle lists - "extend" (default) or "replace"
        
    Returns:
        Merged dictionary
        
    Special syntax in revision:
        - Keys starting with '-' remove that key from base (e.g., "-disarm" removes "disarm")
        - "__list_strategy__": "replace" in a dict makes child lists replace instead of extend
        - "__replace__": true on a dict replaces the entire dict instead of merging
    """
    if base is None:
        return copy_item(revision)
    if revision is None:
        return base
    
    result = copy_item(base)
    
    # Check for full replacement marker
    if is_mapping(revision) and revision.get("__replace__"):
        rev_copy = copy_item(revision)
        if "__replace__" in rev_copy:
            del rev_copy["__replace__"]
        return rev_copy
    
    # Check for list strategy override
    current_list_strategy = list_strategy
    if is_mapping(revision) and "__list_strategy__" in revision:
        current_list_strategy = revision["__list_strategy__"]
    
    for key in revision:
        # Skip meta keys
        if isinstance(key, str) and key.startswith("__") and key.endswith("__"):
            continue
        
        rev_value = revision[key]
            
        # Handle removal syntax: -keyname removes keyname
        if isinstance(key, str) and key.startswith("-"):
            actual_key = key[1:]
            if actual_key in result:
                del result[actual_key]
            continue
        
        if key not in result:
            # Key doesn't exist in base, just add it
            result[key] = copy_item(rev_value)
        elif is_mapping(result[key]) and is_mapping(rev_value):
            # Both are dicts, recurse
            result[key] = deep_merge(result[key], rev_value, current_list_strategy)
        elif is_sequence(result[key]) and is_sequence(rev_value):
            # Both are lists
            if current_list_strategy == "replace":
                result[key] = copy_item(rev_value)
            else:
                # Extend, avoiding exact duplicates
                existing_items = list(result[key])
                for item in rev_value:
                    if item not in existing_items:
                        result[key].append(copy_item(item))
        else:
            # Different types or scalars - revision wins
            result[key] = copy_item(rev_value)
    
    return result


def find_by_id(items, item_id: str) -> tuple:
    """Find an item in a list by its 'id' field. Returns (index, item) or (-1, None)."""
    for i, item in enumerate(items):
        if is_mapping(item) and item.get("id") == item_id:
            return i, item
    return -1, None


def merge_character_or_object_list(base_list, revision_list):
    """
    Merge a list of characters or objects by ID.
    
    - If revision item has an ID that exists in base, deep merge them
    - If revision item has a new ID, append it
    - If revision item has "__remove__": true, remove that ID from base
    """
    result = copy_item(base_list) if base_list else create_sequence()
    
    for rev_item in (revision_list or []):
        if not is_mapping(rev_item):
            result.append(copy_item(rev_item))
            continue
            
        item_id = rev_item.get("id")
        if not item_id:
            # No ID, just append
            result.append(copy_item(rev_item))
            continue
        
        idx, existing = find_by_id(result, item_id)
        
        if rev_item.get("__remove__"):
            # Remove this item
            if idx >= 0:
                del result[idx]
            continue
        
        if existing is not None:
            # Merge into existing
            result[idx] = deep_merge(existing, rev_item)
        else:
            # New item, append
            result.append(copy_item(rev_item))
    
    return result


def merge_rooms(base_rooms, revision_rooms):
    """
    Merge room definitions.
    
    For existing rooms: deep merge all fields (exits, triggers, characters, objects, etc.)
    For new rooms: add them entirely
    """
    result = copy_item(base_rooms) if base_rooms else create_mapping()
    
    if not revision_rooms:
        return result
    
    for room_id in revision_rooms:
        rev_room = revision_rooms[room_id]
        
        if is_mapping(rev_room) and rev_room.get("__remove__"):
            # Remove this room
            if room_id in result:
                del result[room_id]
            continue
            
        if room_id in result:
            # Existing room - merge fields
            base_room = result[room_id]
            
            for field in rev_room:
                if isinstance(field, str) and field.startswith("__"):
                    continue
                
                rev_value = rev_room[field]
                    
                if field == "exits":
                    # Exits are a dict, merge them
                    if "exits" not in base_room:
                        base_room["exits"] = create_mapping()
                    base_room["exits"] = deep_merge(base_room["exits"], rev_value)
                elif field == "triggers":
                    # Triggers are a list with IDs, merge by ID
                    if "triggers" not in base_room:
                        base_room["triggers"] = create_sequence()
                    base_room["triggers"] = merge_character_or_object_list(
                        base_room["triggers"], rev_value
                    )
                elif field == "characters":
                    # Characters in rooms are simple dicts with id/quantity, merge by id
                    if "characters" not in base_room:
                        base_room["characters"] = create_sequence()
                    base_room["characters"] = merge_character_or_object_list(
                        base_room["characters"], rev_value
                    )
                elif field == "objects":
                    # Objects in rooms
                    if "objects" not in base_room:
                        base_room["objects"] = create_sequence()
                    base_room["objects"] = merge_character_or_object_list(
                        base_room["objects"], rev_value
                    )
                elif is_mapping(base_room.get(field)) and is_mapping(rev_value):
                    base_room[field] = deep_merge(base_room[field], rev_value)
                elif is_sequence(base_room.get(field)) and is_sequence(rev_value):
                    for item in rev_value:
                        if item not in base_room[field]:
                            base_room[field].append(copy_item(item))
                else:
                    # Scalar or type mismatch - revision wins
                    base_room[field] = copy_item(rev_value)
        else:
            # New room - add entirely
            result[room_id] = copy_item(rev_room)
    
    return result


def merge_zones(base_zones, revision_zones):
    """Merge ZONES sections."""
    result = copy_item(base_zones) if base_zones else create_mapping()
    
    if not revision_zones:
        return result
    
    for zone_id in revision_zones:
        rev_zone = revision_zones[zone_id]
        
        if zone_id not in result:
            # Entirely new zone
            result[zone_id] = copy_item(rev_zone)
            continue
        
        base_zone = result[zone_id]
        
        # Merge common_knowledge (dict)
        if "common_knowledge" in rev_zone:
            if "common_knowledge" not in base_zone:
                base_zone["common_knowledge"] = create_mapping()
            base_zone["common_knowledge"] = deep_merge(
                base_zone["common_knowledge"], 
                rev_zone["common_knowledge"]
            )
        
        # Merge quest_variables (dict)
        if "quest_variables" in rev_zone:
            if "quest_variables" not in base_zone:
                base_zone["quest_variables"] = create_mapping()
            base_zone["quest_variables"] = deep_merge(
                base_zone["quest_variables"],
                rev_zone["quest_variables"]
            )
        
        # Merge rooms
        if "rooms" in rev_zone:
            base_zone["rooms"] = merge_rooms(
                base_zone.get("rooms"),
                rev_zone["rooms"]
            )
        
        # Merge any other zone-level fields
        for field in rev_zone:
            if field not in ["common_knowledge", "quest_variables", "rooms", "name", "description"]:
                if field not in base_zone:
                    base_zone[field] = copy_item(rev_zone[field])
                elif is_mapping(base_zone[field]):
                    base_zone[field] = deep_merge(base_zone[field], rev_zone[field])
                elif is_sequence(base_zone[field]):
                    for item in rev_zone[field]:
                        if item not in base_zone[field]:
                            base_zone[field].append(copy_item(item))
                else:
                    base_zone[field] = rev_zone[field]
            elif field in ["name", "description"] and rev_zone.get(field):
                # Allow overriding name/description if specified
                base_zone[field] = rev_zone[field]
    
    return result


def merge_section_list(base_list, revision_list, item_key: str):
    """
    Merge a top-level section like CHARACTERS or OBJECTS.
    
    These have structure: [{zone: "zone_name", characters: [...]}]
    """
    result = copy_item(base_list) if base_list else create_sequence()
    
    if not revision_list:
        return result
    
    for rev_entry in revision_list:
        if not is_mapping(rev_entry):
            continue
            
        zone_name = rev_entry.get("zone")
        if not zone_name:
            continue
        
        # Find matching zone entry in base
        found = False
        for base_entry in result:
            if is_mapping(base_entry) and base_entry.get("zone") == zone_name:
                # Merge the items list
                if item_key not in base_entry:
                    base_entry[item_key] = create_sequence()
                base_entry[item_key] = merge_character_or_object_list(
                    base_entry.get(item_key),
                    rev_entry.get(item_key)
                )
                found = True
                break
        
        if not found:
            # New zone entry, add it
            result.append(copy_item(rev_entry))
    
    return result


def merge_mud_files(base_path: str, revisions_path: str, output_path: str) -> bool:
    """
    Merge a revisions file into a base MUD zone file.
    
    Args:
        base_path: Path to the original zone file
        revisions_path: Path to the revisions file
        output_path: Path for the merged output file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create YAML handler (for comment preservation)
        yaml_handler = create_yaml_handler()
        
        if not RUAMEL_AVAILABLE:
            print("[WARNING] ruamel.yaml not installed - comments will NOT be preserved!")
            print("          Install with: pip install ruamel.yaml")
        
        # Load files
        base = load_yaml(base_path, yaml_handler)
        if base is None:
            base = create_mapping()
        
        revisions = load_yaml(revisions_path, yaml_handler)
        if revisions is None:
            revisions = create_mapping()
        
        # Merge ZONES
        if "ZONES" in revisions:
            base["ZONES"] = merge_zones(base.get("ZONES"), revisions["ZONES"])
        
        # Merge CHARACTERS
        if "CHARACTERS" in revisions:
            base["CHARACTERS"] = merge_section_list(
                base.get("CHARACTERS"),
                revisions["CHARACTERS"],
                "characters"
            )
        
        # Merge OBJECTS
        if "OBJECTS" in revisions:
            base["OBJECTS"] = merge_section_list(
                base.get("OBJECTS"),
                revisions["OBJECTS"],
                "objects"
            )
        
        # Write output (pass base_path for comment restoration)
        save_yaml(base, output_path, yaml_handler, original_path=base_path)
        
        print(f"[OK] Successfully merged: {output_path}")
        print("     Comments preserved.")
        return True
        
    except FileNotFoundError as e:
        print(f"[ERROR] File not found - {e.filename}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Merge MUD zone revision files into base zone files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s world_data/zone.yaml revisions.yaml output.yaml
  %(prog)s world_data/zone.yaml revisions.yaml  # Outputs to zone_merged.yaml
  
See README-merge-mud-files.md for detailed documentation.

Note: Install ruamel.yaml to preserve comments: pip install ruamel.yaml
        """
    )
    parser.add_argument("base_file", help="Path to the base zone YAML file")
    parser.add_argument("revisions_file", help="Path to the revisions YAML file")
    parser.add_argument("output_file", nargs="?", help="Output file path (optional)")
    parser.add_argument("--in-place", "-i", action="store_true", 
                        help="Modify the base file in place (dangerous!)")
    
    args = parser.parse_args()
    
    # Determine output path
    if args.in_place:
        output_path = args.base_file
    elif args.output_file:
        output_path = args.output_file
    else:
        # Default: base_merged.yaml
        base = Path(args.base_file)
        output_path = str(base.parent / f"{base.stem}_merged{base.suffix}")
    
    success = merge_mud_files(args.base_file, args.revisions_file, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
