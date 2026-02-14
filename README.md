# pcb-bridge
Integration von pcb2gcode und Height-Map-Kompensation für OpenBuilds CONTROL.

## Architektur
- **Frontend**: OpenBuilds CONTROL JavaScript Makros
- **Backend**: FastAPI Server (Python) zur Verarbeitung von G-Code und Gerber-Files
- **Kommunikation**: REST API (lokal)

## Konzept
Das Projekt verbindet die Web-Oberfläche von OpenBuilds CONTROL mit leistungsfähigen Python-Tools.
1. **Gerber-Upload**: Über ein JS-Makro werden Gerber-Dateien an das Backend gesendet.
2. **Verarbeitung**: Das Backend nutzt `pcb2gcode`, um Isolationsfräspfade zu berechnen.
3. **Leveling**: Eine zuvor erstellte Heightmap (JSON) wird genutzt, um den Z-Code der Fräspfade an die Unebenheiten der Platine anzupassen (Warping).
4. **Output**: Der fertige G-Code wird im Backend-Verzeichnis gespeichert und kann von dort manuell in CONTROL geladen werden.

## Komponenten
- **FastAPI**: Python Web-Framework für die API.
- **pcb2gcode**: Kommandozeilen-Tool zur Umwandlung von Gerber in G-Code.
- **NumPy / SciPy**: Für die mathematische Interpolation der Heightmap.
- **Metro UI**: UI-Framework innerhalb von OpenBuilds CONTROL für die Dialoge.

## Setup
1. Conda Environment: `conda env create -f environment.yml`
2. Aktiviere Env: `conda activate pcb-bridge`
3. Starte Backend: `python backend/main.py`

## Ordner
- /bin: Lokal pcb2gcode ausführbare Dateien ablegen (wird von Git ignoriert)
- /macros: JavaScript Quellcode für die Makros
- /backend: API und Transformations-Logik
