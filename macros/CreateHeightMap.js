// Makro für OpenBuilds CONTROL
// Erstellt einen Dialog zur Eingabe der PCB-Dimensionen und sendet diese an das Python-Backend

(function() {
    var content = `
        <div class="p-2">
            <h5>Probe-Raster Konfiguration</h5>
            <hr>
            <div class="row mb-2">
                <div class="cell-6">
                    <label>Größe X [mm]</label>
                    <input type="number" id="pb_width" data-role="input" value="50" data-append="mm">
                </div>
                <div class="cell-6">
                    <label>Größe Y [mm]</label>
                    <input type="number" id="pb_height" data-role="input" value="30" data-append="mm">
                </div>
            </div>
            <div class="row mb-2">
                <div class="cell-6">
                    <label>Punkte X</label>
                    <input type="number" id="pb_px" data-role="input" value="5">
                </div>
                <div class="cell-6">
                    <label>Punkte Y</label>
                    <input type="number" id="pb_py" data-role="input" value="3">
                </div>
            </div>
            <div class="row mt-4">
                <div class="cell-12">
                    <button class="button primary w-100" id="pb_sim">
                        <span class="mif-magic-wand"></span> Simulation (Testdaten erzeugen)
                    </button>
                    <button class="button alert w-100 mt-2" id="pb_probe">
                        <span class="mif-target"></span> Start Probing (Echt)
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
                caption: "Schließen",
                cls: "js-dialog-close"
            }
        ],
        onShow: function(dialog) {
            var el = dialog.element;
            
            function getPayload() {
                var w = parseFloat(el.find('#pb_width').val());
                var h = parseFloat(el.find('#pb_height').val());
                var px = parseInt(el.find('#pb_px').val());
                var py = parseInt(el.find('#pb_py').val());
                if (isNaN(w) || isNaN(h) || isNaN(px) || isNaN(py)) {
                    Metro.toast.create("Bitte gültige Zahlen eingeben.", null, 3000, "alert");
                    return null;
                }
                return {
                    width: w,
                    height: h,
                    points_x: px,
                    points_y: py
                };
            }

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
                    Metro.toast.create("Simulation fertig! " + data.points.length + " Punkte generiert.", null, 3000, "success");
                    console.log(data);
                    Metro.toast.create("Visualisierungs-Datei gespeichert: " + data.viz_file, null, 3000, "info");
                })
                .catch(e => {
                    Metro.toast.create("Fehler: " + e, null, 3000, "alert");
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
                
                Metro.toast.create("Probing-Logik muss noch implementiert werden (siehe Code-Kommentare)", null, 5000, "info");
            });
        }
    });
})();