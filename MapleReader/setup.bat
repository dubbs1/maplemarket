@echo off
cd /d "%~dp0"
echo Step 1 of 2: Tesseract (reads the text)
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo   Already installed.
) else (
  echo   Not found. Installing it with winget. Click Yes if Windows asks.
  winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
  if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo   Could not install it automatically. Install it by hand: see Part A of GUIDE.md.
  )
)
echo.
echo Step 2 of 2: Python packages
py -3.13 -m pip install --upgrade mss pillow pytesseract
echo.
echo Done. Next: double-click run_tests.bat to check everything, then start.bat to scan.
pause
