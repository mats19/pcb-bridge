import os
import subprocess
import json
import numpy as np
from scipy.interpolate import griddata

class PcbTransformer:
    def __init__(self, data_dir="backend/data"):
        self.data_dir = data_dir
        self.probe_file = os.path.join(data_dir, "probe_result.json")

    def run_pcb2gcode(self, front_gerber, outline_gerber, drill_gerber, config):
        """
        Ruft pcb2gcode als Subprozess auf.
        """
        output_dir = os.path.join(self.data_dir, "gcode_raw")
        os.makedirs(output_dir, exist_ok=True)
        
        # Basis-Kommando
        cmd = ["pcb2gcode"]
        
        # Eingabedateien
        if front_gerber:
            cmd.extend(["--front", front_gerber])
        if outline_gerber:
            cmd.extend(["--outline", outline_gerber])
        if drill_gerber:
            cmd.extend(["--drill", drill_gerber])
            
        # Output Konfiguration
        cmd.extend(["--output-dir", output_dir])
        cmd.extend(["--basename", "pcb_project"])
        
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

    def apply_leveling(self, gcode_path):
        """
        Liest G-Code ein und wendet die Höhenkorrektur basierend auf probe_result.json an.
        """
        if not os.path.exists(self.probe_file):
            return None # Keine Probe-Daten vorhanden
            
        with open(self.probe_file, 'r') as f:
            probe_data = json.load(f)
            
        # Erstelle Interpolations-Gitter
        points = np.array([[p['x'], p['y']] for p in probe_data['points']])
        values = np.array([p['z'] for p in probe_data['points']])
        
        with open(gcode_path, 'r') as f:
            lines = f.readlines()
            
        new_lines = ["; Leveling Applied via pcb-bridge"]
        
        current_x = 0.0
        current_y = 0.0
        
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
            
            for part in parts:
                if part.startswith('X'):
                    current_x = float(part[1:])
                    has_move = True
                    new_parts.append(part)
                elif part.startswith('Y'):
                    current_y = float(part[1:])
                    has_move = True
                    new_parts.append(part)
                elif part.startswith('Z'):
                    target_z = float(part[1:])
                    # Z wird später modifiziert hinzugefügt
                else:
                    new_parts.append(part)
            
            if target_z is not None:
                # Interpoliere Z-Offset an aktueller XY Position
                # method='linear' ist sicher, 'cubic' wäre glatter
                z_offset = griddata(points, values, (current_x, current_y), method='linear', fill_value=0.0)
                corrected_z = target_z + float(z_offset)
                new_parts.append(f"Z{corrected_z:.4f}")
                
            new_lines.append(" ".join(new_parts))
            
        return "\n".join(new_lines)