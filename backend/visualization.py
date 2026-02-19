import os
import json
import matplotlib
# Set backend to 'Agg' to prevent GUI windows on server
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def generate_heightmap_image(probe_file: str, output_path: str) -> bool:
    """Generates a heatmap image from the probe data."""
    if not os.path.exists(probe_file):
        return False
    
    try:
        with open(probe_file, "r") as f:
            data = json.load(f)
        
        points = data.get("points", [])
        if not points:
            return False

        x = [p['x'] for p in points]
        y = [p['y'] for p in points]
        z = [p['z'] for p in points]
        
        plt.figure(figsize=(10, 6))
        
        # Determine symmetric range for colorbar to keep 0 neutral
        max_val = max(max([abs(v) for v in z]), 0.05)
        levels = np.linspace(-max_val, max_val, 21)
        
        # Create a triangulation for interpolation/plotting
        cntr = plt.tricontourf(x, y, z, levels=levels, cmap="RdYlBu_r", extend="both")
        plt.colorbar(cntr, label="Z Height [mm]", orientation='horizontal', pad=0.15)
        plt.scatter(x, y, c='black', s=10, label='Probe Points')
        plt.title("PCB Heightmap Interpolation")
        plt.xlabel("X [mm]")
        plt.ylabel("Y [mm]")
        plt.legend()
        plt.axis('equal')
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        return True
    except Exception as e:
        print(f"Visualization Error (Heightmap): {e}")
        return False

def generate_gcode_image(gcode_path: str, output_path: str) -> bool:
    """Generates a scatter plot of the G-code path colored by Z-height."""
    if not os.path.exists(gcode_path):
        return False
        
    try:
        xs, ys, zs = [], [], []
        
        with open(gcode_path, "r") as f:
            current_x, current_y, current_z = 0, 0, 0
            for line in f:
                line = line.strip()
                if not line or line.startswith(";") or line.startswith("("): continue
                
                upline = line.upper()
                
                # Check for cut commands (G1, G01) or Canned Cycles (G81, G82, G83)
                is_cut = "G1" in upline or "G01" in upline or \
                         "G81" in upline or "G82" in upline or "G83" in upline
                
                # Check for rapid commands
                is_rapid = "G0" in upline or "G00" in upline
                
                if is_cut or is_rapid:
                    parts = upline.split()
                    new_x, new_y, new_z = current_x, current_y, current_z
                    
                    for p in parts:
                        try:
                            if p.startswith("X"): new_x = float(p[1:])
                            if p.startswith("Y"): new_y = float(p[1:])
                            if p.startswith("Z"): new_z = float(p[1:])
                        except ValueError:
                            pass
                    
                    if is_cut:
                        xs.append(new_x)
                        ys.append(new_y)
                        zs.append(new_z)
                    
                    current_x, current_y, current_z = new_x, new_y, new_z

        if xs:
            plt.figure(figsize=(10, 6))
            
            # Determine symmetric range for colorbar to keep 0 neutral (like heightmap)
            max_val = max(max([abs(v) for v in zs]), 0.05)
            
            sc = plt.scatter(xs, ys, c=zs, cmap="RdYlBu_r", s=1, alpha=0.5, vmin=-max_val, vmax=max_val)
            plt.colorbar(sc, label="Z Height [mm]", orientation='horizontal', pad=0.15, extend='both')
            plt.title("Leveled G-Code Path (Z-Coloring)")
            plt.xlabel("X [mm]")
            plt.ylabel("Y [mm]")
            plt.axis('equal')
            
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            return True
        return False
    except Exception as e:
        print(f"Visualization Error (GCode): {e}")
        return False