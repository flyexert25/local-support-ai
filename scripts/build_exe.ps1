param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Clean) {
    if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
    if (Test-Path ".\dist") { Remove-Item ".\dist" -Recurse -Force }
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pyinstaller .\LocalSupportAI.spec --noconfirm

Write-Host ""
Write-Host "Готово: dist\Local Support AI\Local Support AI.exe"
