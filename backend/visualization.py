import os
import json
import matplotlib
# Set backend to 'Agg' to prevent GUI windows on server
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

# Standard-Theme verwenden (hell)
plt.style.use('default')

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
        
        ax = plt.gca()
        ax.set_facecolor('#E8E8E8')
        plt.gcf().patch.set_facecolor('#E8E8E8')
        
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
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#E8E8E8')
        plt.close()
        return True
    except Exception as e:
        print(f"Visualization Error (Heightmap): {e}")
        return False

def generate_gcode_image(gcode_path: str, output_path: str) -> bool:
    """Generates a plot of the G-code path colored by Z-height."""
    if not os.path.exists(gcode_path):
        return False
        
    try:
        segments = []
        zs_mean = []
        drill_pts = []
        drill_zs = []
        
        with open(gcode_path, "r") as f:
            current_x, current_y, current_z = 0.0, 0.0, 0.0
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
                        if current_x == new_x and current_y == new_y:
                            drill_pts.append((new_x, new_y))
                            drill_zs.append((current_z + new_z) / 2.0)
                        else:
                            segments.append([(current_x, current_y), (new_x, new_y)])
                            zs_mean.append((current_z + new_z) / 2.0)
                    
                    current_x, current_y, current_z = new_x, new_y, new_z

        if segments or drill_pts:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.set_facecolor('#E8E8E8')
            fig.patch.set_facecolor('#E8E8E8')
            
            all_z = zs_mean + drill_zs
            max_val = max(max([abs(v) for v in all_z]), 0.05)
            
            plot_elem = None
            if segments:
                lc = LineCollection(segments, cmap="RdYlBu_r", alpha=0.9, linewidths=1.5)
                lc.set_array(np.array(zs_mean))
                lc.set_clim(-max_val, max_val)
                plot_elem = ax.add_collection(lc)
                
            if drill_pts:
                sc = ax.scatter([p[0] for p in drill_pts], [p[1] for p in drill_pts], 
                                c=drill_zs, cmap="RdYlBu_r", s=15, vmin=-max_val, vmax=max_val, zorder=3)
                if not plot_elem: plot_elem = sc
                
            all_xs = [pt[0] for seg in segments for pt in seg] + [p[0] for p in drill_pts]
            all_ys = [pt[1] for seg in segments for pt in seg] + [p[1] for p in drill_pts]
            if all_xs and all_ys:
                ax.set_xlim(min(all_xs) - 1, max(all_xs) + 1)
                ax.set_ylim(min(all_ys) - 1, max(all_ys) + 1)
                
            if plot_elem:
                plt.colorbar(plot_elem, label="Z Height [mm]", orientation='horizontal', pad=0.15, extend='both')
                
            plt.title("Leveled G-Code Path (Z-Coloring)")
            plt.xlabel("X [mm]")
            plt.ylabel("Y [mm]")
            ax.set_aspect('equal', adjustable='box')
            
            plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#E8E8E8')
            plt.close()
            return True
        return False
    except Exception as e:
        print(f"Visualization Error (GCode): {e}")
        return False