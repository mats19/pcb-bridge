# pcb-bridge
Integration von pcb2gcode und Height-Map-Kompensation für OpenBuilds CONTROL.

**Entwickelt mit Unterstützung von Google Gemini.**

## Architektur
- **Frontend**: OpenBuilds CONTROL JavaScript Makros
- **Backend**: FastAPI Server (Python) zur Verarbeitung von G-Code und Gerber-Files
- **Kommunikation**: REST API (lokal)

## Konzept
Das Projekt verbindet die Web-Oberfläche von OpenBuilds CONTROL mit leistungsfähigen Python-Tools.
1. **Gerber-Upload**: Über ein JS-Makro werden Gerber-Dateien an das Backend gesendet.
2. **Verarbeitung**: Das Backend nutzt `pcb2gcode`, um Isolationsfräspfade zu berechnen.
3. **Leveling**: Eine zuvor erstellte Heightmap (JSON) wird genutzt, um den Z-Code der Fräspfade an die Unebenheiten der Platine anzupassen (Warping).
4. **Output**: Der generierte G-Code (Front, Outline, Drill) wird direkt in den OpenBuilds CONTROL Editor geladen und visualisiert.

## Features
- **Multi-Layer Support**: Separate Verarbeitung und Visualisierung von Front (Traces), Outline (Cutout) und Drill (Bohrungen).
- **Auto-Leveling**: Anwendung einer Heightmap auf den G-Code zur Kompensation von Platinen-Unebenheiten.
- **Offset**: Verschiebung des Nullpunkts (Offset X/Y) direkt bei der Verarbeitung.
- **Segmentation**: Automatische Unterteilung langer Fahrwege (>1mm) für präzises Leveling auch bei geraden Leiterbahnen.
- **Statistiken**: Anzeige von Dimensionen (Bounding Box) und Z-Bereichen für jede Datei.
- **Persistenz**: Speicherung des letzten Verarbeitungszustands und der Probe-Daten.

## Komponenten
- **FastAPI**: Python Web-Framework für die API.
- **pcb2gcode**: Kommandozeilen-Tool zur Umwandlung von Gerber in G-Code.
- **NumPy / SciPy**: Für die mathematische Interpolation der Heightmap.
- **Metro UI**: UI-Framework innerhalb von OpenBuilds CONTROL für die Dialoge.

## Setup
1. Conda Environment: `conda env create -f environment.yml`
2. Aktiviere Env: `conda activate pcb-bridge`
3. Starte Backend: `python backend/main.py`

## Konfiguration
Die Parameter für `pcb2gcode` (z.B. Werkzeugdurchmesser, Drehzahlen, Frästiefen) werden zentral in der Datei `config/pcb2gcode.conf` gesteuert. Das Backend liest diese Werte aus, um korrekte Werkzeugwechsel-Hinweise in den G-Code einzufügen.

## Ordner
- /bin: Lokal pcb2gcode ausführbare Dateien ablegen (wird von Git ignoriert)
- /macros: JavaScript Quellcode für die Makros
- /backend: API und Transformations-Logik

## Bekannte Einschränkungen / Design-Entscheidungen
- **Probing**: Die Logik für das physische Abtasten (G38.2) ist im Frontend-Makro vorbereitet, muss aber noch final auf die Hardware abgestimmt und getestet werden.

## Testing
Um die API ohne Frontend zu testen, liegen Beispiel-Dateien unter `tests/samples/`.

Beispielaufruf mit cURL:
```bash
curl -X POST "http://127.0.0.1:8000/process/pcb" \
  -F "front=@tests/samples/Front.gbr" \
  -F "outline=@tests/samples/Edge_Cuts.gbr" \
  -F "drill=@tests/samples/Drill.drl" \
  -F "z_work=-0.1" \
  -F "feed_rate=200"
```

## Roadmap / Nächste Schritte
1. **Echtes Probing**: Implementierung der G38.2 Schleife im JavaScript-Makro (Kommunikation via Socket).
2. **Leveling-Mathematik**: Verifizierung der Koordinatensysteme (Maschinen- vs. Arbeitskoordinaten) beim Anwenden der Heightmap.
3. **Parameter**: Weitere pcb2gcode-Optionen (z.B. Werkzeugdurchmesser) im Frontend konfigurierbar machen.
4. **Hardware-Tests**: Validierung des Workflows an der echten CNC-Maschine.
