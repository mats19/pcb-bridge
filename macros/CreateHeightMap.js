// Makro für OpenBuilds CONTROL
// Erstellt einen Dialog zur Eingabe der PCB-Dimensionen und sendet diese an das Python-Backend

(function() {
    var content = `
        <div class="p-2">
            <h5>Probe Grid Configuration</h5>
            <hr>
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
            
            <div id="probe_stats" class="mt-2 text-small text-muted border p-1" style="display:none;"></div>

            <div class="row mt-4">
                <div class="cell-12">
                    <button class="button primary w-100" id="pb_sim">
                        <span class="mif-magic-wand"></span> Simulation (Generate Test Data)
                    </button>
                    <button class="button alert w-100 mt-2" id="pb_probe">
                        <span class="mif-target"></span> Start Probing (Real)
                    </button>
                </div>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge",
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
                // 1. Code in den Editor schreiben
                if (typeof editor !== 'undefined' && editor.session) {
                    editor.session.setValue(gCode);
                    if (typeof printLog === "function") printLog("Editor content updated.");
                }

                // 2. Den 3D-Viewer aktualisieren
                if (typeof parseGcodeInWebWorker === "function") {
                    parseGcodeInWebWorker(editor.getValue());
                    if (typeof printLog === "function") printLog("3D View refresh triggered.");
                }

                // 3. Viewport zentrieren
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
                        
                        // Config Felder updaten, falls vorhanden
                        if(data.config) {
                            el.find('#pb_width').val(data.config.width);
                            el.find('#pb_height').val(data.config.height);
                            el.find('#pb_px').val(data.config.points_x);
                            el.find('#pb_py').val(data.config.points_y);
                        }

                        // Visualisierung anzeigen
                        if(data.viz_gcode) {
                            updateEditor(data.viz_gcode);
                        }
                        
                        // Stats anzeigen
                        updateStats(data.points);
                    } else {
                        if (!isAutoLoad) Metro.toast.create("No saved data found.", null, 3000, "warning");
                    }
                })
                .catch(e => {
                    if (!isAutoLoad) Metro.toast.create("Error loading: " + e, null, 3000, "alert");
                });
            }

            // Automatisch laden beim Öffnen
            loadProbeData(true);

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

                // Hier würde die echte Logik stehen:
                // 1. Loop über x/y Koordinaten (in JS berechnet)
                // 2. socket.emit('run', 'G0 X... Y...')
                // 3. socket.emit('run', 'G38.2 Z-5 F100')
                // 4. Warten auf socket message mit "[PRB:x,y,z:state]"
                // 5. Daten sammeln und am Ende an /probe/save senden
                if (payload.points_x < 2 || payload.points_y < 2) {
                    Metro.toast.create("Please specify at least 2 points per axis.", null, 3000, "alert");
                    return;
                }

                // Konfiguration
                var zSafe = 2.0;       // Rückzugshöhe [mm]
                var zProbeMin = -5.0;  // Maximale Tiefe [mm]
                var feed = 100;        // Probing Geschwindigkeit [mm/min]

                // Punkte generieren
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
                var probingActive = true;
                var btn = $(this);
                
                Metro.toast.create("Probing logic needs to be implemented (see code comments)", null, 5000, "info");
                btn.prop('disabled', true);
                Metro.toast.create("Probing started...", null, 2000, "info");

                // Serial Listener für [PRB:...] Antworten
                var onSerial = function(data) {
                    if (!probingActive) return;
                    
                    var line = data;
                    if (typeof data === 'object' && data.line) line = data.line;
                    if (typeof line !== 'string') return;

                    if (line.indexOf('[PRB:') !== -1) {
                        // Parse [PRB:x,y,z:state]
                        var content = line.substring(line.indexOf('[PRB:') + 5, line.indexOf(']'));
                        var parts = content.split(':');
                        var coords = parts[0].split(',');
                        var mZ = parseFloat(coords[2]);

                        results.push({
                            x: points[currentIndex].x,
                            y: points[currentIndex].y,
                            z_raw: mZ
                        });

                        // Retract
                        socket.emit('run', 'G0 Z' + zSafe);
                        currentIndex++;
                        setTimeout(nextPoint, 200);
                    }
                };

                socket.on('serial', onSerial);

                function nextPoint() {
                    if (currentIndex >= points.length) {
                        finishProbing();
                        return;
                    }
                    var p = points[currentIndex];
                    socket.emit('run', 'G0 X' + p.x.toFixed(3) + ' Y' + p.y.toFixed(3));
                    socket.emit('run', 'G38.2 Z' + zProbeMin + ' F' + feed);
                }

                function finishProbing() {
                    probingActive = false;
                    socket.off('serial', onSerial);
                    btn.prop('disabled', false);

                    if (results.length > 0) {
                        // Normalisierung: Z relativ zum ersten Punkt (0,0)
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

                // Start: Zuerst auf Safe Height, dann erster Punkt
                socket.emit('run', 'G0 Z' + zSafe);
                setTimeout(nextPoint, 500);
            });
        }
    });
})();