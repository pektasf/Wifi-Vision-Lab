param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "wifi_vision_endpoint_adapters.json")
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue)) {
    throw "Get-NetAdapter is unavailable. Run this collector on Windows."
}

$adapters = @(
    Get-NetAdapter -IncludeHidden | ForEach-Object {
        $adapter = $_
        $configuration = Get-NetIPConfiguration -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue
        $addresses = @()
        if ($configuration -and $configuration.IPv4Address) {
            $addresses = @($configuration.IPv4Address | ForEach-Object { $_.IPAddress })
        }

        $description = [string]$adapter.InterfaceDescription
        $name = [string]$adapter.Name
        $isHardware = $null
        if ($null -ne $adapter.HardwareInterface) {
            $isHardware = [bool]$adapter.HardwareInterface
        }

        $kind = "unknown"
        $combined = "$name $description".ToLowerInvariant()
        if ($isHardware -eq $true) {
            $kind = "physical"
        }
        elseif ($isHardware -eq $false) {
            if ($combined -match "wi-fi direct|wifi direct|hosted network|wireless virtual") {
                $kind = "virtual_wlan"
            }
            else {
                $kind = "virtual_or_software"
            }
        }

        [pscustomobject]@{
            name = $name
            description = $description
            mac = ([string]$adapter.MacAddress).Replace("-", ":").ToUpperInvariant()
            status = [string]$adapter.Status
            hardware_interface = $isHardware
            adapter_kind = $kind
            ipv4_addresses = $addresses
            network_cidr = ""
        }
    }
)

$payload = [ordered]@{
    schema_version = 1
    collector = "wifi_vision_endpoint"
    observed_at = (Get-Date).ToUniversalTime().ToString("o")
    adapters = $adapters
}

$json = $payload | ConvertTo-Json -Depth 6
$parent = Split-Path -Parent $OutputPath
if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
Write-Host "WiFi Vision endpoint adapter inventory saved locally:"
Write-Host $OutputPath
Write-Host "The file contains local adapter MAC/IP details. Share it only with the network owner."
