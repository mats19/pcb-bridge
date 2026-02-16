# pcb-bridge
Integration of pcb2gcode and Height-Map-Compensation for OpenBuilds CONTROL.

**STATUS: EXPERIMENTAL / IN DEVELOPMENT. UNTESTED ON REAL HARDWARE.**
**USE AT YOUR OWN RISK.**
**Tested on macOS and Windows 10/11.**
**Developed with support from Google Gemini.**

## Architecture
- **Frontend**: OpenBuilds CONTROL JavaScript Macros
- **Backend**: FastAPI Server (Python) for G-code and Gerber processing
- **Communication**: REST API (local)

## Concept
This project bridges the web interface of OpenBuilds CONTROL with powerful Python tools.
1. **Gerber Upload**: Gerber files are sent to the backend via a JS macro.
2. **Processing**: The backend uses `pcb2gcode` to calculate isolation milling paths.
3. **Leveling**: A previously created heightmap (JSON) is used to warp the Z-code of the milling paths to compensate for PCB unevenness.
4. **Output**: The generated G-code (Front, Outline, Drill) is loaded directly into the OpenBuilds CONTROL editor and visualized.

## Features
- **Multi-Layer Support**: Separate processing and visualization of Front (Traces), Outline (Cutout), and Drill (Holes).
- **Auto-Leveling**: Application of a heightmap to the G-code to compensate for PCB warping.
- **Offset**: Zero-point shift (Offset X/Y) directly during processing.
- **Segmentation**: Automatic subdivision of long moves (>1mm) for precise leveling even on straight traces.
- **Statistics**: Display of dimensions (Bounding Box) and Z-ranges for each file.
- **Persistence**: Storage of the last processing state and probe data.
- **State Management**: Reset functionality to clear previous data and start fresh.
- **UI Safety**: Visual feedback and UI locking during long processing tasks to prevent accidental cancellation.

## Components
- **FastAPI**: Python web framework for the API.
- **pcb2gcode**: Command-line tool for converting Gerber to G-code.
- **NumPy / SciPy**: For mathematical interpolation of the heightmap.
- **Metro UI**: UI framework within OpenBuilds CONTROL for the dialogs.

## Setup
1. Create Conda Environment: `conda env create -f environment.yml`
2. Activate Env: `conda activate pcb-bridge`
3. Start Backend: `python backend/main.py`

## Setup (Windows / CNC-PC)
1. Install Miniconda for Windows.
2. Open **Anaconda Prompt** and navigate to the project folder.
3. Create Environment: `conda env create -f environment.yml`
4. **pcb2gcode**:
   - Download the Windows ZIP from GitHub Releases.
   - Extract `pcb2gcode.exe` (and all included DLLs) into the `/bin` folder of this project.
   - *Note:* The backend automatically detects `pcb2gcode.exe`, `pcb2gcode.bat`, or `pcb2gcode.cmd` in the `/bin` folder.
5. Start Backend: `python backend/main.py`

## Configuration
Parameters for `pcb2gcode` (e.g., tool diameters, speeds, milling depths) are controlled centrally in the `config/pcb2gcode.conf` file. The backend reads these values to inject correct tool change prompts into the G-code.
**Note:** The backend manually parses this config file to ensure compatibility with older `pcb2gcode` versions (e.g., v2.4) that do not support the `--config` flag.

## Folders
- `/bin`: Place local `pcb2gcode` executables here (ignored by Git).
- `/macros`: JavaScript source code for the macros.
- `/backend`: API and transformation logic.

## Known Limitations / Design Decisions
- **Probing**: The logic for physical probing (G38.2) is implemented in the frontend macro but requires final validation and tuning on real hardware.

## Testing
To test the API without the frontend, sample files are located in `tests/samples/`.

Example call with cURL:
```bash
curl -X POST "http://127.0.0.1:8000/process/pcb" \
  -F "front=@tests/samples/Front.gbr" \
  -F "outline=@tests/samples/Edge_Cuts.gbr" \
  -F "drill=@tests/samples/Drill.drl" \
  -F "z_work=-0.1" \
  -F "feed_rate=200"
```

## Roadmap / Next Steps
1. **Real Probing**: Verification of the G38.2 loop in the JavaScript macro (communication via socket).
2. **Leveling Math**: Verification of coordinate systems (machine vs. work coordinates) when applying the heightmap.
3. **Hardware Tests**: Validation of the workflow on the real CNC machine.
