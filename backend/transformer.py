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
        Liest G-Code ein, wendet Offset an, segmentiert lange G1-Fahrwege
        und wendet Leveling an.
        """
        MAX_SEGMENT_LENGTH = 1.0 # mm - Maximale Länge eines Segments für Leveling

        probe_data = None
        points = None
        values = None

        # Probe Daten laden
        if os.path.exists(self.probe_file):
            with open(self.probe_file, 'r') as f:
                probe_data = json.load(f)
            if probe_data and 'points' in probe_data:
                points = np.array([[p['x'], p['y']] for p in probe_data['points']])
                values = np.array([p['z'] for p in probe_data['points']])
        
        with open(gcode_path, 'r') as f:
            lines = f.readlines()
            
        new_lines = ["; Processed by pcb-bridge (Offset + Segmentation + Leveling)"]
        
        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        current_mode = 'G0' # Startannahme
        
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        min_z, max_z = float('inf'), float('-inf')
        has_coords = False

        # Helper für Z-Interpolation
        def get_z_offset(x, y):
            if points is None: return 0.0
            # griddata ist robust, aber bei vielen Punkten langsam. Für PCB G-Code (<10k Zeilen) ok.
            return float(griddata(points, values, (x, y), method='linear', fill_value=0.0))

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith(';') or line_stripped.startswith('('):
                new_lines.append(line_stripped)
                continue
            
            parts = line_stripped.split()
            
            # Modus erkennen (G0 vs G1)
            if 'G0' in parts or 'G00' in parts: current_mode = 'G0'
            elif 'G1' in parts or 'G01' in parts: current_mode = 'G1'
            
            # Zielkoordinaten parsen
            target_x = current_x
            target_y = current_y
            target_z = current_z
            
            has_x = False
            has_y = False
            has_z = False
            other_parts = [] # F, S, M Befehle

            for part in parts:
                if part.startswith('X'):
                    target_x = float(part[1:]) + offset_x
                    has_x = True
                elif part.startswith('Y'):
                    target_y = float(part[1:]) + offset_y
                    has_y = True
                elif part.startswith('Z'):
                    target_z = float(part[1:])
                    has_z = True
                elif not part.startswith('G'): # Alles was kein G-Befehl und keine Koordinate ist (F, S, M, T)
                    other_parts.append(part)
                elif part not in ['G0', 'G00', 'G1', 'G01']: # Andere G-Befehle (G21, G90 etc)
                    other_parts.append(part)
            
            # Segmentierung prüfen (nur bei G1 und wenn Probe-Daten da sind)
            dist = 0.0
            if has_x or has_y:
                dist = np.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
            
            if current_mode == 'G1' and dist > MAX_SEGMENT_LENGTH and points is not None:
                # Segmentieren!
                num_segments = int(np.ceil(dist / MAX_SEGMENT_LENGTH))
                
                for i in range(1, num_segments + 1):
                    t = i / num_segments
                    seg_x = current_x + (target_x - current_x) * t
                    seg_y = current_y + (target_y - current_y) * t
                    
                    # Z linear interpolieren (falls Rampe) + Leveling Offset
                    seg_z_base = current_z + (target_z - current_z) * t
                    z_offset = get_z_offset(seg_x, seg_y)
                    seg_z_final = seg_z_base + z_offset
                    
                    # Stats update
                    if seg_z_final < min_z: min_z = seg_z_final
                    if seg_z_final > max_z: max_z = seg_z_final
                    
                    # Zeile bauen
                    seg_line = f"G1 X{seg_x:.4f} Y{seg_y:.4f} Z{seg_z_final:.4f}"
                    # F-Werte etc. nur beim ersten Segment anhängen
                    if i == 1 and other_parts:
                        seg_line += " " + " ".join(other_parts)
                    new_lines.append(seg_line)
                
                # State update
                current_x, current_y, current_z = target_x, target_y, target_z
            
            else:
                # Standard-Verarbeitung (keine Segmentierung, z.B. G0 oder kurze G1)
                new_line_parts = []
                if 'G0' in parts or 'G00' in parts: new_line_parts.append('G0')
                elif 'G1' in parts or 'G01' in parts: new_line_parts.append('G1')
                
                if has_x: new_line_parts.append(f"X{target_x:.4f}")
                if has_y: new_line_parts.append(f"Y{target_y:.4f}")
                
                # Z-Leveling anwenden
                final_z_val = target_z
                if has_z or (has_x or has_y): # Auch bei XY-Move Z anpassen (Leveling)
                    z_offset = get_z_offset(target_x, target_y)
                    final_z_val = target_z + z_offset
                    new_line_parts.append(f"Z{final_z_val:.4f}")
                
                new_line_parts.extend(other_parts)
                new_lines.append(" ".join(new_line_parts))
                
                # State update
                current_x, current_y, current_z = target_x, target_y, target_z
                
                # Stats update
                if final_z_val < min_z: min_z = final_z_val
                if final_z_val > max_z: max_z = final_z_val

            # Dimensionen tracken
            if has_x or has_y:
                has_coords = True
                if current_x < min_x: min_x = current_x
                if current_x > max_x: max_x = current_x
                if current_y < min_y: min_y = current_y
                if current_y > max_y: max_y = current_y

        dims = None
        if has_coords:
            # Falls kein Z gefunden wurde (2D), Nullen setzen
            if min_z == float('inf'): min_z = 0.0
            if max_z == float('-inf'): max_z = 0.0
            
            dims = {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y, "width": max_x - min_x, "height": max_y - min_y, "min_z": min_z, "max_z": max_z}
            
        return "\n".join(new_lines), dims