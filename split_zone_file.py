#!/usr/bin/env python3
import sys
import os
import yaml
from pathlib import Path
from itertools import zip_longest

def grouper(iterable, n, fillvalue=None):
    """Group iterable into chunks of n items."""
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

def split_yaml_file(file_path):
    # Load the YAML file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        print(f"Loaded YAML file: {file_path}")
        print(f"Top level keys: {list(data.keys())}")
        
        # Ensure we have an output directory
        output_dir = Path("split_zones")
        output_dir.mkdir(exist_ok=True)
        
        # Get the base filename without extension
        base_name = Path(file_path).stem
        
        # Check for alternate structure where zone info is directly at top level
        if 'name' in data and 'rooms' in data and isinstance(data['rooms'], dict):
            print("Found direct zone structure at top level")
            # Create a synthetic ZONES structure
            data = {'ZONES': {base_name: data}}
            print(f"Created synthetic ZONES structure with zone id: {base_name}")
        
        # Process ZONES section
        if 'ZONES' in data:
            print(f"Found ZONES section with {len(data['ZONES'])} zones")
            for zone_id, zone_data in data['ZONES'].items():
                print(f"Processing zone: {zone_id}")
                print(f"Zone keys: {list(zone_data.keys())}")
                
                # Check if rooms exist
                if 'rooms' in zone_data:
                    rooms = zone_data['rooms']
                    print(f"Found 'rooms' element with type: {type(rooms)}")
                    
                    if not isinstance(rooms, dict):
                        print(f"WARNING: 'rooms' is not a dictionary! It's a {type(rooms)}.")
                        continue
                    
                    print(f"Found {len(rooms)} rooms in zone {zone_id}")
                    print(f"Room keys: {list(rooms.keys())[:5]}..." if len(rooms) > 5 else f"Room keys: {list(rooms.keys())}")
                    
                    # Double check room structure
                    for room_id, room_data in list(rooms.items())[:3]:  # Check first 3 rooms
                        print(f"Room '{room_id}' type: {type(room_data)}")
                        if isinstance(room_data, dict):
                            print(f"  Room keys: {list(room_data.keys())}")
                    
                    # Split rooms into chunks of 10
                    room_items = list(rooms.items())
                    chunks = list(grouper(room_items, 10))
                    print(f"Split into {len(chunks)} chunks")
                    
                    for i, chunk in enumerate(chunks, 1):
                        # Filter out None values that might come from zip_longest
                        chunk = [item for item in chunk if item is not None]
                        
                        # Create a dictionary from the chunk
                        room_chunk = dict(chunk)
                        
                        # Create the output data structure
                        output_data = {
                            'ZONES': {
                                zone_id: {
                                    'rooms': room_chunk
                                }
                            }
                        }
                        
                        # Add zone metadata if present
                        if 'name' in zone_data:
                            output_data['ZONES'][zone_id]['name'] = zone_data['name']
                        if 'description' in zone_data:
                            output_data['ZONES'][zone_id]['description'] = zone_data['description']
                        
                        # Create the new filename
                        output_filename = f"{base_name}_zones_{i:02d}.yaml"
                        full_path = output_dir / output_filename
                        
                        print(f"Writing {len(room_chunk)} rooms to {full_path}")
                        
                        # Save the chunk to a new file
                        with open(full_path, 'w', encoding='utf-8') as f:
                            yaml.dump(output_data, f, sort_keys=False, allow_unicode=True)
                        
                        print(f"Created {full_path} with {len(room_chunk)} rooms")
        else:
            print("No ZONES section found in the YAML file")
        
        # Process CHARACTERS section
        if 'CHARACTERS' in data:
            print(f"Found CHARACTERS section with {len(data['CHARACTERS'])} entries")
            # Group characters by zone
            characters_by_zone = {}
            
            for char_entry in data['CHARACTERS']:
                print(f"Processing character entry: {char_entry.keys() if isinstance(char_entry, dict) else 'not a dict'}")
                if isinstance(char_entry, dict) and 'zone' in char_entry:
                    zone_id = char_entry['zone']
                    print(f"Found characters for zone: {zone_id}")
                    
                    if 'characters' in char_entry:
                        chars = char_entry['characters']
                        print(f"Found {len(chars)} characters")
                        if zone_id not in characters_by_zone:
                            characters_by_zone[zone_id] = []
                        characters_by_zone[zone_id].extend(chars)
                    else:
                        print(f"No 'characters' key in character entry for zone {zone_id}")
            
            # Now process each zone's characters
            for zone_id, characters in characters_by_zone.items():
                print(f"Processing {len(characters)} characters in zone {zone_id}")
                
                # Split characters into chunks of 10
                for i, chunk in enumerate(grouper(characters, 10), 1):
                    # Filter out None values
                    chunk = [item for item in chunk if item is not None]
                    
                    # Create the output data structure
                    output_data = {
                        'CHARACTERS': [
                            {
                                'zone': zone_id,
                                'characters': chunk
                            }
                        ]
                    }
                    
                    # Create the new filename
                    output_filename = f"{base_name}_characters_{i:02d}.yaml"
                    full_path = output_dir / output_filename
                    
                    print(f"Writing {len(chunk)} characters to {full_path}")
                    
                    # Save the chunk to a new file
                    with open(full_path, 'w', encoding='utf-8') as f:
                        yaml.dump(output_data, f, sort_keys=False, allow_unicode=True)
                    
                    print(f"Created {full_path} with {len(chunk)} characters")
        else:
            print("No CHARACTERS section found in the YAML file")
        
        # Process OBJECTS section (if it exists)
        if 'OBJECTS' in data:
            print(f"Found OBJECTS section with {len(data['OBJECTS'])} entries")
            # Group objects by zone
            objects_by_zone = {}
            
            for obj_entry in data['OBJECTS']:
                print(f"Processing object entry: {obj_entry.keys() if isinstance(obj_entry, dict) else 'not a dict'}")
                if isinstance(obj_entry, dict) and 'zone' in obj_entry:
                    zone_id = obj_entry['zone']
                    print(f"Found objects for zone: {zone_id}")
                    
                    if 'objects' in obj_entry:
                        objs = obj_entry['objects']
                        print(f"Found {len(objs)} objects")
                        if zone_id not in objects_by_zone:
                            objects_by_zone[zone_id] = []
                        objects_by_zone[zone_id].extend(objs)
                    else:
                        print(f"No 'objects' key in object entry for zone {zone_id}")
            
            # Now process each zone's objects
            for zone_id, objects in objects_by_zone.items():
                print(f"Processing {len(objects)} objects in zone {zone_id}")
                
                # Split objects into chunks of 10
                for i, chunk in enumerate(grouper(objects, 10), 1):
                    # Filter out None values
                    chunk = [item for item in chunk if item is not None]
                    
                    # Create the output data structure
                    output_data = {
                        'OBJECTS': [
                            {
                                'zone': zone_id,
                                'objects': chunk
                            }
                        ]
                    }
                    
                    # Create the new filename
                    output_filename = f"{base_name}_objects_{i:02d}.yaml"
                    full_path = output_dir / output_filename
                    
                    print(f"Writing {len(chunk)} objects to {full_path}")
                    
                    # Save the chunk to a new file
                    with open(full_path, 'w', encoding='utf-8') as f:
                        yaml.dump(output_data, f, sort_keys=False, allow_unicode=True)
                    
                    print(f"Created {full_path} with {len(chunk)} objects")
        else:
            print("No OBJECTS section found in the YAML file")
            
        # If we didn't process anything, dump the file structure
        if 'ZONES' not in data and 'CHARACTERS' not in data and 'OBJECTS' not in data:
            print("WARNING: Could not find expected sections in the YAML file")
            print("File structure:")
            
            def print_structure(data, prefix=""):
                if isinstance(data, dict):
                    for key, value in data.items():
                        print(f"{prefix}{key}: {type(value)}")
                        if isinstance(value, (dict, list)):
                            print_structure(value, prefix + "  ")
                elif isinstance(data, list):
                    print(f"{prefix}List with {len(data)} items")
                    if data and isinstance(data[0], (dict, list)):
                        print_structure(data[0], prefix + "  [0] ")
            
            print_structure(data)
    
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python split_zone_file.py <yaml_file>")
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    if not os.path.exists(yaml_file):
        print(f"Error: File {yaml_file} not found")
        sys.exit(1)
    
    # Make sure we're not modifying the input file
    original_stats = os.stat(yaml_file)
    
    split_yaml_file(yaml_file)
    
    # Verify the input file wasn't modified
    after_stats = os.stat(yaml_file)
    if original_stats.st_mtime != after_stats.st_mtime or original_stats.st_size != after_stats.st_size:
        print("WARNING: The input file was modified, which should not happen!") 