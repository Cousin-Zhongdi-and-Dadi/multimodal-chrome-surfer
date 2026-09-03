param(
  [Parameter(Mandatory = $false)]
  [string]$ExtensionId = ""
)

$ErrorActionPreference = "Stop"

$hostName = "com.multimodal.browser_agent"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = (Get-Command python).Source
$manifestPath = Join-Path $PSScriptRoot "native-host-manifest.json"

if (-not $pythonPath) {
  throw "Python was not found on PATH."
}

$allowedOrigins = @()
if ($ExtensionId) {
  $allowedOrigins += "chrome-extension://$ExtensionId/"
}

$manifest = @{
  name = $hostName
  description = "Local GenericAgent host for the Multimodal Browser Agent extension."
  path = $pythonPath
  type = "stdio"
  allowed_origins = $allowedOrigins
}

$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8

$registryRoot = "HKCU:\Software\Google\Chrome\NativeMessagingHosts"
$hostKey = Join-Path $registryRoot $hostName

New-Item -Path $registryRoot -Force | Out-Null
New-Item -Path $hostKey -Force | Out-Null
New-ItemProperty -Path $hostKey -Name "(Default)" -Value $manifestPath -PropertyType String -Force | Out-Null

Write-Host "Native messaging host '$hostName' registered with manifest: $manifestPath"
