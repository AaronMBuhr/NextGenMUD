# Define file paths
$filePath = "world_data/gloomy_graveyard.yaml"
$backupPath = "$filePath.fix_indent.bak" # Use a different backup name

# Validate file exists
if (-not (Test-Path $filePath)) {
    Write-Error "File not found: $filePath"
    exit 1
}

# Create backup
Write-Host "Backing up $filePath to $backupPath..."
Copy-Item -Path $filePath -Destination $backupPath -Force -ErrorAction SilentlyContinue

# Read file content
Write-Host "Reading file: $filePath..."
try {
    $content = Get-Content -Path $filePath -Raw -Encoding UTF8
} catch {
    Write-Error "Failed to read the input file: $filePath. Error: $($_.Exception.Message)"
    exit 1
}

# Define the regex pattern and replacement
# (?m)          : Multiline mode (^/$ match line start/end)
# ^(\s+)        : Capture leading whitespace (indentation) - Group 1
# - \s+         : Match the dash and space for the id line
# (id: .*\n)    : Capture the 'id: ...' line content including newline - Group 2
# \1            : Match the same leading indentation as Group 1 for the type line
# - \s+         : Match the dash and space for the type line (this is what we'll remove/change)
# (type: .*)$   : Capture the 'type: ...' line content - Group 3
# Replacement:
# $1- $2        : Keep the original '- id: ...' line ($1 = indent, - space, $2 = id content)
# $1  $3        : Add the original indent ($1), two spaces for alignment, then the type content ($3)
$regexPattern = '(?m)^(\s+)-\s+(id: .*\n)\1-\s+(type: .*)$'
$replacement = '$1- $2$1  $3' # Note the two spaces before $3 for alignment

# Perform the replacement
Write-Host "Fixing indentation for type lines following id lines..."
$originalLength = $content.Length
$content = $content -replace $regexPattern, $replacement
$modifiedLength = $content.Length

if ($originalLength -eq $modifiedLength) {
    Write-Host "No indentation issues found or fixed."
} else {
     Write-Host "Indentation fixed."
}


# Write the modified content back to the file
Write-Host "Writing changes back to $filePath..."
try {
    Set-Content -Path $filePath -Value $content -Encoding UTF8 -NoNewline # Use -NoNewline with -Raw Get-Content
    Write-Host "Script finished successfully. Indentation fixed in $filePath."
    Write-Host "Original file backed up at $backupPath."
} catch {
     Write-Error "Failed to write changes back to $filePath. Error: $($_.Exception.Message)"
     Write-Error "The original file is backed up at $backupPath. The modified content was not saved."
     exit 1
} 