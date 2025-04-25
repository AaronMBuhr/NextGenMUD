# Add-TriggerIDs-To-CitySewerYaml.ps1
# Script to add trigger IDs to all triggers in city_sewers.yaml

# Get the actual path to the city_sewers.yaml file
# First check if it exists in the current directory
$filePath = "city_sewers.yaml"
if (-not (Test-Path $filePath)) {
    # If not in current directory, check in world_data subdirectory
    $filePath = Join-Path "world_data" "city_sewers.yaml"
    if (-not (Test-Path $filePath)) {
        # Try the absolute path in case we're running from a different directory
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        $filePath = Join-Path $scriptDir "world_data" "city_sewers.yaml"
        if (-not (Test-Path $filePath)) {
            Write-Error "Could not find city_sewers.yaml file in current directory or world_data subdirectory"
            exit 1
        }
    }
}

Write-Host "Found city_sewers.yaml at: $filePath"

# Read the content of the file
$content = Get-Content -Path $filePath -Raw

# Replace timer_tick triggers
$content = $content -replace '- type: timer_tick(?!\s+id:)', '- id: timer_tick_water_sound
          type: timer_tick'

$content = $content -replace '- id: timer_tick_water_sound\s+type: timer_tick\s+flags:\s+- only_when_pc_room\s+criteria:\s+- subject: "%time_elapsed%"\s+operator: "numgte"\s+predicate: 20\s+- subject: "\$random\(1,100\)"\s+operator: "numlte"\s+predicate: 25', '- id: timer_tick_debris
          type: timer_tick
          flags:
            - only_when_pc_room
          criteria:
            - subject: "%time_elapsed%"
              operator: "numgte"
              predicate: 20
            - subject: "$random(1,100)"
              operator: "numlte"
              predicate: 25'

# Replace specific triggers with more detailed patterns
$content = $content -replace '- type: timer_tick\s+flags:\s+- only_when_pc_room\s+criteria:\s+- subject: "%time_elapsed%"\s+operator: "numgte"\s+predicate: 15', '- id: timer_tick_dripping_water
          type: timer_tick
          flags:
            - only_when_pc_room
          criteria:
            - subject: "%time_elapsed%"
              operator: "numgte"
              predicate: 15'

$content = $content -replace '- type: timer_tick\s+flags:\s+- only_when_pc_room\s+criteria:\s+- subject: "%time_elapsed%"\s+operator: "numgte"\s+predicate: 30\s+- subject: "\$random\(1,100\)"\s+operator: "numlte"\s+predicate: 30', '- id: timer_tick_splashing
          type: timer_tick
          flags:
            - only_when_pc_room
          criteria:
            - subject: "%time_elapsed%"
              operator: "numgte"
              predicate: 30
            - subject: "$random(1,100)"
              operator: "numlte"
              predicate: 30'

# Replace catch_look triggers
$content = $content -replace '- type: catch_look\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "water"', '- id: catch_look_sewer_water
          type: catch_look
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "water"'

$content = $content -replace '- type: catch_look\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "pipe"', '- id: catch_look_sewer_pipe
          type: catch_look
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "pipe"'

$content = $content -replace '- type: catch_look\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "tunnel"', '- id: catch_look_sewer_tunnel
          type: catch_look
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "tunnel"'

$content = $content -replace '- type: catch_look\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "rat"', '- id: catch_look_sewer_rat
          type: catch_look
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "rat"'

# Replace catch_any triggers
$content = $content -replace '- type: catch_any\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "swim"', '- id: catch_any_sewer_swim
          type: catch_any
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "swim"'

$content = $content -replace '- type: catch_any\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "drink"', '- id: catch_any_sewer_drink
          type: catch_any
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "drink"'

$content = $content -replace '- type: catch_any\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "touch"', '- id: catch_any_sewer_touch
          type: catch_any
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "touch"'

# Replace catch_say triggers
$content = $content -replace '- type: catch_say\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "echo"', '- id: catch_say_sewer_echo
          type: catch_say
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "echo"'

$content = $content -replace '- type: catch_say\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "smell"', '- id: catch_say_sewer_smell
          type: catch_say
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "smell"'

$content = $content -replace '- type: catch_say\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "secret"', '- id: catch_say_sewer_secret
          type: catch_say
          criteria:
            - subject: "%{*}"
              operator: contains
              predicate: "secret"'

# Generic fallback replacements for any remaining triggers
$content = $content -replace '- type: timer_tick(?!\s+id:)', '- id: timer_tick_generic
          type: timer_tick'

$content = $content -replace '- type: catch_look(?!\s+id:)', '- id: catch_look_generic
          type: catch_look'

$content = $content -replace '- type: catch_any(?!\s+id:)', '- id: catch_any_generic
          type: catch_any'

$content = $content -replace '- type: catch_say(?!\s+id:)', '- id: catch_say_generic
          type: catch_say'

# Make a backup of the original file
$backupFile = "$filePath.bak"
if (Test-Path $filePath) {
    Copy-Item -Path $filePath -Destination $backupFile -Force
    Write-Host "Created backup at $backupFile"
}

# Write the modified content back to the file
$content | Out-File -FilePath $filePath -Encoding UTF8

Write-Host "Trigger IDs have been added to all triggers in city_sewers.yaml" 