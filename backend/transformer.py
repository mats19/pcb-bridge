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