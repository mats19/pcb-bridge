// Macro for OpenBuilds CONTROL
// Creates a dialog to input PCB dimensions and sends them to the Python backend

(function() {
    var content = `
        <div class="p-2">
            <div class="row mb-2">
                <div class="cell-6">
                    <label>Size X [mm]</label>
                    <input type="number" id="pb_width" data-role="input" value="50" data-append="mm">
                </div>
                <div class="cell-6">
                    <label>Size Y [mm]</label>
                    <input type="number" id="pb_height" data-role="input" value="30" data-append="mm">
                </div>
            </div>
            <div class="row mb-2">
                <div class="cell-6">
                    <label>Points X</label>
                    <input type="number" id="pb_px" data-role="input" value="5">
                </div>
                <div class="cell-6">
                    <label>Points Y</label>
                    <input type="number" id="pb_py" data-role="input" value="3">
                </div>
            </div>
            
            <div class="d-flex flex-justify-between flex-align-center mt-2 mb-2">
                <div id="probe_stats" class="text-small text-muted border p-1 mr-2" style="display:none; flex-grow: 1;"></div>
                <button class="button small warning outline" id="pb_reset" title="Reset Data"><span class="mif-bin"></span> Reset</button>
            </div>

            <div class="row">
                <div class="cell-6">
                    <button class="button primary w-100" id="pb_sim">
                        <span class="mif-magic-wand"></span> Simulation
                    </button>
                </div>
                <div class="cell-6">
                    <button class="button alert w-100" id="pb_probe">
                        <span class="mif-target"></span> Probing
                    </button>
                </div>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge - Probe Grid",
        content: content,
        width: 450,
        actions: [
            {
                caption: "Close",
                cls: "js-dialog-close"
            }
        ],
        onShow: function(dialog) {
            var el = dialog.element;
            
            function updateEditor(gCode) {
                // 1. Write code to editor
                if (typeof editor !== 'undefined' && editor.session) {
                    editor.session.setValue(gCode);
                    if (typeof printLog === "function") printLog("Editor content updated.");
                }

                // 2. Update 3D viewer
                if (typeof parseGcodeInWebWorker === "function") {
                    parseGcodeInWebWorker(editor.getValue());
                    if (typeof printLog === "function") printLog("3D View refresh triggered.");
                }

                // 3. Center viewport
                if (typeof resetView === "function") resetView();
            }

            function getPayload() {
                var w = parseFloat(el.find('#pb_width').val());
                var h = parseFloat(el.find('#pb_height').val());
                var px = parseInt(el.find('#pb_px').val());
                var py = parseInt(el.find('#pb_py').val());
                if (isNaN(w) || isNaN(h) || isNaN(px) || isNaN(py)) {
                    Metro.toast.create("Please enter valid numbers.", null, 3000, "alert");
                    return null;
                }
                return {
                    width: w,
                    height: h,
                    points_x: px,
                    points_y: py
                };
            }

            function updateStats(points) {
                var div = el.find('#probe_stats');
                if (!points || points.length === 0) {
                    div.hide();
                    return;
                }
                
                var minZ = Infinity;
                var maxZ = -Infinity;
                points.forEach(p => {
                    if (p.z < minZ) minZ = p.z;
                    if (p.z > maxZ) maxZ = p.z;
                });
                
                div.html(`<b>Probe Stats:</b> Min Z: ${minZ.toFixed(4)} mm | Max Z: ${maxZ.toFixed(4)} mm | Delta: ${(maxZ - minZ).toFixed(4)} mm`);
                div.show();
            }

            function loadProbeData(isAutoLoad) {
                if (!isAutoLoad) Metro.toast.create("Loading data...", null, 1000, "info");
                
                fetch('http://127.0.0.1:8000/probe/latest')
                .then(r => r.json())
                .then(data => {
                    if(data.status === "success") {
                        if (!isAutoLoad) Metro.toast.create("Loaded! " + data.points.length + " points.", null, 3000, "success");
                        
                        // Update config fields if available
                        if(data.config) {
                            el.find('#pb_width').val(data.config.width);
                            el.find('#pb_height').val(data.config.height);
                            el.find('#pb_px').val(data.config.points_x);
                            el.find('#pb_py').val(data.config.points_y);
                        }

                        // Show visualization
                        if(data.viz_gcode) {
                            updateEditor(data.viz_gcode);
                        }
                        
                        // Show stats
                        updateStats(data.points);
                    } else {
                        if (!isAutoLoad) Metro.toast.create("No saved data found.", null, 3000, "warning");
                    }
                })
                .catch(e => {
                    if (!isAutoLoad) Metro.toast.create("Error loading: " + e, null, 3000, "alert");
                });
            }

            // Automatically load on open
            loadProbeData(true);

            // Reset Button
            el.find('#pb_reset').on('click', function() {
                fetch('http://127.0.0.1:8000/probe/reset', { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    Metro.toast.create("Probe data reset.", null, 1000, "info");
                    
                    // Reset UI to defaults
                    el.find('#pb_width').val(50);
                    el.find('#pb_height').val(30);
                    el.find('#pb_px').val(5);
                    el.find('#pb_py').val(3);
                    el.find('#probe_stats').hide();
                    
                    // Clear editor
                    if (typeof editor !== 'undefined' && editor.session) editor.session.setValue("");
                    if (typeof parseGcodeInWebWorker === "function") parseGcodeInWebWorker("");
                });
            });

            el.find('#pb_sim').on('click', function() {
                var payload = getPayload();
                if(!payload) return;

                // Simulation
                fetch('http://127.0.0.1:8000/probe/simulate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    Metro.toast.create("Simulation complete! " + data.points.length + " points generated.", null, 3000, "success");
                    console.log(data);
                    if (data.viz_gcode) updateEditor(data.viz_gcode);
                    updateStats(data.points);
                })
                .catch(e => {
                    Metro.toast.create("Error: " + e, null, 3000, "alert");
                });
            });

            el.find('#pb_probe').on('click', function() {
                var payload = getPayload();
                if(!payload) return;

                if (payload.points_x < 2 || payload.points_y < 2) {
                    Metro.toast.create("Please specify at least 2 points per axis.", null, 3000, "alert");
                    return;
                }

                // Configuration
                var zSafe = 2.0;       // Retract height [mm]
                var zProbeMin = -5.0;  // Max depth [mm]
                var feed = 100;        // Probing feed rate [mm/min]

                // Generate points
                var points = [];
                var stepX = payload.width / (payload.points_x - 1);
                var stepY = payload.height / (payload.points_y - 1);

                for(var y=0; y < payload.points_y; y++) {
                    for(var x=0; x < payload.points_x; x++) {
                        points.push({
                            x: x * stepX,
                            y: y * stepY
                        });
                    }
                }

                var results = [];
                var currentIndex = 0;
                var btn = $(this);
                
                btn.prop('disabled', true);
                Metro.toast.create("Probing started...", null, 2000, "info");

                // Disable old listeners to be safe
                socket.off('prbResult');

                // Listener for Probe Results
                // Logic adapted from 'findCircleCenter' macro (event-driven approach)
                var onProbeResult = function(prbdata) {
                    if (prbdata.state) {
                        // Success
                        results.push({
                            x: points[currentIndex].x,
                            y: points[currentIndex].y,
                            z_raw: prbdata.z
                        });

                        currentIndex++;
                        nextPoint();
                    } else {
                        // Failed
                        Metro.toast.create("Probe failed at point " + (currentIndex + 1), null, 5000, "alert");
                        finishProbing(false);
                    }
                };

                socket.on('prbResult', onProbeResult);

                function nextPoint() {
                    if (currentIndex >= points.length) {
                        finishProbing(true);
                        return;
                    }
                    var p = points[currentIndex];
                    
                    // Construct G-code block: Move to XY, then Probe Z
                    var gcode = `G90\nG0 Z${zSafe}\nG0 X${p.x.toFixed(3)} Y${p.y.toFixed(3)}\nG38.2 Z${zProbeMin} F${feed}`;
                    
                    socket.emit('runJob', {
                        data: gcode,
                        isJob: false,
                        completedMsg: false,
                        fileName: ""
                    });
                }

                function finishProbing(success) {
                    socket.off('prbResult', onProbeResult);
                    btn.prop('disabled', false);
                    
                    // Retract safely
                    socket.emit('runJob', {
                        data: `G0 Z${zSafe}`,
                        isJob: false,
                        completedMsg: false,
                        fileName: ""
                    });

                    if (success && results.length > 0) {
                        // Normalization: Z relative to the first point (0,0)
                        var refZ = results[0].z_raw;
                        var finalPoints = results.map(p => ({
                            x: p.x,
                            y: p.y,
                            z: p.z_raw - refZ
                        }));

                        var finalPayload = { config: payload, points: finalPoints };

                        fetch('http://127.0.0.1:8000/probe/save', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(finalPayload)
                        })
                        .then(r => r.json())
                        .then(data => {
                            Metro.toast.create("Probing finished! File saved.", null, 3000, "success");
                            console.log(data);
                            if (data.viz_gcode) updateEditor(data.viz_gcode);
                            updateStats(finalPoints);
                        })
                        .catch(e => {
                            Metro.toast.create("Error: " + e, null, 5000, "alert");
                        });
                    }
                }

                // Start the loop
                nextPoint();
            });
        }
    });
})();