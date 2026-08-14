# Build (if needed) and run the SkyFleet Ops container. Idempotent.
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$ImageName = "skyfleet-ops"
$ContainerName = "skyfleet-ops"
$Port = 8000

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            # A refused connection is the expected state while the container boots.
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

if (-not (Test-Path ".env")) {
    Write-Error "No .env file found. Copy .env.example to .env and set OPENROUTER_API_KEY first."
    exit 1
}

$Build = $args -contains "--build"

$PSNativeCommandUseErrorActionPreference = $false
docker image inspect $ImageName 1>$null 2>$null
$ImageExists = ($LASTEXITCODE -eq 0)
$PSNativeCommandUseErrorActionPreference = $true

if ($Build -or -not $ImageExists) {
    Write-Host "Building $ImageName..."
    docker build -f docker/Dockerfile -t $ImageName .
}

$Existing = docker ps -a --format '{{.Names}}' | Select-String -Pattern "^$ContainerName$"
if ($Existing) {
    Write-Host "Removing existing container..."
    docker rm -f $ContainerName | Out-Null
}

New-Item -ItemType Directory -Force -Path "$RootDir\database" | Out-Null

Write-Host "Starting $ContainerName on port $Port..."
docker run -d `
  --name $ContainerName `
  -v "${RootDir}\database:/app/database" `
  -p "${Port}:8000" `
  --env-file .env `
  $ImageName

# `docker run -d` returns once the container process exists, not once uvicorn is
# accepting connections. Without this wait the browser is opened into the boot
# window and the first page load fails.
Write-Host "Waiting for SkyFleet Ops to answer on http://localhost:$Port/api/health ..."
if (Wait-ForHealth -Url "http://localhost:$Port/api/health" -TimeoutSeconds 60) {
    Write-Host "Ready."
} else {
    Write-Host "Still not answering after 60s. Check 'docker logs $ContainerName'. Opening anyway."
}

Write-Host "SkyFleet Ops is running at http://localhost:$Port"

$PSNativeCommandUseErrorActionPreference = $false
docker volume inspect skyfleet-data 1>$null 2>$null
$OldVolumeExists = ($LASTEXITCODE -eq 0)
$PSNativeCommandUseErrorActionPreference = $true

if ($OldVolumeExists) {
    Write-Host ""
    Write-Host "Note: a previous Docker-managed volume 'skyfleet-data' still exists."
    Write-Host "This container now reads and writes database\skyfleet.db on the host instead."
    Write-Host "See docker/MIGRATION.md if you need to recover data from the old volume."
    Write-Host ""
}

Start-Process "http://localhost:$Port"
