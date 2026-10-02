# Instala o Vídeo Downloader: venv + dependências, ffmpeg, atalhos e inicia o programa.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$helper = Join-Path $root "helper"
$python = Join-Path $helper ".venv\Scripts\python.exe"
$pythonw = Join-Path $helper ".venv\Scripts\pythonw.exe"

Write-Host "1/5 Ambiente Python..." -ForegroundColor Cyan
if (-not (Test-Path $python)) {
    python -m venv (Join-Path $helper ".venv")
}
& $python -m pip install --upgrade pip --disable-pip-version-check
& $python -m pip install -r (Join-Path $helper "requirements.txt") --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências Python." }

function Update-PathFromRegistry {
    # o winget grava o PATH no registro; recarrega para este terminal e o programa iniciado no passo 5 enxergarem
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "2/5 ffmpeg..." -ForegroundColor Cyan
Update-PathFromRegistry
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "   ffmpeg já instalado."
} else {
    winget install --id Gyan.FFmpeg -e
    Update-PathFromRegistry
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "ffmpeg instalado, mas não encontrado no PATH." }
    Write-Host "   ffmpeg instalado."
}

Write-Host "3/5 Node (necessário para o YouTube)..." -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "   Node não encontrado. Instale com: winget install OpenJS.NodeJS.LTS" -ForegroundColor Yellow
}

Write-Host "4/5 ID da extensão e atalhos..." -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $helper "videodl\extension_id.txt"))) {
    & $python (Join-Path $root "scripts\gen_extension_key.py")
}
Push-Location $helper
try {
    & $python -c "from videodl import startup; startup.install_shortcuts()"
} finally {
    Pop-Location
}

Write-Host "5/5 Iniciando o programa..." -ForegroundColor Cyan
# se já estiver rodando (reinstalação), fecha para a nova cópia pegar o PATH atualizado
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*-m videodl*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Start-Process $pythonw -ArgumentList "-m", "videodl" -WorkingDirectory $helper

Write-Host ""
Write-Host "Pronto! Agora carregue a extensão:" -ForegroundColor Green
Write-Host "  1. Abra brave://extensions (ou opera://extensions)"
Write-Host "  2. Ative 'Modo do desenvolvedor'"
Write-Host "  3. Clique em 'Carregar sem compactação' e escolha: $(Join-Path $root 'extension')"
