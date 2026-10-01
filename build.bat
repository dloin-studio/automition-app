@echo off
REM Build Involeap.exe on Windows. Needs Python 3.10+ from python.org (tick "Add to PATH").
python -m pip install --upgrade pip pyinstaller requests Pillow || goto :err
python -m PyInstaller --noconfirm --onefile --windowed --name Involeap --hidden-import PIL._tkinter_finder gui.py || goto :err
if not exist dist\.env.example copy .env.example dist\ >nul
echo.
echo DONE. Your app is dist\Involeap.exe  (put it in any folder; it creates inbox\, out\ and involeap.db next to itself)
pause
exit /b 0
:err
echo BUILD FAILED
pause
exit /b 1
