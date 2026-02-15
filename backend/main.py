from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import shutil
import numpy as np
import random
import uvicorn
from typing import Optional
from transformer import PcbTransformer

# Pfade relativ zur Position dieser Datei (main.py) bestimmen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

app = FastAPI(title="pcb-bridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProbeConfig(BaseModel):
    width: float
    height: float
    points_x: int
    points_y: int

class ProbePoint(BaseModel):
    x: float
    y: float
    z: float

class ProbeResult(BaseModel):
    config: ProbeConfig
    points: list[ProbePoint]

def generate_viz_gcode(points):
    """Generiert G-Code zur Visualisierung der Probe-Punkte."""
    lines = ["; Probe Grid Visualization", "; DO NOT RUN - VISUALIZATION ONLY", "G21", "G90", "G0 Z2.0"]
    for p in points:
        # Support dict (simulation) and object (pydantic)
        if isinstance(p, dict):
            x, y = p["x"], p["y"]
        else:
            x, y = p.x, p.y
            
        lines.append(f"G0 X{x:.3f} Y{y:.3f}")
        lines.append("G1 Z-1.0 F100")
        lines.append("G0 Z2.0")
    return "\n".join(lines)

@app.post("/probe/save")
async def save_probe_result(result: ProbeResult):
    """
    Speichert das Ergebnis eines echten Abtastvorgangs (vom Frontend gesendet).
    """
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    with open(file_path, "w") as f:
        f.write(result.json(indent=2))
    
    viz = generate_viz_gcode(result.points)
    return {"status": "saved", "file": file_path, "viz_gcode": viz}

@app.post("/probe/simulate")
async def simulate_probe_run(config: ProbeConfig):
    """
    Erstellt direkt eine probe_result.json basierend auf den Dimensionen,
    ohne dass vorher ein Grid gespeichert werden muss.
    """
    # Gitterpunkte berechnen
    xs = np.linspace(0, config.width, config.points_x)
    ys = np.linspace(0, config.height, config.points_y)

    # Simuliere eine gewölbte Oberfläche (z.B. Sinus-Welle + leichte Neigung)
    simulated_points = []
    for y in ys:
        for x in xs:
            # Fake Math: Eine Wölbung von max ca. 0.5mm und eine Neigung
            z_sim = 0.2 * np.sin(x / 20.0) + 0.01 * y + random.uniform(-0.005, 0.005)
            simulated_points.append({"x": float(x), "y": float(y), "z": round(z_sim, 4)})

    result_data = {"config": config.dict(), "points": simulated_points}
    
    result_path = os.path.join(DATA_DIR, "probe_result.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, indent=2)

    viz = generate_viz_gcode(simulated_points)
    return {"message": "Simulation complete", "file": result_path, "viz_gcode": viz, "points": simulated_points}

@app.get("/probe/latest")
async def get_latest_probe_result():
    """
    Lädt das letzte gespeicherte Probe-Ergebnis (falls vorhanden).
    """
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    if not os.path.exists(file_path):
        return {"status": "none", "message": "No probe data found"}
    
    with open(file_path, "r") as f:
        data = json.load(f)
    
    # Visualisierung neu generieren
    viz = generate_viz_gcode(data.get("points", []))
    
    return {
        "status": "success", 
        "config": data.get("config"), 
        "points": data.get("points"), 
        "viz_gcode": viz
    }

@app.on_event("startup")
async def startup_event():
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    if os.path.exists(file_path):
        print(f"Startup: Found existing probe data at {file_path}")
    else:
        print("Startup: No existing probe data found.")

@app.get("/process/latest")
async def get_latest_process():
    """
    Lädt das Ergebnis der letzten Gerber-Verarbeitung.
    """
    state_file = os.path.join(DATA_DIR, "process_state.json")
    if not os.path.exists(state_file):
        return {"status": "none"}
        
    with open(state_file, "r") as f:
        state = json.load(f)
        
    # Inhalte der G-Code Dateien laden
    gcode_data = {}
    for key in ["front", "outline", "drill"]:
        path = state.get("files", {}).get(key)
        if path and os.path.exists(path):
            with open(path, "r") as f:
                gcode_data[key] = f.read()
        else:
            gcode_data[key] = None
            
    return {
        "status": "success",
        "config": state.get("config"),
        "gcode": gcode_data,
        "dimensions": state.get("dimensions"),
        "filenames": state.get("filenames")
    }

def get_config_value(key, default="?"):
    """Liest einen Wert aus der pcb2gcode.conf"""
    try:
        config_path = os.path.join(os.path.dirname(BASE_DIR), "config", "pcb2gcode.conf")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            return v.split("#")[0].strip()
    except Exception:
        pass
    return default

@app.post("/process/pcb")
async def process_pcb(
    front: UploadFile = File(None),
    outline: UploadFile = File(None),
    drill: UploadFile = File(None),
    z_work: float = Form(-0.1),
    feed_rate: float = Form(200.0),
    offset_x: float = Form(0.0),
    offset_y: float = Form(0.0)
):
    """
    Nimmt Gerber-Dateien entgegen, ruft pcb2gcode auf und wendet Leveling an.
    """
    upload_dir = os.path.join(DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    state_file = os.path.join(DATA_DIR, "process_state.json")
    
    # Alten Zustand laden, um Pfade wiederzuverwenden, falls keine neuen Dateien hochgeladen werden
    old_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                old_state = json.load(f)
        except:
            pass
    
    # Dateien speichern
    front_path = None
    outline_path = None
    drill_path = None
    filenames = {}
    raw_paths = {} # Neue Struktur für Rohdateipfade
    
    # Helper: Pfad aus altem State holen
    def get_old_raw(key):
        return old_state.get("raw_paths", {}).get(key)
    def get_old_name(key):
        return old_state.get("filenames", {}).get(key)
    
    if front:
        front_path = os.path.join(upload_dir, front.filename)
        filenames["front"] = front.filename
        raw_paths["front"] = front_path
        with open(front_path, "wb") as buffer:
            shutil.copyfileobj(front.file, buffer)
    elif get_old_raw("front") and os.path.exists(get_old_raw("front")):
        front_path = get_old_raw("front")
        filenames["front"] = get_old_name("front")
        raw_paths["front"] = front_path
            
    if outline:
        outline_path = os.path.join(upload_dir, outline.filename)
        filenames["outline"] = outline.filename
        raw_paths["outline"] = outline_path
        with open(outline_path, "wb") as buffer:
            shutil.copyfileobj(outline.file, buffer)
    elif get_old_raw("outline") and os.path.exists(get_old_raw("outline")):
        outline_path = get_old_raw("outline")
        filenames["outline"] = get_old_name("outline")
        raw_paths["outline"] = outline_path
            
    if drill:
        drill_path = os.path.join(upload_dir, drill.filename)
        filenames["drill"] = drill.filename
        raw_paths["drill"] = drill_path
        with open(drill_path, "wb") as buffer:
            shutil.copyfileobj(drill.file, buffer)
    elif get_old_raw("drill") and os.path.exists(get_old_raw("drill")):
        drill_path = get_old_raw("drill")
        filenames["drill"] = get_old_name("drill")
        raw_paths["drill"] = drill_path
            
    # Transformer initialisieren
    transformer = PcbTransformer(data_dir=DATA_DIR)
    
    # 1. G-Code generieren
    config = {
        "z_work": z_work, 
        "feed_rate": feed_rate, 
        "offset_x": offset_x, 
        "offset_y": offset_y
    }
    raw_files = transformer.run_pcb2gcode(front_path, outline_path, drill_path, config)
    
    # 2. Leveling auf alle generierten Dateien anwenden
    leveled_files = {}
    gcode_contents = {}
    dimensions = {}
    
    for key in ["front", "outline", "drill"]:
        raw_path = raw_files.get(key)
        if raw_path and os.path.exists(raw_path):
            # Processing (Offset + Leveling + Dimensions)
            gcode, dims = transformer.process_gcode(raw_path, offset_x, offset_y)
            
            if dims:
                dimensions[key] = dims
            
            # Header Injection: Werkzeugwechsel-Hinweis einfügen
            # pcb2gcode macht das bei Drills automatisch, aber oft nicht bei Front/Outline
            header = ""
            if key == "front":
                dia = get_config_value("mill-diameters", "unknown")
                header = f"(MSG, Please insert Trace Isolation Tool: {dia})\nM0\n"
            elif key == "outline":
                dia = get_config_value("cutter-diameter", "unknown")
                header = f"(MSG, Please insert Outline Cutter: {dia})\nM0\n"
            
            if header:
                gcode = header + gcode
            
            # Speichern
            out_path = os.path.join(BASE_DIR, f"pcb_leveled_{key}.gcode")
            with open(out_path, "w") as f:
                f.write(gcode)
            
            leveled_files[key] = out_path
            gcode_contents[key] = gcode

    # Status speichern für Reload
    with open(state_file, "w") as f:
        json.dump({"config": config, "files": leveled_files, "dimensions": dimensions, "filenames": filenames, "raw_paths": raw_paths}, f, indent=2)
    
    return {"status": "success", "files": leveled_files, "gcode": gcode_contents, "dimensions": dimensions, "filenames": filenames}

@app.get("/status")
async def get_status():
    return {"status": "pcb-bridge is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
