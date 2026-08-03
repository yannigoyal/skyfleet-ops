# Stop and remove the SkyFleet Ops container. Data volume is preserved. Idempotent.
$ErrorActionPreference = "Stop"

$ContainerName = "skyfleet-ops"
$Existing = docker ps -a --format '{{.Names}}' | Select-String -Pattern "^$ContainerName$"

if ($Existing) {
    docker rm -f $ContainerName | Out-Null
    Write-Host "Stopped and removed $ContainerName."
} else {
    Write-Host "$ContainerName is not running."
}
