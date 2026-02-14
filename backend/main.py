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
    file_path = os.path.join("backend", "data", "probe_result.json")
    with open(file_path, "w") as f:
        f.write(result.json(indent=2))
    
    viz = generate_viz_gcode(result.points)
    viz_path = os.path.join("backend", "probe_viz.gcode")
    with open(viz_path, "w") as f:
        f.write(viz)
    return {"status": "saved", "file": file_path, "viz_file": viz_path}

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
    
    result_path = os.path.join("backend", "data", "probe_result.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, indent=2)

    viz = generate_viz_gcode(simulated_points)
    viz_path = os.path.join("backend", "simulation.gcode")
    with open(viz_path, "w") as f:
        f.write(viz)
    return {"message": "Simulation complete", "file": result_path, "viz_file": viz_path, "points": simulated_points}

@app.post("/process/pcb")
async def process_pcb(
    front: UploadFile = File(None),
    outline: UploadFile = File(None),
    drill: UploadFile = File(None),
    z_work: float = Form(-0.1),
    feed_rate: float = Form(200.0)
):
    """
    Nimmt Gerber-Dateien entgegen, ruft pcb2gcode auf und wendet Leveling an.
    """
    upload_dir = os.path.join("backend", "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Dateien speichern
    front_path = None
    outline_path = None
    drill_path = None
    
    if front:
        front_path = os.path.join(upload_dir, front.filename)
        with open(front_path, "wb") as buffer:
            shutil.copyfileobj(front.file, buffer)
            
    if outline:
        outline_path = os.path.join(upload_dir, outline.filename)
        with open(outline_path, "wb") as buffer:
            shutil.copyfileobj(outline.file, buffer)
            
    if drill:
        drill_path = os.path.join(upload_dir, drill.filename)
        with open(drill_path, "wb") as buffer:
            shutil.copyfileobj(drill.file, buffer)
            
    # Transformer initialisieren
    transformer = PcbTransformer()
    
    # 1. G-Code generieren
    config = {"z_work": z_work, "feed_rate": feed_rate}
    raw_files = transformer.run_pcb2gcode(front_path, outline_path, drill_path, config)
    
    # 2. Leveling anwenden (Beispielhaft nur auf Front/Traces)
    # In der Praxis würde man alle generierten Files leveln und kombinieren
    leveled_gcode = transformer.apply_leveling(raw_files["front"])
    
    output_path = os.path.join("backend", "pcb_leveled.gcode")
    with open(output_path, "w") as f:
        f.write(leveled_gcode)
    
    return {"status": "success", "file": output_path}

@app.get("/status")
async def get_status():
    return {"status": "pcb-bridge is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
