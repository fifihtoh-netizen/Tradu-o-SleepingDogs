# Tradu-o-SleepingDogs
Tradução pt-br para o port de SleepingDogs DE para mobile
# Sleeping Dogs: Definitive Edition – Android PT-BR Fix

A community-made tool to adapt the Brazilian Portuguese translation of Sleeping Dogs: Definitive Edition for compatible Android ports.

## About

The original PC translation may produce UI.big files that exceed the file-size requirements of certain Android ports.

This project provides a Python script that rebuilds the UI.big and UI.bix files while preserving the original UI.big file size.

## Features

- Rebuilds the translated UI.big file.
- Preserves the original file size (212,897,792 bytes).
- Generates a corresponding UI.bix index.
- Reorganizes translated resources to fit the original file structure.

## Requirements

- Windows PC
- Python 3
- NumPy (`python -m pip install numpy`)
- Original Sleeping Dogs: Definitive Edition files
- Compatible Brazilian Portuguese translation files

## Installation and Usage

1. Install Python 3.
2. Install NumPy:

   `python -m pip install numpy`

3. Place the following files in the same directory:

   - `build_ui_big.py`
   - `UI.big`
   - `UI.bix`
   - `UI__traduzido_.big`
   - `UI__traduzido_.bix`

4. Open Command Prompt in that directory.
5. Run:

   `python build_ui_big.py UI.big UI.bix UI__traduzido_.big UI__traduzido_.bix SAIDA_UI.big SAIDA_UI.bix`

6. The script will generate:

   - `SAIDA_UI.big`
   - `SAIDA_UI.bix`

7. Back up your original Android game files before replacing them.

8. Transfer the generated files to the appropriate game directory, using the exact filenames and capitalization expected by your Android port.

## Important

- This project is unofficial and is not affiliated with Square Enix.
- It does not include original game files or copyrighted translation assets.
- Users must obtain their own legally acquired game files and translation files.
- Compatibility may vary between Android ports and versions.
- Always back up your original files before making modifications.

## Credits

- Brazilian Portuguese translation: TriboGamer.
- Technical investigation and Android compatibility adaptation: community contributors.

## Disclaimer

Use this tool at your own risk. The author is not responsible for corrupted game files or installation problems.
