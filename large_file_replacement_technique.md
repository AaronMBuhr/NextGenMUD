# YAML Trigger ID and Indentation Fix for NextGenMUD

Our successful approach for updating trigger IDs and fixing indentation in YAML files used a PowerShell script with multiple regex-based replacements. Here's the detailed technique:

## Problem Areas Addressed
1. Improper indentation of "catch_say_sewer_echo" triggers
2. Non-unique timer_tick IDs across the file
3. Inconsistent formatting in various trigger types

## Solution Steps

1. **Backup Protection**: Create a backup of the target file before any modifications
2. **Reset Existing IDs**: Reset any existing timer_tick IDs to a standard format to avoid compounding changes
3. **Fix Generic Catch Triggers**: Replace generic triggers (catch_look, catch_say, catch_any) with specific ones based on predicates
4. **Room-Based Processing**:
   - Parse the file to identify each room section
   - Handle the special case of the first room (sewer_entrance)
   - Extract all timer_tick triggers for each room
   - Apply unique naming with format: `timer_tick_[room_id]_[sequence_number]`
5. **Fix Indentation Issues**:
   - Apply consistent indentation for all trigger types
   - Special handling for catch_say_sewer_echo formatting
6. **Apply Content Replacements**:
   - Replace sections of the file with updated versions
   - Write the modified content back to the file

## Key Technical Elements

- **Regex Pattern Matching**: Used to identify specific sections in the YAML file
- **Sequential Processing**: Room-by-room approach to ensure context-aware replacements
- **Content Replacement**: Full-section replacements rather than line-by-line to maintain structure
- **ID Generation Logic**: Combined room identifiers with sequential numbering

The script successfully creates unique, descriptive trigger IDs for all rooms while maintaining consistent YAML formatting.

## Preventing Duplicates: Detailed Pattern Matching Strategy

### Identifying Rooms

To properly process each room independently and avoid duplicates, we used this regex pattern:

```powershell
'(\s+)([a-zA-Z_]+):\s+name: ([^\n]+).*?(triggers:.*?)(?=\s+creatures:|$)'
```

This pattern:
- Captures the indentation level `(\s+)`
- Identifies the room ID `([a-zA-Z_]+)`
- Gets the room name `([^\n]+)`
- Extracts the entire triggers section `(triggers:.*?)`
- Uses a positive lookahead `(?=\s+creatures:|$)` to properly bound the section

### Extracting Triggers Within Rooms

To identify timer_tick triggers without duplicating them:

```powershell
'(- id: timer_tick_water_sound\s+type: timer_tick.*?)(?=\s+- id:|$)'
```

This pattern:
- Captures a complete trigger definition starting with the ID
- Uses positive lookahead `(?=\s+- id:|$)` to stop at the next trigger or end of section
- Processes each match separately to ensure one-for-one replacements

### Preventing Duplicate Processing

Three key mechanisms prevented duplication:

1. **Reset existing timer IDs** before processing:
   ```powershell
   $content = $content -replace '- id: timer_tick_[a-z_0-9]+', '- id: timer_tick_water_sound'
   ```
   This standardizes all existing IDs before making room-specific changes.

2. **Whole-section replacement** instead of global search/replace:
   ```powershell
   $updatedTriggersSection = $updatedTriggersSection.Replace($timerTickTrigger, $updatedTimerTickTrigger)
   ```
   This replaces each specific trigger once, not all instances in the file.

3. **Sequential numbering within each room**:
   ```powershell
   for ($i = 0; $i -lt $timerTickMatches.Count; $i++) {
       $newId = "timer_tick_${roomId}_$($i+1)"
   }
   ```
   Each room's triggers get sequential numbers (1,2,3...) starting fresh with each room.

### Special Case Handling

For the first room (sewer_entrance), we added this logic:

```powershell
if ($roomId -eq "city_sewers") {
    $roomId = "sewer_entrance"
}
```

This prevents incorrectly using the zone ID instead of the room ID for the first room's triggers.

By carefully matching sections, applying replacements within specific contexts, and handling special cases, we ensured unique IDs across the entire file while maintaining consistent formatting. 