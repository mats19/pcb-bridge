// Macro for OpenBuilds CONTROL
// Upload of Gerber files, processing via pcb2gcode, and leveling

(function() {
    var content = `
        <div class="p-2">
            <div class="row">
                <div class="cell-7">
                    <form id="gerberForm">
                        <div class="mb-2">
                        <label>Projekt-Ordner auswählen</label>
                        <input type="file" id="folder_input" webkitdirectory directory multiple data-role="file" data-button-title="Ordner öffnen">
                        </div>
                    
                    <div id="detected_files" class="text-small text-muted mb-2 border p-2 bg-light" style="display:none;">
                        <!-- Detected files will be listed here -->
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
                    
                    <div class="d-flex flex-justify-between flex-align-center mt-2 mb-2">
                        <div id="dimensions_info" class="text-small text-muted border p-1 mr-2" style="display:none; flex-grow: 1;"></div>
                        <button class="button small warning outline" id="btn_reset" title="Reset All"><span class="mif-bin"></span> Reset</button>
                    </div>

                    <div class="d-flex flex-row flex-wrap w-100 mb-2" id="view_buttons" style="display:none; gap: 5px;"></div>

                    <div class="mt-2">
                        <button class="button success w-100" id="btn_process">
                            <span class="mif-cogs"></span> Process & Level
                        </button>
                    </div>
                </div>
                <div class="cell-5 text-center d-flex flex-align-center flex-justify-center">
                    <div id="viz_container" style="display:none; width: 100%;">
                        <img id="viz_img" src="" style="width: 100%; border: 1px solid #ccc; max-height: 350px; object-fit: contain;">
                        <div class="mt-1">
                            <a id="viz_link" href="#" target="_blank" class="text-small">Open full size <span class="mif-external"></span></a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge - Gerber Processing",
        content: content,
        width: 750,
        actions: [{ caption: "Close", cls: "js-dialog-close" }],
        onShow: function(dialog) {
            var el = dialog.element;
            var pendingFiles = { traces: null, outline: null, drill: null, user_drawings: null };
            
            // Storage for loaded G-codes
            var currentGcodeData = { traces: null, outline: null, drill: null, user_drawings: null };
            var currentDimensions = { traces: null, outline: null, drill: null, user_drawings: null };
            var currentToolMetadata = {};

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

            function updateDimensionsInfo(dims) {
                var div = el.find('#dimensions_info');
                if (dims) {
                    div.html(`<b>Leveling Stats:</b> ${dims.width.toFixed(2)} x ${dims.height.toFixed(2)} mm <br> 
                              <b>Range:</b> X: ${dims.min_x.toFixed(2)}..${dims.max_x.toFixed(2)} / Y: ${dims.min_y.toFixed(2)}..${dims.max_y.toFixed(2)} <br>
                              <b>Z-Range (Final):</b> ${dims.min_z.toFixed(3)} .. ${dims.max_z.toFixed(3)} mm`);
                    div.show();
                } else {
                    div.html('');
                    div.hide();
                }
            }

            function updateImage(type) {
                // Add timestamp to force refresh
                var t = type || 'traces';
                var url = "http://127.0.0.1:8000/data/viz_gcode_" + t + ".png?t=" + new Date().getTime();
                var img = el.find('#viz_img');
                var link = el.find('#viz_link');
                var container = el.find('#viz_container');
                
                var temp = new Image();
                temp.onload = function() { img.attr('src', url); link.attr('href', url); container.show(); };
                temp.onerror = function() { container.hide(); };
                temp.src = url;
            }

            function renderViewButtons() {
                var container = el.find('#view_buttons');
                container.html('');
                container.show();

                var map = {
                    'traces': { label: 'Traces', icon: 'mif-flow-line', cls: 'primary' },
                    'user_drawings': { label: 'Pocketing', icon: 'mif-layers', cls: 'info' },
                    'outline': { label: 'Outline', icon: 'mif-cut', cls: 'alert' },
                    'drill': { label: 'Drill', icon: 'mif-more-vert', cls: 'warning' }
                };

                var keys = Object.keys(currentGcodeData).sort((a, b) => {
                    var order = {'traces': 1, 'user_drawings': 2, 'outline': 3, 'drill': 4};
                    var oa = order[a] || 4;
                    var ob = order[b] || 5;
                    if (oa !== ob) return oa - ob;
                    return a.localeCompare(b);
                });

                keys.forEach(key => {
                    if (currentGcodeData[key]) {
                        var config = map[key];
                        var meta = currentToolMetadata[key];
                        
                        if (!config && key.startsWith('drill_')) {
                            var tName = key.replace('drill_', '');
                            config = { label: 'Holes ' + tName, icon: 'mif-more-vert', cls: 'secondary' };
                        }

                        if (config) {
                            var labelText = config.label;
                            if (meta) {
                                labelText += " (" + meta + ")";
                            }
                            
                            var btn = $(`<button class="button small ${config.cls} flex-fill"><span class="${config.icon}"></span> ${labelText}</button>`);
                            btn.on('click', function() {
                                updateEditor(currentGcodeData[key]);
                                updateDimensionsInfo(currentDimensions[key]);
                                updateImage(key);
                                Metro.toast.create(config.label + " loaded.", null, 1000, "info");
                            });
                            container.append(btn);
                        }
                    }
                });
            }

            // Handle folder selection
            el.find('#folder_input').on('change', function(e) {
                var files = e.target.files;
                pendingFiles = { traces: null, outline: null, drill: null, user_drawings: null };
                var html = "<b>Gefundene Dateien:</b><br>";
                
                for(var i=0; i<files.length; i++) {
                    var f = files[i];
                    if (f.name.endsWith('-B_Cu.gbr')) pendingFiles.traces = f;
                    else if (f.name.endsWith('-Edge_Cuts.gbr')) pendingFiles.outline = f;
                    else if (f.name.endsWith('.drl')) pendingFiles.drill = f;
                    else if (f.name.endsWith('-User_Drawings.gbr')) pendingFiles.user_drawings = f;
                }
                
                if(pendingFiles.traces) html += `<span class="fg-green mif-checkmark"></span> Traces: ${pendingFiles.traces.name}<br>`;
                if(pendingFiles.outline) html += `<span class="fg-green mif-checkmark"></span> Outline: ${pendingFiles.outline.name}<br>`;
                if(pendingFiles.drill) html += `<span class="fg-green mif-checkmark"></span> Drill: ${pendingFiles.drill.name}<br>`;
                if(pendingFiles.user_drawings) html += `<span class="fg-green mif-checkmark"></span> User Drawings: ${pendingFiles.user_drawings.name}<br>`;
                
                el.find('#detected_files').html(html).show();
            });

            function loadLatestData() {
                fetch('http://127.0.0.1:8000/process/latest')
                .then(r => r.json())
                .then(data => {
                    if (data.status === "success" && data.gcode) {
                        currentGcodeData = data.gcode;
                        currentDimensions = data.dimensions || {};
                        currentToolMetadata = data.tool_metadata || {};
                        renderViewButtons();
                        
                        // Automatically load Traces if available
                        if (currentGcodeData.traces) {
                            updateEditor(currentGcodeData.traces);
                            updateDimensionsInfo(currentDimensions.traces);
                            Metro.toast.create("Latest processing loaded.", null, 2000, "success");
                        }
                        
                        // Restore form values (optional)
                        if (data.config) {
                            if(data.config.offset_x) el.find('#val_offset_x').val(data.config.offset_x);
                            if(data.config.offset_y) el.find('#val_offset_y').val(data.config.offset_y);
                        }

                        // Display filenames
                        if (data.filenames) {
                        var html = "<b>Zuletzt geladene Dateien:</b><br>";
                        if(data.filenames.traces) html += `<span class="fg-green mif-checkmark"></span> Traces: ${data.filenames.traces}<br>`;
                        if(data.filenames.outline) html += `<span class="fg-green mif-checkmark"></span> Outline: ${data.filenames.outline}<br>`;
                        if(data.filenames.drill) html += `<span class="fg-green mif-checkmark"></span> Drill: ${data.filenames.drill}<br>`;
                        if(data.filenames.user_drawings) html += `<span class="fg-green mif-checkmark"></span> User Drawings: ${data.filenames.user_drawings}<br>`;
                        el.find('#detected_files').html(html).show();
                        }

                        // Show Image
                        if (currentGcodeData.traces) updateImage('traces');
                    else if (currentGcodeData.user_drawings) updateImage('user_drawings');
                        else if (currentGcodeData.outline) updateImage('outline');
                        else if (currentGcodeData.drill) updateImage('drill');
                    }
                })
                .catch(e => {
                    console.log("No previous data or error:", e);
                });
            }

            // Try to load old data on startup
            loadLatestData();

            // Reset Button
            el.find('#btn_reset').on('click', function() {
                fetch('http://127.0.0.1:8000/process/reset', { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    Metro.toast.create("Reset successful.", null, 1000, "info");
                    
                    // 1. Immediately hide/clear visual elements
                    el.find('#view_buttons').html('').hide();
                    el.find('#dimensions_info').html('').hide();
                    el.find('#detected_files').html('').hide();
                    pendingFiles = { traces: null, outline: null, drill: null, user_drawings: null };
                    el.find('#viz_container').hide();
                    
                    // 2. Clear internal data
                    currentGcodeData = { traces: null, outline: null, drill: null, user_drawings: null };
                    currentDimensions = { traces: null, outline: null, drill: null, user_drawings: null };
                    currentToolMetadata = {};
                    
                    // 3. Clear editor
                    if (typeof editor !== 'undefined' && editor.session) editor.session.setValue("");
                    if (typeof parseGcodeInWebWorker === "function") parseGcodeInWebWorker("");
                    if (typeof resetView === "function") resetView();

                    // 4. Reset form and inputs (increased robustness)
                    try {
                        var form = el.find('#gerberForm')[0];
                        if (form) form.reset();
                        ['#folder_input'].forEach(id => {
                            var input = el.find(id);
                            input.val('');
                            var instance = Metro.getPlugin(input[0], 'file');
                            if(instance) instance.clear();
                        });
                    } catch(e) {
                        console.warn("Form reset warning:", e);
                    }
                });
            });

            el.find('#btn_process').on('click', function() {
                var btn = $(this);
                // Find and lock close button in dialog wrapper
                var closeBtn = el.closest('.dialog, .window').find('.js-dialog-close');
                
                btn.prop('disabled', true);
                var originalText = btn.html();
                btn.html('<span class="mif-spinner4 ani-spin"></span> Processing...');
                closeBtn.addClass('disabled').css('pointer-events', 'none');

                var formData = new FormData();
                if(pendingFiles.traces) formData.append("traces", pendingFiles.traces);
                if(pendingFiles.outline) formData.append("outline", pendingFiles.outline);
                if(pendingFiles.drill) formData.append("drill", pendingFiles.drill);
                if(pendingFiles.user_drawings) formData.append("user_drawings", pendingFiles.user_drawings);

                formData.append("offset_x", el.find('#val_offset_x').val());
                formData.append("offset_y", el.find('#val_offset_y').val());

                Metro.toast.create("Processing started. Please wait...", null, 2000, "info");

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
                        currentToolMetadata = data.tool_metadata || {};
                        renderViewButtons();
                        
                        // Update filenames (if newly uploaded)
                        if (data.filenames) {
                        var html = "<b>Geladene Dateien:</b><br>";
                        if(data.filenames.traces) html += `<span class="fg-green mif-checkmark"></span> Traces: ${data.filenames.traces}<br>`;
                        if(data.filenames.outline) html += `<span class="fg-green mif-checkmark"></span> Outline: ${data.filenames.outline}<br>`;
                        if(data.filenames.drill) html += `<span class="fg-green mif-checkmark"></span> Drill: ${data.filenames.drill}<br>`;
                        if(data.filenames.user_drawings) html += `<span class="fg-green mif-checkmark"></span> User Drawings: ${data.filenames.user_drawings}<br>`;
                        el.find('#detected_files').html(html).show();
                        }

                        // Show Traces by default
                        if (data.gcode.traces) {
                            updateEditor(data.gcode.traces);
                            updateDimensionsInfo(currentDimensions.traces);
                        }

                        // Show Image
                        if (data.gcode.traces) updateImage('traces');
                    else if (data.gcode.user_drawings) updateImage('user_drawings');
                        else if (data.gcode.outline) updateImage('outline');
                        else if (data.gcode.drill) updateImage('drill');
                    } else {
                        Metro.toast.create("Error: " + JSON.stringify(data), null, 5000, "alert");
                    }
                })
                .catch(e => {
                    Metro.toast.create("Backend Error: " + e, null, 3000, "alert");
                })
                .finally(() => {
                    // Unlock UI
                    btn.prop('disabled', false);
                    btn.html(originalText);
                    closeBtn.removeClass('disabled').css('pointer-events', 'auto');
                });
            });
        }
    });
})();