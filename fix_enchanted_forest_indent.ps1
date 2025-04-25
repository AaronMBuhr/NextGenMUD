# fix_enchanted_forest_indent.ps1
# Script to fix trigger indentation for enchanted_forest.yaml

# Define file paths
$filePath = "world_data/enchanted_forest.yaml"
$backupPath = "$filePath.fix_indent.bak" # Use a consistent backup name

# Validate file exists
if (-not (Test-Path $filePath)) {
    Write-Error "File not found: $filePath"
    exit 1
}

# Create backup
Write-Host "Backing up $filePath to $backupPath..."
Copy-Item -Path $filePath -Destination $backupPath -Force -ErrorAction SilentlyContinue

# Read file content using -Raw for multiline regex
Write-Host "Reading file: $filePath..."
try {
    $content = Get-Content -Path $filePath -Raw -Encoding UTF8
} catch {
    Write-Error "Failed to read the input file: $filePath. Error: $($_.Exception.Message)"
    exit 1
}

# Define the regex pattern and replacement (same as fix_trigger_indent.ps1)
$regexPattern = '(?m)^(\s+)-\s+(id: .*\n)\1-\s+(type: .*)$'
$replacement = '$1- $2$1  $3' # $1=indent, $2=id line, $3=type part. Adds 2 spaces for type indent.

# Perform the replacement
Write-Host "Fixing indentation for type lines following id lines..."
$originalLength = $content.Length
$content = $content -replace $regexPattern, $replacement
$modifiedLength = $content.Length

if ($originalLength -eq $modifiedLength) {
    Write-Host "No indentation issues found or fixed by the regex."
} else {
     Write-Host "Indentation issues fixed by the regex."
}

# Write the modified content back to the file
Write-Host "Writing changes back to $filePath..."
try {
    # Use -NoNewline because we read with -Raw
    Set-Content -Path $filePath -Value $content -Encoding UTF8 -NoNewline
    Write-Host "Script finished successfully. Indentation potentially fixed in $filePath."
    Write-Host "Original file backed up at $backupPath."
} catch {
     Write-Error "Failed to write changes back to $filePath. Error: $($_.Exception.Message)"
     Write-Error "The original file is backed up at $backupPath. The modified content was not saved."
     exit 1
} 