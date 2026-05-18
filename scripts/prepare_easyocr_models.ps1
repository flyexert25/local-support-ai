param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "Preparing EasyOCR models for Russian and English..."
Write-Host "Models will be stored in: $env:USERPROFILE\.EasyOCR\model"
Write-Host ""

& $Python -c "import easyocr; easyocr.Reader(['ru','en'], gpu=False, verbose=True, download_enabled=True); print('EasyOCR models are ready.')"

Write-Host ""
Write-Host "Done. You can now disconnect the internet and use OCR locally."
