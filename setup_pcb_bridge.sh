#!/bin/bash

# Projektname
PROJECT_NAME="pcb-bridge"
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Ordnerstruktur erstellen
mkdir -p bin macros backend/data config

# .gitignore erstellen
cat <<EOF > .gitignore
# Binaries und Executables
bin/pcb2gcode*
*.exe
*.bin
*.app

# Python
__pycache__/
.venv/
.conda/
*.pyc
.env

# Daten und Temporäres
backend/data/*
*.gcode
*.csv
.DS_Store
EOF

# Conda environment.yml erstellen
cat <<EOF > environment.yml
name: pcb-bridge
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - fastapi
  - uvicorn
  - scipy
  - numpy
  - python-multipart
  - pip
  - pip:
    - flask-cors
EOF

# Minimales README erstellen
cat <<EOF > README.md
# pcb-bridge
Integration von pcb2gcode und Height-Map-Kompensation für OpenBuilds CONTROL.

## Architektur
- **Frontend**: OpenBuilds CONTROL JavaScript Makros
- **Backend**: FastAPI Server (Python) zur Verarbeitung von G-Code und Gerber-Files

## Setup
1. Conda Environment: \`conda env create -f environment.yml\`
2. Aktiviere Env: \`conda activate pcb-bridge\`
3. Starte Backend: \`python backend/main.py\`

## Ordner
- /bin: Lokal pcb2gcode ausführbare Dateien ablegen (wird von Git ignoriert)
- /macros: JavaScript Quellcode für die Makros
- /backend: API und Transformations-Logik
EOF

# Dateien initialisieren
touch macros/CreateHeightMap.js
touch macros/ProcessGerber.js
touch backend/transformer.py

# Initiales Backend-Skelett (main.py)
cat <<EOF > backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

app = FastAPI(title="pcb-bridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
async def get_status():
    return {"status": "pcb-bridge is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
EOF

echo "Struktur für $PROJECT_NAME wurde erfolgreich erstellt!"
