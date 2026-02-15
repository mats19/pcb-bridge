// Makro für OpenBuilds CONTROL
// Upload von Gerber-Dateien, Verarbeitung via pcb2gcode und Leveling

(function() {
    var content = `
        <div class="p-2">
            <h5>Gerber Processing & Leveling</h5>
            <hr>
            <form id="gerberForm">
                <div class="mb-2">
                    <label>Front Copper (Gerber) <span id="lbl_front" class="text-muted text-small"></span></label>
                    <input type="file" id="file_front" data-role="file" data-button-title="Select">
                </div>
                <div class="mb-2">
                    <label>Outline / Edge Cuts <span id="lbl_outline" class="text-muted text-small"></span></label>
                    <input type="file" id="file_outline" data-role="file" data-button-title="Select">
                </div>
                <div class="mb-2">
                    <label>Drill File <span id="lbl_drill" class="text-muted text-small"></span></label>
                    <input type="file" id="file_drill" data-role="file" data-button-title="Select">
                </div>
                <div class="row mb-2">
                    <div class="cell-6">
                        <label>Milling Depth (Z-Work)</label>
                        <input type="number" id="val_zwork" value="-0.1" step="0.05" data-role="input">
                    </div>
                    <div class="cell-6">
                        <label>Feed Rate</label>
                        <input type="number" id="val_feed" value="200" data-role="input">
                    </div>
                </div>
                <div class="row mb-2">
                    <div class="cell-6">
                        <label>Offset X [mm]</label>
                        <input type="number" id="val_offset_x" value="0" data-role="input">
                    </div>
                    <div class="cell-6">
                        <label>Offset Y [mm]</label>
                        <input type="number" id="val_offset_y" value="0" data-role="input">
                    </div>
                </div>
            </form>
            
            <div id="result_area" style="display:none;" class="mt-2 border p-2">
                <h6>Show Result:</h6>
                <div id="dimensions_info" class="text-small mb-2 text-muted"></div>
                <div class="row">
                    <div class="cell-12" id="view_buttons"></div>
                </div>
            </div>

            <div class="mt-4">
                <button class="button success w-100" id="btn_process">
                    <span class="mif-cogs"></span> Process & Level
                </button>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge - Gerber",
        content: content,
        width: 500,
        actions: [{ caption: "Close", cls: "js-dialog-close" }],
        onShow: function(dialog) {
            var el = dialog.element;
            // Speicher für die geladenen G-Codes
            var currentGcodeData = { front: null, outline: null, drill: null };
            var currentDimensions = { front: null, outline: null, drill: null };

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

            function updateDimensionsInfo(dims) {
                var div = el.find('#dimensions_info');
                if (dims) {
                    div.html(`<b>Dimensions:</b> ${dims.width.toFixed(2)} x ${dims.height.toFixed(2)} mm <br> 
                              <b>Range:</b> X: ${dims.min_x.toFixed(2)}..${dims.max_x.toFixed(2)} / Y: ${dims.min_y.toFixed(2)}..${dims.max_y.toFixed(2)} <br>
                              <b>Z-Range (Final):</b> ${dims.min_z.toFixed(3)} .. ${dims.max_z.toFixed(3)} mm`);
                } else {
                    div.html('');
                }
            }

            function renderViewButtons() {
                var container = el.find('#view_buttons');
                container.html('');
                el.find('#result_area').show();

                var map = {
                    'front': { label: 'Front (Traces)', icon: 'mif-flow-line', cls: 'primary' },
                    'outline': { label: 'Outline (Cut)', icon: 'mif-cut', cls: 'alert' },
                    'drill': { label: 'Drill (Holes)', icon: 'mif-more-vert', cls: 'warning' }
                };

                Object.keys(currentGcodeData).forEach(key => {
                    if (currentGcodeData[key]) {
                        var btn = $(`<button class="button small ${map[key].cls} mr-1"><span class="${map[key].icon}"></span> ${map[key].label}</button>`);
                        btn.on('click', function() {
                            updateEditor(currentGcodeData[key]);
                            updateDimensionsInfo(currentDimensions[key]);
                            Metro.toast.create(map[key].label + " loaded.", null, 1000, "info");
                        });
                        container.append(btn);
                    }
                });
            }

            function loadLatestData() {
                fetch('http://127.0.0.1:8000/process/latest')
                .then(r => r.json())
                .then(data => {
                    if (data.status === "success" && data.gcode) {
                        currentGcodeData = data.gcode;
                        currentDimensions = data.dimensions || {};
                        renderViewButtons();
                        
                        // Automatisch Front laden, wenn vorhanden
                        if (currentGcodeData.front) {
                            updateEditor(currentGcodeData.front);
                            updateDimensionsInfo(currentDimensions.front);
                            Metro.toast.create("Latest processing loaded.", null, 2000, "success");
                        }
                        
                        // Formularwerte wiederherstellen (optional)
                        if (data.config) {
                            if(data.config.z_work) el.find('#val_zwork').val(data.config.z_work);
                            if(data.config.feed_rate) el.find('#val_feed').val(data.config.feed_rate);
                            if(data.config.offset_x) el.find('#val_offset_x').val(data.config.offset_x);
                            if(data.config.offset_y) el.find('#val_offset_y').val(data.config.offset_y);
                        }

                        // Dateinamen anzeigen
                        if (data.filenames) {
                            if(data.filenames.front) el.find('#lbl_front').text("(" + data.filenames.front + ")");
                            if(data.filenames.outline) el.find('#lbl_outline').text("(" + data.filenames.outline + ")");
                            if(data.filenames.drill) el.find('#lbl_drill').text("(" + data.filenames.drill + ")");
                        }
                    }
                })
                .catch(e => {
                    console.log("No previous data or error:", e);
                });
            }

            // Beim Start versuchen, alte Daten zu laden
            loadLatestData();

            el.find('#btn_process').on('click', function() {
                var formData = new FormData();
                
                var fFront = el.find('#file_front')[0].files[0];
                var fOutline = el.find('#file_outline')[0].files[0];
                var fDrill = el.find('#file_drill')[0].files[0];

                if(fFront) formData.append("front", fFront);
                if(fOutline) formData.append("outline", fOutline);
                if(fDrill) formData.append("drill", fDrill);

                formData.append("z_work", el.find('#val_zwork').val());
                formData.append("feed_rate", el.find('#val_feed').val());
                formData.append("offset_x", el.find('#val_offset_x').val());
                formData.append("offset_y", el.find('#val_offset_y').val());

                Metro.toast.create("Processing...", null, 2000, "info");

                fetch('http://127.0.0.1:8000/process/pcb', {
                    method: 'POST',
                    body: formData
                })
                .then(r => r.json())
                .then(data => {
                    if(data.status === "success") {
                        Metro.toast.create("Processing successful!", null, 3000, "success");
                        
                        currentGcodeData = data.gcode;
                        currentDimensions = data.dimensions || {};
                        renderViewButtons();
                        
                        // Dateinamen aktualisieren (falls neu hochgeladen)
                        if (data.filenames) {
                            if(data.filenames.front) el.find('#lbl_front').text("(" + data.filenames.front + ")");
                            if(data.filenames.outline) el.find('#lbl_outline').text("(" + data.filenames.outline + ")");
                            if(data.filenames.drill) el.find('#lbl_drill').text("(" + data.filenames.drill + ")");
                        }

                        // Standardmäßig Front anzeigen
                        if (data.gcode.front) {
                            updateEditor(data.gcode.front);
                            updateDimensionsInfo(currentDimensions.front);
                        }
                    } else {
                        Metro.toast.create("Error: " + JSON.stringify(data), null, 5000, "alert");
                    }
                })
                .catch(e => {
                    Metro.toast.create("Backend Error: " + e, null, 3000, "alert");
                });
            });
        }
    });
})();