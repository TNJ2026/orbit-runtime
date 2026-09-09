[CmdletBinding()]
param(
    [Alias("dry-run")]
    [switch] $DryRun
)

$arguments = @{ StopOnly = $true }
if ($DryRun) { $arguments.DryRun = $true }

$global:LASTEXITCODE = 0
& (Join-Path $PSScriptRoot "restart-orbit.ps1") @arguments
exit $global:LASTEXITCODE
