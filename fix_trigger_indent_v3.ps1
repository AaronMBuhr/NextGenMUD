# Define file paths
$filePath = "world_data/gloomy_graveyard.yaml"
$backupPath = "$filePath.fix_indent_v3.bak"

# Validate file exists
if (-not (Test-Path $filePath)) {
    Write-Error "File not found: $filePath"
    exit 1
}

# Create backup
Write-Host "Backing up $filePath to $backupPath..."
Copy-Item -Path $filePath -Destination $backupPath -Force -ErrorAction SilentlyContinue

# Read file lines
Write-Host "Reading file lines: $filePath..."
try {
    $lines = Get-Content -Path $filePath -Encoding UTF8
} catch {
    Write-Error "Failed to read the input file: $filePath. Error: $($_.Exception.Message)"
    exit 1
}

$newLines = [System.Collections.Generic.List[string]]::new()
$linesFixed = 0
$i = 0

Write-Host "Processing lines to fix indentation..."
while ($i -lt $lines.Count) {
    $currentLine = $lines[$i]
    $nextLine = if (($i + 1) -lt $lines.Count) { $lines[$i + 1] } else { $null }

    # Check current line for '- id: ...'
    $idPattern = '^(\s+)-\s+(id:\s*.*)$'
    $matchId = [regex]::Match($currentLine, $idPattern)

    if ($matchId.Success -and $nextLine -ne $null) {
        $idIndentation = $matchId.Groups[1].Value
        $idPart = $matchId.Groups[2].Value

        # Check next line for '- type: ...' using string methods for robustness
        $nextLineTrimmed = $nextLine.TrimStart()
        $expectedTypePrefix = "$idIndentation- " # Check if next line starts with same indent + dash + space

        if ($nextLine.StartsWith($expectedTypePrefix) -and $nextLineTrimmed.StartsWith("type:")) {
             # --- Found the pattern to fix ---

             # Extract the 'type: ...' part after the prefix
             $typePart = $nextLine.Substring($expectedTypePrefix.Length).TrimStart()

             # Add the current '- id: ...' line as is
             $newLines.Add($currentLine)

             # Construct the fixed 'type: ...' line (indent + 2 spaces + type part)
             $fixedTypeLine = "$idIndentation  $typePart" # Note 2 spaces for alignment
             $newLines.Add($fixedTypeLine)

             Write-Host "Fixed indentation at lines $($i+1) -> $($i+2)"
             $linesFixed++
             $i += 2 # Increment index by 2 since we processed two lines
             continue # Continue to next iteration
        }
    }

    # If the pattern wasn't found, just add the current line and move to the next
    $newLines.Add($currentLine)
    $i++
}

if ($linesFixed -gt 0) {
    Write-Host "$linesFixed indentation issues fixed."
    # Write the modified content back to the file
    Write-Host "Writing changes back to $filePath..."
    try {
        Set-Content -Path $filePath -Value $newLines -Encoding UTF8
        Write-Host "Script finished successfully. Indentation fixed in $filePath."
        Write-Host "Original file backed up at $backupPath."
    } catch {
         Write-Error "Failed to write changes back to $filePath. Error: $($_.Exception.Message)"
         Write-Error "The original file is backed up at $backupPath. The modified content was not saved."
         exit 1
    }
} else {
    Write-Host "No indentation issues requiring fixes were found."
} 