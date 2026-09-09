[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $ProjectPath,

    [Alias("hub-service")]
    [switch] $HubService,

    [Alias("mcp-proxy")]
    [switch] $McpProxy,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ForwardArguments = @()
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$promptaflowSourceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$env:PROMPTAFLOW_SOURCE_ROOT = $promptaflowSourceRoot

function Resolve-PromptaflowCommand {
    if ($env:PROMPTAFLOW_CLI) {
        $explicit = Get-Command -Name $env:PROMPTAFLOW_CLI -ErrorAction SilentlyContinue
        if ($null -eq $explicit) {
            throw "PROMPTAFLOW_CLI is not executable: $($env:PROMPTAFLOW_CLI)"
        }
        return [pscustomobject]@{ Executable = $explicit.Source; Prefix = @() }
    }

    foreach ($candidate in @(
        (Join-Path $promptaflowSourceRoot ".venv\Scripts\promptaflow.exe"),
        (Join-Path $promptaflowSourceRoot ".venv\bin\promptaflow")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [pscustomobject]@{ Executable = $candidate; Prefix = @() }
        }
    }

    $uv = Get-Command -Name "uv" -ErrorAction SilentlyContinue
    if ($null -ne $uv) {
        return [pscustomobject]@{
            Executable = $uv.Source
            Prefix = @("run", "--project", $promptaflowSourceRoot, "promptaflow")
        }
    }
    throw "PromptaFlow cannot start: no project virtualenv or uv executable was found."
}

function Invoke-Promptaflow {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments,
        [switch] $DiscardOutput
    )

    $prefix = $script:promptaflowCommand.Prefix
    $global:LASTEXITCODE = 0
    if ($DiscardOutput) {
        & $script:promptaflowCommand.Executable @prefix @Arguments | Out-Null
    }
    else {
        & $script:promptaflowCommand.Executable @prefix @Arguments
    }
    $result = $global:LASTEXITCODE
    if ($null -ne $result -and $result -ne 0) {
        exit $result
    }
}

function Find-WorkspaceRuntimeUrl {
    param([Parameter(Mandatory = $true)][string] $Workspace)

    $prefix = $script:promptaflowCommand.Prefix
    $global:LASTEXITCODE = 0
    $output = & $script:promptaflowCommand.Executable @prefix "runtimes" "--json" 2>$null
    if ($global:LASTEXITCODE -ne 0) { return $null }
    $text = ($output | Out-String).Trim()
    if (-not $text) { return $null }
    try { $listed = $text | ConvertFrom-Json }
    catch { return $null }

    $runtimesProperty = $listed.PSObject.Properties["runtimes"]
    if ($listed -isnot [System.Array] -and $null -ne $runtimesProperty) {
        $listed = $runtimesProperty.Value
    }
    foreach ($entry in @($listed)) {
        if ($null -eq $entry) { continue }
        $projectProperty = $entry.PSObject.Properties["project_root"]
        $urlProperty = $entry.PSObject.Properties["base_url"]
        if ($null -eq $projectProperty -or $null -eq $urlProperty) { continue }
        try { $candidate = [System.IO.Path]::GetFullPath([string]$projectProperty.Value) }
        catch { continue }
        if ([string]::Equals(
            $candidate.TrimEnd("\", "/"),
            $Workspace.TrimEnd("\", "/"),
            [StringComparison]::OrdinalIgnoreCase
        )) {
            return ([string]$urlProperty.Value).TrimEnd("/")
        }
    }
    return $null
}

try {
    $script:promptaflowCommand = Resolve-PromptaflowCommand

    if ($HubService) {
        Invoke-Promptaflow -Arguments (@("hub", "serve") + $ForwardArguments)
        exit 0
    }

    if ($McpProxy) {
        # MCP stdio is UTF-8. Windows Python otherwise inherits the active OEM
        # code page when launched through cmd.exe/Windows PowerShell, which can
        # make a valid tools/list response undecodable by the MCP client.
        $env:PYTHONUTF8 = "1"
        $env:PYTHONIOENCODING = "utf-8"
        $arguments = @(
            "agent-app", "mcp-proxy", (Join-Path $promptaflowSourceRoot "agent-app.windows.json")
        )
        # Explicit rather than `??`: the .cmd wrapper launches Windows
        # PowerShell 5.1, which fails to parse that operator at all.
        $workspaceInput = $env:PROMPTAFLOW_AGENT_APP_WORKSPACE
        if (-not $workspaceInput) { $workspaceInput = $env:ORBIT_AGENT_APP_WORKSPACE }
        if ($workspaceInput) {
            $workspace = (Resolve-Path -LiteralPath $workspaceInput).Path
            $arguments += @("--workspace", $workspace)
        }
        Invoke-Promptaflow -Arguments ($arguments + $ForwardArguments)
        exit 0
    }

    if ($ForwardArguments.Count -gt 0) {
        throw "usage: .\start-promptaflow.ps1 [PROJECT_PATH]"
    }

    $workspaceInput = $ProjectPath
    if (-not $workspaceInput) {
        $workspaceInput = (Get-Location).Path
    }
    if (-not (Test-Path -LiteralPath $workspaceInput -PathType Container)) {
        [Console]::Error.WriteLine("PromptaFlow project path is not a directory: $workspaceInput")
        exit 2
    }
    $workspace = (Resolve-Path -LiteralPath $workspaceInput).Path

    # The Windows manifest launches this script's HubService mode, so AgentAppHost
    # retains ownership of the background process and its PID record.
    Invoke-Promptaflow -Arguments @(
        "agent-app", "ensure", (Join-Path $promptaflowSourceRoot "agent-app.windows.json")
    ) -DiscardOutput

    $prefix = $script:promptaflowCommand.Prefix
    $global:LASTEXITCODE = 0
    $registrationOutput = & $script:promptaflowCommand.Executable @prefix `
        "hub" "register" $workspace
    if ($global:LASTEXITCODE -ne 0) {
        exit $global:LASTEXITCODE
    }
    $registrationText = ($registrationOutput | Out-String).Trim()
    try {
        $registration = $registrationText | ConvertFrom-Json
        if (-not $registration.ui_url) {
            throw "registration did not include ui_url"
        }
    }
    catch {
        throw "PromptaFlow Hub returned an invalid workspace registration: $registrationText"
    }

    $windowsManifest = Get-Content `
        -LiteralPath (Join-Path $promptaflowSourceRoot "agent-app.windows.json") `
        -Raw | ConvertFrom-Json
    $hubReadyUri = [Uri] $windowsManifest.service.ready_url
    $hubUrl = $hubReadyUri.GetLeftPart([UriPartial]::Authority)
    $runtimeUrl = Find-WorkspaceRuntimeUrl -Workspace $workspace
    if (-not $runtimeUrl) {
        # A registration is durable but lazy. Opening its stable Hub route is
        # the public signal that starts the dynamic Workspace Runtime.
        Invoke-WebRequest -Uri ([string]$registration.ui_url) -UseBasicParsing `
            -TimeoutSec 65 | Out-Null
        for ($attempt = 0; $attempt -lt 20 -and -not $runtimeUrl; $attempt++) {
            $runtimeUrl = Find-WorkspaceRuntimeUrl -Workspace $workspace
            if (-not $runtimeUrl) { Start-Sleep -Milliseconds 250 }
        }
    }
    if (-not $runtimeUrl) {
        throw "Workspace Runtime started but did not publish its URL."
    }
    Write-Output "PromptaFlow Hub: $hubUrl"
    Write-Output "Workspace Runtime: $runtimeUrl"
    Write-Output "Workspace UI: $($registration.ui_url)"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
