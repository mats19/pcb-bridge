import os
import gerber
from gerber.primitives import Region, Line
from shapely.geometry import Polygon, LineString
import shapely.affinity
import math
import re

class PocketingGenerator:
    def __init__(self, config_file):
        self.config_file = config_file

    def parse_config(self):
        config = {
            "tool-diameter": "5.0mm",
            "z-pocket": "-0.1mm",
            "pocket-feed": "500mm/min",
            "spindle-speed": "24000rpm",
            "stepover": "0.5"
        }
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.split('#')[0].strip()
                    if not line or '=' not in line: continue
                    k, v = line.split('=', 1)
                    config[k.strip()] = v.strip()
        return config

    def generate(self, gerber_path, output_path, auto_mirror_x=False):
        config = self.parse_config()
        
        # Parameter extrahieren
        try:
            tool_dia = float(config.get("tool-diameter", "5.0mm").replace("mm", ""))
            z_pocket = float(config.get("z-pocket", "-0.1mm").replace("mm", ""))
            f_pocket = float(config.get("pocket-feed", "500mm/min").replace("mm/min", ""))
            s_speed = int(config.get("spindle-speed", "24000rpm").replace("rpm", ""))
            stepover_ratio = float(config.get("stepover", "0.5"))
            
            # Neue Korrekturparameter
            scale_factor = float(config.get("scale", "1.0"))
            mirror_x = int(config.get("mirror-x", "0"))
            mirror_y = int(config.get("mirror-y", "0"))
            off_x = float(config.get("offset-x", "0.0").replace("mm", ""))
            off_y = float(config.get("offset-y", "0.0").replace("mm", ""))
        except ValueError:
            tool_dia, z_pocket, f_pocket, s_speed, stepover_ratio = 5.0, -0.1, 500, 24000, 0.5
            scale_factor, mirror_x, mirror_y, off_x, off_y = 1.0, 0, 0, 0.0, 0.0

        tool_radius = tool_dia / 2.0
        stepover_mm = tool_dia * stepover_ratio

        gcode = [
            "; --- User Drawings Pocketing ---",
            f"; Tool Diameter: {tool_dia} mm",
            f"; Depth: {z_pocket} mm",
            f"; Stepover: {stepover_mm} mm",
            "G21",
            "G90",
            f"S{s_speed} M3"
        ]

        try:
            cam = gerber.read(gerber_path)
            cam.to_metric() # Sicherstellen, dass wir in Millimetern rechnen
        except Exception as e:
            gcode.append(f"; Fehler beim Lesen der Gerber-Datei: {e}")
            with open(output_path, 'w') as f:
                f.write("\n".join(gcode) + "\n")
            return

        # Polygone aus Gerber-Regionen (G36) extrahieren
        polygons = []
        for prim in cam.primitives:
            if isinstance(prim, Region):
                pts = []
                for sub_p in prim.primitives:
                    if hasattr(sub_p, 'start') and hasattr(sub_p, 'end'):
                        if not pts: pts.append(sub_p.start)
                        pts.append(sub_p.end)
                if len(pts) >= 3:
                    poly = Polygon(pts)
                    
                    # Korrekturen anwenden
                    if scale_factor != 1.0:
                        poly = shapely.affinity.scale(poly, xfact=scale_factor, yfact=scale_factor, origin=(0, 0))
                        
                    if mirror_x == 1 or auto_mirror_x:
                        poly = shapely.affinity.scale(poly, xfact=-1.0, yfact=1.0, origin=(0, 0))
                        
                    if mirror_y == 1:
                        poly = shapely.affinity.scale(poly, xfact=1.0, yfact=-1.0, origin=(0, 0))
                        
                    if off_x != 0.0 or off_y != 0.0:
                        poly = shapely.affinity.translate(poly, xoff=off_x, yoff=off_y)
                        
                    polygons.append(poly)

        gcode.append("G0 Z2.0")

        for i, poly in enumerate(polygons):
            gcode.append(f"\n; --- Pocket {i+1} ---")
            
            # 1. Offset nach innen (Fräserradius)
            offset_poly = poly.buffer(-tool_radius)
            
            if offset_poly.is_empty:
                gcode.append("; Polygon zu klein für diesen Fraeser. Uebersprungen.")
                continue
                
            # Falls das Polygon durch den Offset in mehrere Teile zerfällt (MultiPolygon)
            geoms = offset_poly.geoms if hasattr(offset_poly, 'geoms') else [offset_poly]
            
            for geom_idx, geom in enumerate(geoms):
                minx, miny, maxx, maxy = geom.bounds
                
                # 2. X-parallele Zick-Zack Pfade berechnen
                y = miny
                zigzag_paths = []
                left_to_right = True
                
                while y <= maxy:
                    scan_line = LineString([(minx - 1, y), (maxx + 1, y)])
                    intersection = scan_line.intersection(geom)
                    
                    if not intersection.is_empty:
                        parts = intersection.geoms if hasattr(intersection, 'geoms') else [intersection]
                        for part in parts:
                            if isinstance(part, LineString):
                                coords = list(part.coords)
                                if not left_to_right:
                                    coords.reverse()
                                zigzag_paths.append(coords)
                    
                    y += stepover_mm
                    left_to_right = not left_to_right

                # 3. Zick-Zack G-Code schreiben
                if zigzag_paths:
                    gcode.append(f"; Zig-Zag Clearing (Teil {geom_idx+1})")
                    start_pt = zigzag_paths[0][0]
                    gcode.append(f"G0 X{start_pt[0]:.4f} Y{start_pt[1]:.4f}")
                    gcode.append(f"G1 Z{z_pocket:.4f} F{f_pocket}") # Eintauchen
                    
                    for path in zigzag_paths:
                        gcode.append(f"G1 X{path[0][0]:.4f} Y{path[0][1]:.4f} F{f_pocket}")
                        for pt in path[1:]:
                            gcode.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F{f_pocket}")
                            
                    gcode.append("G0 Z2.0") # Rückzug nach dem Zick-Zack

                # 4. Innenkontur abfahren (Finishing Pass)
                contour_coords = list(geom.exterior.coords)
                if contour_coords:
                    gcode.append(f"; Contour Finishing Pass (Teil {geom_idx+1})")
                    start_pt = contour_coords[0]
                    gcode.append(f"G0 X{start_pt[0]:.4f} Y{start_pt[1]:.4f}")
                    gcode.append(f"G1 Z{z_pocket:.4f} F{f_pocket}")
                    for pt in contour_coords[1:]:
                        gcode.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F{f_pocket}")
                    gcode.append("G0 Z2.0")

        gcode.append("\nM5") # Spindel aus

        with open(output_path, 'w') as f:
            f.write("\n".join(gcode) + "\n")