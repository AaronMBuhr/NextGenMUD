# Update-TriggerIDs.ps1
# Script to update generic trigger IDs with more specific ones based on predicates
# and fix indentation issues with timer_tick triggers

# Get the file path
$filePath = "world_data\city_sewers.yaml"
if (-not (Test-Path $filePath)) {
    Write-Error "Could not find city_sewers.yaml file at $filePath"
    exit 1
}

# Make a backup of the original file
$backupFile = "$filePath.bak"
Copy-Item -Path $filePath -Destination $backupFile -Force
Write-Host "Created backup at $backupFile"

# Read the file content
$content = Get-Content -Path $filePath -Raw

# First, let's reset any timer_tick IDs that have accumulated multiple suffixes or duplications
$content = $content -replace '- id: timer_tick_[a-z_0-9]+', '- id: timer_tick_water_sound'

# Create a regex pattern to find and replace generic IDs with specific ones based on predicate values
$pattern = '- id: catch_look_generic\s+type: catch_look\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "([^"]+)"'
$replacement = '- id: catch_look_$1
            type: catch_look
            criteria: 
              - subject: "%{*}"
                operator: contains
                predicate: "$1"'

# Replace catch_look_generic with catch_look_[predicate]
$content = [regex]::Replace($content, $pattern, $replacement)

# Replace catch_say_generic with catch_say_[predicate]
$pattern = '- id: catch_say_generic\s+type: catch_say\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "([^"]+)"'
$replacement = '- id: catch_say_$1
            type: catch_say
            criteria: 
              - subject: "%{*}"
                operator: contains
                predicate: "$1"'
$content = [regex]::Replace($content, $pattern, $replacement)

# Replace catch_any_generic with catch_any_[predicate]
$pattern = '- id: catch_any_generic\s+type: catch_any\s+criteria:\s+- subject: "%{\*}"\s+operator: contains\s+predicate: "([^"]+)"'
$replacement = '- id: catch_any_$1
            type: catch_any
            criteria: 
              - subject: "%{*}"
                operator: contains
                predicate: "$1"'
$content = [regex]::Replace($content, $pattern, $replacement)

# Fix indentation for timer_tick_water_sound
$timerTickPattern = '- id: timer_tick_water_sound\s+type: timer_tick'
$timerTickFixed = '- id: timer_tick_water_sound
            type: timer_tick'
$content = [regex]::Replace($content, $timerTickPattern, $timerTickFixed)

# Fix the indentation for catch_say_sewer_echo
$catchSayEchoPattern = '- id: catch_say_sewer_echo\s+type: catch_say\s+criteria:'
$catchSayEchoFixed = '- id: catch_say_sewer_echo
            type: catch_say
            criteria:'
$content = [regex]::Replace($content, $catchSayEchoPattern, $catchSayEchoFixed)

# Fix specifically for lines with wrong indentation between type and criteria
$catchSayEchoPattern2 = '- id: catch_say_sewer_echo\s+type: catch_say\s+\n\s+criteria:'
$catchSayEchoFixed2 = '- id: catch_say_sewer_echo
            type: catch_say
            criteria:'
$content = [regex]::Replace($content, $catchSayEchoPattern2, $catchSayEchoFixed2)

# Also fix any remaining occurrences with a direct pattern match
$content = $content -replace '- id: catch_say_sewer_echo\s+type: catch_say\s+criteria:', '- id: catch_say_sewer_echo
            type: catch_say
            criteria:'

# Find all room sections in the content
$roomPattern = '(\s+)([a-zA-Z_]+):\s+name: ([^\n]+).*?(triggers:.*?)(?=\s+creatures:|$)'
$roomMatches = [regex]::Matches($content, $roomPattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)

# Special handling for first room (sewer_entrance)
foreach ($roomMatch in $roomMatches) {
    $indentation = $roomMatch.Groups[1].Value
    $roomId = $roomMatch.Groups[2].Value
    $roomName = $roomMatch.Groups[3].Value
    $triggersSection = $roomMatch.Groups[4].Value
    
    # Make sure we're using the room ID, not the zone ID for sewer_entrance triggers
    if ($roomId -eq "city_sewers") {
        $roomId = "sewer_entrance"
    }
    
    # Extract all timer_tick triggers from this room's triggers section
    $timerTickPattern = '(- id: timer_tick_water_sound\s+type: timer_tick.*?)(?=\s+- id:|$)'
    $timerTickMatches = [regex]::Matches($triggersSection, $timerTickPattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    
    # If there are timer_tick triggers in this room
    if ($timerTickMatches.Count -gt 0) {
        $updatedTriggersSection = $triggersSection
        
        # Process each timer_tick trigger
        for ($i = 0; $i -lt $timerTickMatches.Count; $i++) {
            $timerTickTrigger = $timerTickMatches[$i].Value
            $newId = "timer_tick_${roomId}_$($i+1)"
            
            # Replace the ID in this specific trigger
            $updatedTimerTickTrigger = $timerTickTrigger -replace 'timer_tick_water_sound', $newId
            
            # Update the triggers section by replacing this specific trigger
            $updatedTriggersSection = $updatedTriggersSection.Replace($timerTickTrigger, $updatedTimerTickTrigger)
        }
        
        # Replace the original triggers section with the updated one
        $content = $content.Replace($triggersSection, $updatedTriggersSection)
    }
}

# Replace any remaining generic timer_tick IDs with more specific ones based on the echo messages
$waterSoundPattern = '- id: timer_tick_generic\s+type: timer_tick.*?echo (.*?)\.'
$matches = [regex]::Matches($content, $waterSoundPattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)

foreach ($match in $matches) {
    $echoMessage = $match.Groups[1].Value
    $echoMessage = $echoMessage.Trim()
    $idWord = ""
    
    # Extract a meaningful word from the echo message for the ID
    if ($echoMessage -match "water") { $idWord = "water" }
    elseif ($echoMessage -match "bubble") { $idWord = "bubble" }
    elseif ($echoMessage -match "splash") { $idWord = "splash" }
    elseif ($echoMessage -match "drip") { $idWord = "dripping" }
    elseif ($echoMessage -match "draft") { $idWord = "draft" }
    elseif ($echoMessage -match "grinding") { $idWord = "grinding" }
    elseif ($echoMessage -match "gas") { $idWord = "gas" }
    elseif ($echoMessage -match "breeze") { $idWord = "breeze" }
    elseif ($echoMessage -match "geyser") { $idWord = "geyser" }
    elseif ($echoMessage -match "surge") { $idWord = "surge" }
    elseif ($echoMessage -match "fish") { $idWord = "fish" }
    else { $idWord = "ambient" }
    
    # Only replace if we found a meaningful word
    if ($idWord -ne "") {
        $originalText = $match.Value
        $newText = $originalText -replace "timer_tick_generic", "timer_tick_$idWord"
        $content = $content.Replace($originalText, $newText)
    }
}

# Fix indentation of catch_any type
$catchAnyPattern = '- id: catch_any_([^\s]+)\s+type: catch_any\s+criteria:'
$catchAnyFixed = '- id: catch_any_$1
            type: catch_any
            criteria:'
$content = [regex]::Replace($content, $catchAnyPattern, $catchAnyFixed)

# Write the modified content back to the file
Set-Content -Path $filePath -Value $content
Write-Host "Updated trigger IDs with more specific names and fixed indentation in $filePath" 