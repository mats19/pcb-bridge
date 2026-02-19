from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import shutil
import numpy as np
import random
import uvicorn
from typing import Optional
from transformer import PcbTransformer
from visualization import generate_heightmap_image, generate_gcode_image

# Determine paths relative to this file (main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

app = FastAPI(title="pcb-bridge API")

# Serve data directory (images) statically
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

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
    """Generates G-code to visualize the probe points."""
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
    Saves the result of a real probing run (sent from the frontend).
    """
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    with open(file_path, "w") as f:
        f.write(result.model_dump_json(indent=2))
    
    # Generate Heightmap Image immediately
    out_path_hm = os.path.join(DATA_DIR, "viz_heightmap.png")
    generate_heightmap_image(file_path, out_path_hm)
    
    viz = generate_viz_gcode(result.points)
    return {"status": "saved", "file": file_path, "viz_gcode": viz, "images": {"heightmap": out_path_hm}}

@app.post("/probe/simulate")
async def simulate_probe_run(config: ProbeConfig):
    """ 
    Directly creates a probe_result.json based on dimensions, 
    without needing to save a grid beforehand.
    """
    # Calculate grid points
    xs = np.linspace(0, config.width, config.points_x)
    ys = np.linspace(0, config.height, config.points_y)

    # Simulate a curved surface (e.g., Sine wave + slight tilt)
    simulated_points = []
    for y in ys:
        for x in xs:
            # Fake Math: Warping of max approx. 0.5mm and a tilt
            z_sim = 0.2 * np.sin(x / 20.0) + 0.01 * y + random.uniform(-0.005, 0.005)
            simulated_points.append({"x": float(x), "y": float(y), "z": round(z_sim, 4)})

    result_data = {"config": config.model_dump(), "points": simulated_points}
    
    result_path = os.path.join(DATA_DIR, "probe_result.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, indent=2)

    # Generate Heightmap Image immediately
    out_path_hm = os.path.join(DATA_DIR, "viz_heightmap.png")
    generate_heightmap_image(result_path, out_path_hm)

    viz = generate_viz_gcode(simulated_points)
    return {"message": "Simulation complete", "file": result_path, "viz_gcode": viz, "points": simulated_points, "images": {"heightmap": out_path_hm}}

@app.get("/probe/latest")
async def get_latest_probe_result():
    """ 
    Loads the last saved probe result (if available).
    """
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    if not os.path.exists(file_path):
        return {"status": "none", "message": "No probe data found"}
    
    with open(file_path, "r") as f:
        data = json.load(f)
    
    # Regenerate visualization
    viz = generate_viz_gcode(data.get("points", []))
    
    return {
        "status": "success", 
        "config": data.get("config"), 
        "points": data.get("points"), 
        "viz_gcode": viz
    }

@app.delete("/probe/reset")
async def reset_probe_data():
    """Deletes the saved probe data."""
    file_path = os.path.join(DATA_DIR, "probe_result.json")
    if os.path.exists(file_path):
        os.remove(file_path)
    return {"status": "success", "message": "Probe data cleared"}

@app.delete("/process/reset")
async def reset_process_data():
    """Clears the processing state."""
    state_file = os.path.join(DATA_DIR, "process_state.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    return {"status": "success", "message": "Process state cleared"}

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
    Loads the result of the last Gerber processing.
    """
    state_file = os.path.join(DATA_DIR, "process_state.json")
    if not os.path.exists(state_file):
        return {"status": "none"}
        
    with open(state_file, "r") as f:
        state = json.load(f)
        
    # Load content of G-code files
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
        "filenames": state.get("filenames"),
        "images": state.get("images")
    }

