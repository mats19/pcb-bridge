# pcb-bridge
Integration von pcb2gcode und Height-Map-Kompensation für OpenBuilds CONTROL.

## Architektur
- **Frontend**: OpenBuilds CONTROL JavaScript Makros
- **Backend**: FastAPI Server (Python) zur Verarbeitung von G-Code und Gerber-Files

## Setup
1. Conda Environment: `conda env create -f environment.yml`
2. Aktiviere Env: `conda activate pcb-bridge`
3. Starte Backend: `python backend/main.py`

## Ordner
- /bin: Lokal pcb2gcode ausführbare Dateien ablegen (wird von Git ignoriert)
- /macros: JavaScript Quellcode für die Makros
- /backend: API und Transformations-Logik
