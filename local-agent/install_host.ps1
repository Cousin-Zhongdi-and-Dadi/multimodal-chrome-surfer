param(
  [Parameter(Mandatory = $false)]
  [string]$ExtensionId = ""
)

$ErrorActionPreference = "Stop"

$hostName = "com.multimodal.browser_agent"
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$runnerPath = Join-Path $PSScriptRoot "host_runner.cmd"
$manifestPath = Join-Path $PSScriptRoot "native-host-manifest.json"

if (-not (Test-Path $pythonPath)) {
  throw "Workspace virtualenv Python was not found: $pythonPath"
}

if (-not (Test-Path $runnerPath)) {
  throw "Native host runner was not found: $runnerPath"
}

$allowedOrigins = @()
if ($ExtensionId) {
  $allowedOrigins += "chrome-extension://$ExtensionId/"
}

$manifest = @{
  name = $hostName
  description = "Local GenericAgent host for the Multimodal Browser Agent extension."
  path = $runnerPath
  type = "stdio"
  allowed_origins = $allowedOrigins
}

$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8

$registryRoot = "HKCU:\Software\Google\Chrome\NativeMessagingHosts"
$hostKey = Join-Path $registryRoot $hostName

if (-not (Test-Path $registryRoot)) {
  New-Item -Path $registryRoot | Out-Null
}

if (-not (Test-Path $hostKey)) {
  New-Item -Path $hostKey | Out-Null
}

New-ItemProperty -Path $hostKey -Name "(Default)" -Value $manifestPath -PropertyType String -Force | Out-Null

Write-Host "Native messaging host '$hostName' registered with manifest: $manifestPath"
