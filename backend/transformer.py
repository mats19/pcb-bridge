import os
import subprocess
import json
import numpy as np
from scipy.interpolate import griddata
import platform

class PcbTransformer:
    def __init__(self, data_dir=None):
        # Pfade bestimmen (relativ zum Projekt-Root)
        # transformer.py liegt in backend/, also gehen wir eine Ebene hoch
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)
        
        self.data_dir = data_dir if data_dir else os.path.join(base_dir, "data")
        self.probe_file = os.path.join(data_dir, "probe_result.json")
        
        exe_name = "pcb2gcode.exe" if platform.system() == "Windows" else "pcb2gcode"
        self.pcb2gcode_bin = os.path.join(project_root, "bin", exe_name)
        self.config_file = os.path.join(project_root, "config", "pcb2gcode.conf")

    def run_pcb2gcode(self, front_gerber, outline_gerber, drill_gerber, config):
        """
        Ruft pcb2gcode als Subprozess auf.
        """
        output_dir = os.path.join(self.data_dir, "gcode_raw")
        os.makedirs(output_dir, exist_ok=True)
        
        # Basis-Kommando
        if os.path.exists(self.pcb2gcode_bin):
            cmd = [self.pcb2gcode_bin]
        else:
            cmd = ["pcb2gcode"] # Fallback auf System-PATH
            
        # Config-Datei laden
        if os.path.exists(self.config_file):
            cmd.extend(["--config", self.config_file])
        
        # Nullpunkt immer unten links erzwingen
        cmd.extend(["--zero-start"])
        
        # Eingabedateien und explizite Outputs
        # Wir setzen explizite Ausgabedateinamen, um Config-Werte zu überschreiben
        if front_gerber:
            cmd.extend(["--front", front_gerber])
            cmd.extend(["--front-output", "pcb_project_front.gcode"])
        if outline_gerber:
            cmd.extend(["--outline", outline_gerber])
            cmd.extend(["--outline-output", "pcb_project_outline.gcode"])
        if drill_gerber:
            cmd.extend(["--drill", drill_gerber])
            cmd.extend(["--drill-output", "pcb_project_drill.gcode"])
            
        # Output Konfiguration
        cmd.extend(["--output-dir", output_dir])
        
        # Parameter aus Config (Beispiele)
        cmd.extend(["--zwork", str(config.get("z_work", -0.1))])
        cmd.extend(["--zsafe", str(config.get("z_safe", 2.0))])
        cmd.extend(["--mill-feed", str(config.get("feed_rate", 200))])
        cmd.extend(["--mill-speed", str(config.get("spindle_speed", 12000))])
        
        # Prozess ausführen
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"pcb2gcode failed: {e.stderr.decode()}")
            
        # Rückgabe der generierten Dateipfade
        return {
            "front": os.path.join(output_dir, "pcb_project_front.gcode"),
            "outline": os.path.join(output_dir, "pcb_project_outline.gcode"),
            "drill": os.path.join(output_dir, "pcb_project_drill.gcode")
        }

    def process_gcode(self, gcode_path, offset_x=0.0, offset_y=0.0):
        """
        Liest G-Code ein, wendet Offset an, berechnet Dimensionen und wendet Leveling an.
        Gibt (content, dimensions) zurück.
        """
        probe_data = None
        points = None
        values = None

        # Probe Daten laden falls vorhanden
        if os.path.exists(self.probe_file):
            with open(self.probe_file, 'r') as f:
                probe_data = json.load(f)
            
            # Erstelle Interpolations-Gitter
            if probe_data and 'points' in probe_data:
                points = np.array([[p['x'], p['y']] for p in probe_data['points']])
                values = np.array([p['z'] for p in probe_data['points']])
        
        with open(gcode_path, 'r') as f:
            lines = f.readlines()
            
        new_lines = ["; Processed by pcb-bridge (Offset + Leveling)"]
        
        current_x = 0.0
        current_y = 0.0
        
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        min_z, max_z = float('inf'), float('-inf')
        has_coords = False

        for line in lines:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('('):
                new_lines.append(line)
                continue
                
            # Parse X, Y, Z aus der Zeile (sehr rudimentärer Parser)
            # In einer Produktion sollte hier ein Regex verwendet werden
            has_move = False
            new_z_part = ""
            
            parts = line.split()
            new_parts = []
            
            target_z = None
            final_z = None
            
            for part in parts:
                if part.startswith('X'):
                    # Offset anwenden
                    val = float(part[1:]) + offset_x
                    current_x = val
                    has_move = True
                    new_parts.append(f"X{val:.4f}")
                elif part.startswith('Y'):
                    val = float(part[1:]) + offset_y
                    current_y = val
                    has_move = True
                    new_parts.append(f"Y{val:.4f}")
                elif part.startswith('Z'):
                    target_z = float(part[1:])
                    # Z wird später modifiziert hinzugefügt
                else:
                    new_parts.append(part)
            
            # Dimensionen tracken
            if has_move:
                has_coords = True
                if current_x < min_x: min_x = current_x
                if current_x > max_x: max_x = current_x
                if current_y < min_y: min_y = current_y
                if current_y > max_y: max_y = current_y

            if target_z is not None and points is not None:
                # Interpoliere Z-Offset an aktueller XY Position
                # method='linear' ist sicher, 'cubic' wäre glatter
                z_offset = griddata(points, values, (current_x, current_y), method='linear', fill_value=0.0)
                corrected_z = target_z + float(z_offset)
                new_parts.append(f"Z{corrected_z:.4f}")
                final_z = corrected_z
            elif target_z is not None:
                new_parts.append(f"Z{target_z:.4f}")
                final_z = target_z
            
            if final_z is not None:
                if final_z < min_z: min_z = final_z
                if final_z > max_z: max_z = final_z
                
            new_lines.append(" ".join(new_parts))
            
        dims = None
        if has_coords:
            # Falls kein Z gefunden wurde (2D), Nullen setzen
            if min_z == float('inf'): min_z = 0.0
            if max_z == float('-inf'): max_z = 0.0
            
            dims = {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y, "width": max_x - min_x, "height": max_y - min_y, "min_z": min_z, "max_z": max_z}
            
        return "\n".join(new_lines), dims