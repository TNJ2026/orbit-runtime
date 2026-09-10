[CmdletBinding()]
param(
    [Alias("dry-run")]
    [switch] $DryRun,

    [Alias("stop-only")]
    [switch] $StopOnly
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$promptaflowSourceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$userProfilePath = [Environment]::GetFolderPath("UserProfile")
$agentAppStateRoot = if ($env:AGENT_APP_STATE_DIR) {
    $env:AGENT_APP_STATE_DIR
}
else {
    Join-Path $userProfilePath ".local\state\agent-apps"
}
$runtimeStateRoot = if ($env:PROMPTAFLOW_RUNTIME_ROOT) {
    $env:PROMPTAFLOW_RUNTIME_ROOT
}
else {
    Join-Path $userProfilePath ".promptaflow"
}

function Resolve-PromptaflowCommand {
    if ($env:PROMPTAFLOW_CLI) {
        $explicit = Get-Command -Name $env:PROMPTAFLOW_CLI -ErrorAction SilentlyContinue
        if ($null -eq $explicit) {
            throw "PROMPTAFLOW_CLI is not executable: $($env:PROMPTAFLOW_CLI)"
        }
        return [pscustomobject]@{ Executable = $explicit.Source; Prefix = @() }
    }
    foreach ($candidate in @(
        (Join-Path $promptaflowSourceRoot ".venv\Scripts\paf.exe"),
        (Join-Path $promptaflowSourceRoot ".venv\bin\paf")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [pscustomobject]@{ Executable = $candidate; Prefix = @() }
        }
    }
    $uv = Get-Command -Name "uv" -ErrorAction SilentlyContinue
    if ($null -ne $uv) {
        return [pscustomobject]@{
            Executable = $uv.Source
            Prefix = @("run", "--project", $promptaflowSourceRoot, "paf")
        }
    }
    throw "PromptaFlow CLI not found; create .venv or install uv first."
}

function Invoke-PromptaflowJson {
    $prefix = $script:promptaflowCommand.Prefix
    $global:LASTEXITCODE = 0
    $output = & $script:promptaflowCommand.Executable @prefix "runtimes" "--json" 2>$null
    $result = $global:LASTEXITCODE
    if ($null -ne $result -and $result -ne 0) {
        throw "paf runtimes --json failed with exit code $result"
    }
    $text = ($output | Out-String).Trim()
    if (-not $text) { return @() }
    return $text | ConvertFrom-Json
}

function Get-ProcessIdentity {
    param([Parameter(Mandatory = $true)][int] $ProcessId)

    $process = Get-CimInstance -ClassName Win32_Process `
        -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    $created = if ($process.CreationDate -is [datetime]) {
        $process.CreationDate.ToUniversalTime().ToString("o")
    }
    else {
        [string] $process.CreationDate
    }
    $commandLine = [regex]::Replace([string] $process.CommandLine, "\s+", " ").Trim()
    return "$created`n$commandLine"
}

function Get-IdentityCommandLine {
    param([string] $Identity)
    if (-not $Identity) { return "" }
    $parts = $Identity -split "`n", 2
    if ($parts.Count -lt 2) { return "" }
    return $parts[1]
}

function Test-PromptaFlowCommand {
    param(
        [Parameter(Mandatory = $true)][string] $CommandLine,
        [Parameter(Mandatory = $true)][ValidateSet("Hub", "Runtime")][string] $Kind
    )

    $promptaflowPrefix = '(?i)(?:\b-m\s+promptaflow\s+|promptaflow(?:\.exe)?["'']?\s+)'
    if ($Kind -eq "Hub") {
        if ($CommandLine -match ($promptaflowPrefix + '(?:hub\s+serve|serve)(?:\s|$)')) {
            return $true
        }
        $escapedLauncher = [regex]::Escape((Join-Path $promptaflowSourceRoot "start-promptaflow.ps1"))
        if ($CommandLine -match ("(?i)" + $escapedLauncher + '.*-HubService(?:\s|$)')) {
            return $true
        }
        $escapedBashLauncher = [regex]::Escape((Join-Path $promptaflowSourceRoot "start-promptaflow.sh"))
        return $CommandLine -match (
            "(?i)" + $escapedBashLauncher + '.*--hub-service(?:\s|$)'
        )
    }
    return $CommandLine -match ($promptaflowPrefix + '(?:_runtime|serve)(?:\s|$)')
}

$candidates = @{}
function Add-Candidate {
    param(
        [Parameter(Mandatory = $true)][int] $ProcessId,
        [Parameter(Mandatory = $true)][ValidateSet("Hub", "Runtime")][string] $Kind,
        [string] $BaseUrl
    )
    if ($ProcessId -le 1) { return }

    $key = [string] $ProcessId
    if ($candidates.ContainsKey($key)) {
        if ($BaseUrl -and -not $candidates[$key].BaseUrl) {
            $candidates[$key].BaseUrl = $BaseUrl
        }
        return
    }
    $identity = Get-ProcessIdentity -ProcessId $ProcessId
    if (-not $identity) { return }
    $commandLine = Get-IdentityCommandLine -Identity $identity
    if (-not (Test-PromptaFlowCommand -CommandLine $commandLine -Kind $Kind)) {
        [Console]::Error.WriteLine(
            "skipping PID ${ProcessId}: recorded as PromptaFlow $Kind but now runs $commandLine"
        )
        return
    }
    $candidates[$key] = [pscustomobject]@{
        ProcessId = $ProcessId
        Kind = $Kind
        Label = "PromptaFlow $Kind"
        BaseUrl = $BaseUrl
        Identity = $identity
    }
}

function Read-RecordedPid {
    param([Parameter(Mandatory = $true)][string] $Path)
    try {
        $payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        return [int] $payload.pid
    }
    catch {
        return $null
    }
}

function Add-HubDescendants {
    # The Agent App PID belongs to its PowerShell launcher. Windows does not
    # automatically terminate a child when that launcher exits, so retain the
    # identity of every PromptaFlow Hub descendant while the tree is still intact.
    $allProcesses = @(Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue)
    $frontier = @(
        $candidates.Values |
            Where-Object { $_.Kind -eq "Hub" } |
            ForEach-Object { [int] $_.ProcessId }
    )
    $seenParents = @{}
    while ($frontier.Count -gt 0) {
        $next = @()
        foreach ($parentId in $frontier) {
            if ($seenParents.ContainsKey([string]$parentId)) { continue }
            $seenParents[[string]$parentId] = $true
            foreach ($process in $allProcesses) {
                if ([int]$process.ParentProcessId -ne $parentId) { continue }
                $commandLine = [regex]::Replace(
                    [string]$process.CommandLine, "\s+", " "
                ).Trim()
                if (Test-PromptaFlowCommand -CommandLine $commandLine -Kind Hub) {
                    Add-Candidate -ProcessId ([int]$process.ProcessId) -Kind Hub
                }
                $next += [int]$process.ProcessId
            }
        }
        $frontier = $next
    }
}

function Request-RuntimeShutdown {
    param([Parameter(Mandatory = $true)] $Candidate)
    if (-not $Candidate.BaseUrl) { return $false }
    try {
        $capabilities = Invoke-RestMethod `
            -Uri ($Candidate.BaseUrl.TrimEnd("/") + "/api/v1/capabilities") `
            -Method Get -TimeoutSec 5
        $command = @($capabilities.data.runtime.allowed_commands) |
            Where-Object { $_.command -eq "runtime.shutdown" } |
            Select-Object -First 1
        if ($null -eq $command) { return $false }
        $uri = [Uri]::new([Uri]($Candidate.BaseUrl.TrimEnd("/") + "/"), [string]$command.href)
        $headers = @{ "idempotency-key" = [guid]::NewGuid().ToString() }
        $body = @{ expected_version = [int] $command.expected_version } | ConvertTo-Json
        Invoke-RestMethod -Uri $uri.AbsoluteUri -Method Post -Headers $headers `
            -ContentType "application/json" -Body $body -TimeoutSec 5 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Stop-Candidate {
    param([Parameter(Mandatory = $true)] $Candidate)
    $current = Get-ProcessIdentity -ProcessId $Candidate.ProcessId
    if (-not $current) { return }
    if ($current -ne $Candidate.Identity) {
        [Console]::Error.WriteLine(
            "PID $($Candidate.ProcessId) is no longer the $($Candidate.Label) this run found; leaving it alone."
        )
        return
    }

    if ($Candidate.Kind -eq "Runtime" -and (Request-RuntimeShutdown -Candidate $Candidate)) {
        return
    }
    # Windows has no SIGTERM-equivalent for an arbitrary console process.
    # When the Runtime cannot expose its graceful shutdown command, terminate
    # the verified process tree so Worker children are not orphaned.
    $taskkill = Join-Path $env:SystemRoot "System32\taskkill.exe"
    if (Test-Path -LiteralPath $taskkill -PathType Leaf) {
        & $taskkill /PID $Candidate.ProcessId /T /F 2>$null | Out-Null
    }
    else {
        Stop-Process -Id $Candidate.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Force-StopCandidateTree {
    param([Parameter(Mandatory = $true)] $Candidate)
    $current = Get-ProcessIdentity -ProcessId $Candidate.ProcessId
    if (-not $current -or $current -ne $Candidate.Identity) { return }
    Write-Output "Force stopping $($Candidate.Label) (PID $($Candidate.ProcessId))..."
    $taskkill = Join-Path $env:SystemRoot "System32\taskkill.exe"
    if (Test-Path -LiteralPath $taskkill -PathType Leaf) {
        & $taskkill /PID $Candidate.ProcessId /T /F 2>$null | Out-Null
    }
    else {
        Stop-Process -Id $Candidate.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

try {
    $script:promptaflowCommand = Resolve-PromptaflowCommand

    $pidRoot = Join-Path $agentAppStateRoot "promptaflow"
    if (Test-Path -LiteralPath $pidRoot -PathType Container) {
        Get-ChildItem -LiteralPath $pidRoot -Filter "pid.json" -Recurse -File |
            Sort-Object FullName | ForEach-Object {
                $recordedId = Read-RecordedPid -Path $_.FullName
                if ($null -ne $recordedId) {
                    Add-Candidate -ProcessId $recordedId -Kind Hub
                }
            }
    }
    Add-HubDescendants

    $manifest = Get-Content -LiteralPath (Join-Path $promptaflowSourceRoot "agent-app.windows.json") `
        -Raw | ConvertFrom-Json
    $readyUri = [Uri] $manifest.service.ready_url
    $listenerCommand = Get-Command -Name "Get-NetTCPConnection" -ErrorAction SilentlyContinue
    if ($null -ne $listenerCommand) {
        Get-NetTCPConnection -State Listen -LocalPort $readyUri.Port -ErrorAction SilentlyContinue |
            ForEach-Object { Add-Candidate -ProcessId $_.OwningProcess -Kind Hub }
    }

    $listed = Invoke-PromptaflowJson
    $runtimesProperty = if ($null -ne $listed) {
        $listed.PSObject.Properties["runtimes"]
    }
    else { $null }
    if ($listed -isnot [System.Array] -and $null -ne $runtimesProperty) {
        $listed = $runtimesProperty.Value
    }
    foreach ($entry in @($listed)) {
        if ($null -eq $entry) { continue }
        $pidProperty = $entry.PSObject.Properties["pid"]
        if ($null -eq $pidProperty) { continue }
        $baseUrlProperty = $entry.PSObject.Properties["base_url"]
        $baseUrl = if ($null -ne $baseUrlProperty) {
            [string] $baseUrlProperty.Value
        }
        else { $null }
        Add-Candidate -ProcessId ([int] $pidProperty.Value) -Kind Runtime -BaseUrl $baseUrl
    }

    if (Test-Path -LiteralPath $runtimeStateRoot -PathType Container) {
        Get-ChildItem -LiteralPath $runtimeStateRoot -Filter "*.owner.lock" -Recurse -File |
            Sort-Object FullName | ForEach-Object {
                $factsPath = [System.IO.Path]::ChangeExtension($_.FullName, "json")
                foreach ($candidatePath in @($factsPath, $_.FullName)) {
                    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { continue }
                    $recordedId = Read-RecordedPid -Path $candidatePath
                    if ($null -ne $recordedId) {
                        Add-Candidate -ProcessId $recordedId -Kind Runtime
                        break
                    }
                }
            }
    }

    $ordered = @($candidates.Values | Sort-Object Label, ProcessId)
    if ($ordered.Count -eq 0) {
        Write-Output "Nothing of PromptaFlow's is running."
    }
    else {
        foreach ($candidate in $ordered) {
            if ($DryRun) {
                Write-Output "Would stop $($candidate.Label) (PID $($candidate.ProcessId))."
            }
            else {
                Write-Output "Stopping $($candidate.Label) (PID $($candidate.ProcessId))..."
                Stop-Candidate -Candidate $candidate
            }
        }
    }

    if ($DryRun) {
        if ($StopOnly) { Write-Output "Dry run complete; nothing was stopped." }
        else { Write-Output "Dry run complete; nothing was stopped or started." }
        exit 0
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while ([DateTime]::UtcNow -lt $deadline) {
        $stillAlive = $false
        foreach ($candidate in $ordered) {
            if ((Get-ProcessIdentity -ProcessId $candidate.ProcessId) -eq $candidate.Identity) {
                $stillAlive = $true
                break
            }
        }
        if (-not $stillAlive) { break }
        Start-Sleep -Milliseconds 500
    }
    foreach ($candidate in $ordered) {
        Force-StopCandidateTree -Candidate $candidate
    }

    if ($StopOnly) {
        Write-Output "PromptaFlow Hub and all discovered Runtimes are stopped."
        exit 0
    }

    Write-Output "Starting PromptaFlow through the Agent App host..."
    $global:LASTEXITCODE = 0
    & (Join-Path $promptaflowSourceRoot "start-promptaflow.ps1")
    exit $global:LASTEXITCODE
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
