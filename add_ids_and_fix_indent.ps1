# add_ids_and_fix_indent.ps1
# Correctly adds missing trigger IDs and ensures proper indentation

# Define file paths
$filePath = "world_data/enchanted_forest.yaml" # Target the correct file
$backupPath = "$filePath.corrected.bak"

# Create backup
Write-Host "Backing up $filePath to $backupPath..."
if (Test-Path $filePath) {
    Copy-Item -Path $filePath -Destination $backupPath -Force -ErrorAction SilentlyContinue
} else {
    Write-Error "Input file not found: $filePath"
    exit 1
}


# Read file content
try {
    $lines = Get-Content -Path $filePath -Encoding UTF8 # Specify UTF8 encoding
} catch {
    Write-Error "Failed to read the input file: $filePath. Error: $($_.Exception.Message)"
    exit 1
}


# Prepare new content list and track generated IDs
$newLines = [System.Collections.Generic.List[string]]::new()
$generatedIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

# Pre-populate with existing IDs
Write-Host "Scanning for existing trigger IDs..."
foreach ($line in $lines) {
    if ($line.TrimStart().StartsWith("- id:")) {
        $existingIdMatch = [regex]::Match($line, '- id:\s*(.*)')
        if ($existingIdMatch.Success) {
            $existingId = $existingIdMatch.Groups[1].Value.Trim()
            if (-not [string]::IsNullOrWhiteSpace($existingId) -and -not $generatedIds.Contains($existingId)) {
                 $generatedIds.Add($existingId) | Out-Null
            }
        }
    }
}
Write-Host "Finished scanning existing IDs. Found $($generatedIds.Count)."


# Process lines to add missing IDs and fix structure
Write-Host "Processing lines to add missing trigger IDs and fix structure..."
$i = 0
while ($i -lt $lines.Count) {
    $currentLine = $lines[$i]
    $trimmedLine = $currentLine.TrimStart()
    $lineProcessed = $false # Flag to indicate if we handled the line inside the loop

    # Check if the line starts a trigger definition ('- type:')
    if ($trimmedLine.StartsWith("- type:")) {
        # Check the previous non-empty line for an existing ID
        $prevIndex = $i - 1
        $prevLineTrimmed = ""
        while ($prevIndex -ge 0) {
             $prevLineTrimmed = $lines[$prevIndex].Trim()
             if ($prevLineTrimmed) { break }
             $prevIndex--
        }

        # Determine if an ID needs to be added
        $needsId = $true
        if ($prevLineTrimmed.StartsWith("- id:")) {
             $needsId = $false
        }

        if ($needsId) {
            # --- Trigger needs an ID - Process and Fix ---
            Write-Host "Found trigger needing ID at line $($i + 1): $trimmedLine"

            # Extract indentation and type
            $indentation = $currentLine -replace '(\s*).*', '$1'
            $typeMatch = [regex]::Match($trimmedLine, '- type:\s*(\w+)')
            if (-not $typeMatch.Success) {
                 Write-Warning "Could not parse trigger type at line $($i + 1). Skipping ID generation for this trigger."
                 # Add original line and continue if parse fails
                 $newLines.Add($currentLine)
                 $i++
                 continue
            }
            $triggerType = $typeMatch.Groups[1].Value
            $typePart = $trimmedLine.Substring(1).TrimStart() # Get "type: ..." part

            $baseId = ""
            # ... [Logic to determine baseId based on context - same as before] ...
            # Look ahead within the trigger definition for context (predicate or echo)
            $lookAheadIndex = $i + 1
            $scriptBlockFound = $false
            $criteriaBlockFound = $false
            $maxLookAhead = 20 # Limit look ahead
            $linesSearched = 0
            while ($lookAheadIndex -lt $lines.Count -and $linesSearched -lt $maxLookAhead) {
                $nextLine = $lines[$lookAheadIndex]
                $trimmedNextLine = $nextLine.TrimStart()
                $nextIndentation = $nextLine -replace '(\s*).*', '$1'
                if ($nextIndentation.Length -lt $indentation.Length) { break }
                if ($nextIndentation.Length -eq $indentation.Length -and $trimmedNextLine.StartsWith("- ")) { break }
                if ($trimmedNextLine.StartsWith("criteria:")) { $criteriaBlockFound = $true }
                if ($criteriaBlockFound -and $triggerType -like 'catch_*' -and $trimmedNextLine.StartsWith("predicate:")) {
                    $predMatch = [regex]::Match($trimmedNextLine, 'predicate:\s*"?(.*?)"?\s*$')
                    if ($predMatch.Success) {
                         $context = $predMatch.Groups[1].Value.Trim()
                         $sanitizedContext = $context.ToLower() -replace '[^a-z0-9_]+', '_' -replace '_+', '_' -replace '^_*|_*$'
                         if (-not [string]::IsNullOrWhiteSpace($sanitizedContext)) { $baseId = "${triggerType}_${sanitizedContext}" }
                         break
                    }
                }
                if ($trimmedNextLine.StartsWith("script:")) { $scriptBlockFound = $true }
                if ($scriptBlockFound -and $trimmedNextLine.StartsWith("echo ")) {
                    $context = $trimmedNextLine -replace 'echo\s+',''
                    $words = ($context -split '\s+' | Where-Object {$_})
                    if ($words.Count -gt 0) {
                         $wordCount = [System.Math]::Min($words.Count, 3)
                         $sanitizedContext = ($words[0..($wordCount-1)] -join '_').ToLower() -replace '[^a-z0-9_]+', '_' -replace '_+', '_' -replace '^_*|_*$'
                         if (-not [string]::IsNullOrWhiteSpace($sanitizedContext)) { $baseId = "${triggerType}_${sanitizedContext}" }
                    }
                    break
                }
                $lookAheadIndex++; $linesSearched++
            }
            if ([string]::IsNullOrWhiteSpace($baseId)) {
                $baseId = "${triggerType}_trigger_$($i+1)"
                Write-Host "  - Could not determine context, using fallback base ID: $baseId"
            }
             # ... [End of context logic] ...


            # Ensure ID is unique
            $newId = $baseId
            $suffixCounter = 1
            while ($generatedIds.Contains($newId)) {
                $suffixCounter++
                $newId = "${baseId}_${suffixCounter}"
                Write-Host "  - ID '$($newId -replace "_$suffixCounter", '')' collision, trying '$newId'"
            }
            $generatedIds.Add($newId) | Out-Null

            # Add the CORRECTED structure to newLines
            $newLines.Add("$indentation- id: $newId")     # Add the list item start with ID
            $newLines.Add("$indentation  $typePart")    # Add the type part, indented correctly

            Write-Host "  - Adding ID '$newId' and fixing structure for original line $($i + 1)"
            $lineProcessed = $true # Mark line as processed
        }
    }

    # If the line wasn't a '- type:' needing an ID, or if it was handled above, add it (unless handled)
    if (-not $lineProcessed) {
        $newLines.Add($currentLine)
    }

    $i++ # Move to the next line
}

# Write the modified content back to the file
Write-Host "Writing changes back to $filePath..."
try {
    Set-Content -Path $filePath -Value $newLines -Encoding UTF8
    Write-Host "Script finished successfully. Trigger IDs added and structure fixed in $filePath."
    Write-Host "Original file backed up at $backupPath."
} catch {
     Write-Error "Failed to write changes back to $filePath. Error: $($_.Exception.Message)"
     Write-Error "The original file is backed up at $backupPath. The modified content was not saved."
     exit 1
} 