def get_config_value(key, default="?"):
    """Reads a value from pcb2gcode.conf"""
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
    offset_x: float = Form(0.0),
    offset_y: float = Form(0.0)
):
    """
    Accepts Gerber files, calls pcb2gcode, and applies leveling.
    """
    upload_dir = os.path.join(DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    processed_dir = os.path.join(DATA_DIR, "gcode_processed")
    os.makedirs(processed_dir, exist_ok=True)
    state_file = os.path.join(DATA_DIR, "process_state.json")
    
    # Load old state to reuse paths if no new files are uploaded
    old_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                old_state = json.load(f)
        except Exception:
            pass
    
    # Save files
    front_path = None
    outline_path = None
    drill_path = None
    filenames = {}
    raw_paths = {} # New structure for raw file paths
    
    # Helper: Get path from old state
    def get_old_raw(key):
        return old_state.get("raw_paths", {}).get(key)
    def get_old_name(key):
        return old_state.get("filenames", {}).get(key)
    
    # Validierung: Prüfen, ob überhaupt Eingabedaten vorhanden sind
    has_front = front is not None or (get_old_raw("front") and os.path.exists(get_old_raw("front")))
    has_outline = outline is not None or (get_old_raw("outline") and os.path.exists(get_old_raw("outline")))
    has_drill = drill is not None or (get_old_raw("drill") and os.path.exists(get_old_raw("drill")))
    
    if not (has_front or has_outline or has_drill): 
        return {"status": "error", "message": "No input files provided and no previous state found. Please upload Gerber files."}

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
            
    # Initialize Transformer
    transformer = PcbTransformer(data_dir=DATA_DIR)
    
    # 1. Generate G-code
    config = {
        "offset_x": offset_x, 
        "offset_y": offset_y
    }
    raw_files = transformer.run_pcb2gcode(front_path, outline_path, drill_path, config)
    
    # 2. Apply leveling to all generated files
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
            
            # Header Injection: Insert tool change notice
            # pcb2gcode does this automatically for drills, but often not for Front/Outline
            header = ""
            if key == "front":
                dia = get_config_value("mill-diameters", "unknown")
                header = f"(MSG, Please insert Trace Isolation Tool: {dia})\nM0\n"
            elif key == "outline":
                dia = get_config_value("cutter-diameter", "unknown")
                header = f"(MSG, Please insert Outline Cutter: {dia})\nM0\n"
            
            if header:
                gcode = header + gcode
            
            # Save to processed directory
            out_path = os.path.join(processed_dir, f"pcb_leveled_{key}.gcode")
            with open(out_path, "w") as f:
                f.write(gcode)
            
            leveled_files[key] = out_path
            gcode_contents[key] = gcode

    # Generate G-code Visualization (All types)
    images = {}
    for key in ["front", "outline", "drill"]:
        if key in leveled_files:
            out_path_gc = os.path.join(DATA_DIR, f"viz_gcode_{key}.png")
            if generate_gcode_image(leveled_files[key], out_path_gc):
                images[f"gcode_{key}"] = out_path_gc

    # Save state for reload
    with open(state_file, "w") as f:
        json.dump({"config": config, "files": leveled_files, "dimensions": dimensions, "filenames": filenames, "raw_paths": raw_paths, "images": images}, f, indent=2)
    
    return {"status": "success", "files": leveled_files, "gcode": gcode_contents, "dimensions": dimensions, "filenames": filenames, "images": images}

@app.post("/visualize/create")
async def create_visualizations():
    """
    Generates PNG images for the Heightmap and the Leveled G-code.
    """
    images = {}
    
    # 1. Visualize Heightmap
    probe_file = os.path.join(DATA_DIR, "probe_result.json")
    out_path_hm = os.path.join(DATA_DIR, "viz_heightmap.png")
    if generate_heightmap_image(probe_file, out_path_hm):
        images["heightmap"] = out_path_hm

    # 2. Visualize Leveled G-code (All types)
    for key in ["front", "outline", "drill"]:
        gcode_path = os.path.join(DATA_DIR, "gcode_processed", f"pcb_leveled_{key}.gcode")
        if os.path.exists(gcode_path):
            out_path_gc = os.path.join(DATA_DIR, f"viz_gcode_{key}.png")
            if generate_gcode_image(gcode_path, out_path_gc):
                images[f"gcode_{key}"] = out_path_gc

    return {"status": "success", "images": images}

@app.get("/status")
async def get_status():
    return {"status": "pcb-bridge is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
