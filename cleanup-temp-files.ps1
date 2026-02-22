[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [string]$Path = ".",
  [switch]$Recurse,
  [int]$LengthBytes = 4,
  [int]$NameChars = 8
)

$regex = "^[A-Za-z0-9_]{$NameChars}$"

$items =
  Get-ChildItem -LiteralPath $Path -File -Force -Recurse:$Recurse |
  Where-Object {
    $_.Length -eq $LengthBytes -and
    -not $_.Extension -and
    $_.Name -match $regex -and
    $_.FullName -notmatch '\\\.git\\' -and
    $_.FullName -notmatch '\\\.cursor\\'
  }

foreach ($f in $items) {
  if ($PSCmdlet.ShouldProcess($f.FullName, "Remove")) {
    Remove-Item -LiteralPath $f.FullName -Force
  }
}
