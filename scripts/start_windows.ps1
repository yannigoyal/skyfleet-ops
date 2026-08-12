# Build (if needed) and run the SkyFleet Ops container. Idempotent.
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$ImageName = "skyfleet-ops"
$ContainerName = "skyfleet-ops"
$Port = 8000

if (-not (Test-Path ".env")) {
    Write-Error "No .env file found. Copy .env.example to .env and set OPENROUTER_API_KEY first."
    exit 1
}

$Build = $args -contains "--build"
$ImageExists = docker images -q $ImageName

if ($Build -or -not $ImageExists) {
    Write-Host "Building $ImageName..."
    docker build -f docker/Dockerfile -t $ImageName .
}

$Existing = docker ps -a --format '{{.Names}}' | Select-String -Pattern "^$ContainerName$"
if ($Existing) {
    Write-Host "Removing existing container..."
    docker rm -f $ContainerName | Out-Null
}

New-Item -ItemType Directory -Force -Path "database" | Out-Null

Write-Host "Starting $ContainerName on port $Port..."
docker run -d `
  --name $ContainerName `
  -v "${RootDir}\database:/app/database" `
  -p "${Port}:8000" `
  --env-file .env `
  $ImageName

Write-Host "SkyFleet Ops is running at http://localhost:$Port"
Start-Process "http://localhost:$Port"
