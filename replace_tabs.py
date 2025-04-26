#!/usr/bin/env python3
import argparse
import os
import shutil
import sys


def replace_tabs(file_path, num_spaces=4, replacement=' ', create_backup=True):
    """
    Replace tabs in a file with spaces or a custom replacement string.
    
    Args:
        file_path: Path to the file to process
        num_spaces: Number of times to repeat the replacement string
        replacement: String to use as replacement for tabs
        create_backup: Whether to create a backup file
        
    Returns:
        int: Number of tabs replaced
    """
    # Create backup
    if create_backup:
        backup_path = file_path + '.bak'
        shutil.copy2(file_path, backup_path)
        print(f"Original file backed up to {backup_path}")
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count tabs in original content
    tab_count = content.count('\t')
    
    # Replace tabs with spaces or replacement string
    replaced_content = content.replace('\t', replacement * num_spaces)
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(replaced_content)
    
    print(f"Processed {file_path}")
    
    return tab_count


def main():
    parser = argparse.ArgumentParser(
        description="Replace tabs with spaces or custom string in a file"
    )
    parser.add_argument(
        "file", 
        help="File to process"
    )
    parser.add_argument(
        "-n", "--num-spaces", 
        type=int, 
        default=4,
        help="Number of spaces to replace each tab (default: 4)"
    )
    parser.add_argument(
        "-r", "--replacement", 
        default=' ',
        help="Replacement string for tabs (default: space)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup file"
    )
    
    args = parser.parse_args()
    
    # If replacement is specified but num_spaces isn't explicitly set,
    # default to 1 instead of 4
    num_spaces = 1 if args.replacement != ' ' and '-n' not in sys.argv and '--num-spaces' not in sys.argv else args.num_spaces
    
    if not os.path.isfile(args.file):
        print(f"Error: {args.file} is not a valid file")
        return 1
    
    tabs_replaced = replace_tabs(args.file, num_spaces, args.replacement, not args.no_backup)
    print(f"Replaced {tabs_replaced} tab{'s' if tabs_replaced != 1 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 