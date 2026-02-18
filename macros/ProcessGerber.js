// Macro for OpenBuilds CONTROL
// Upload of Gerber files, processing via pcb2gcode, and leveling

(function() {
    var content = `
        <div class="p-2">
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

            <div class="d-flex flex-row w-100 mb-2" id="view_buttons" style="display:none; gap: 5px;"></div>

            <div class="mt-2">
                <button class="button success w-100" id="btn_process">
                    <span class="mif-cogs"></span> Process & Level
                </button>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge - Gerber Processing",
        content: content,
        width: 500,
        actions: [{ caption: "Close", cls: "js-dialog-close" }],
        onShow: function(dialog) {
            var el = dialog.element;
            // Storage for loaded G-codes
            var currentGcodeData = { front: null, outline: null, drill: null };
            var currentDimensions = { front: null, outline: null, drill: null };

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

            function renderViewButtons() {
                var container = el.find('#view_buttons');
                container.html('');
                container.show();

                var map = {
                    'front': { label: 'Front (Traces)', icon: 'mif-flow-line', cls: 'primary' },
                    'outline': { label: 'Outline (Cut)', icon: 'mif-cut', cls: 'alert' },
                    'drill': { label: 'Drill (Holes)', icon: 'mif-more-vert', cls: 'warning' }
                };

                Object.keys(currentGcodeData).forEach(key => {
                    if (currentGcodeData[key]) {
                        var btn = $(`<button class="button small ${map[key].cls} flex-fill"><span class="${map[key].icon}"></span> ${map[key].label}</button>`);
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
                        
                        // Automatically load Front if available
                        if (currentGcodeData.front) {
                            updateEditor(currentGcodeData.front);
                            updateDimensionsInfo(currentDimensions.front);
                            Metro.toast.create("Latest processing loaded.", null, 2000, "success");
                        }
                        
                        // Restore form values (optional)
                        if (data.config) {
                            if(data.config.offset_x) el.find('#val_offset_x').val(data.config.offset_x);
                            if(data.config.offset_y) el.find('#val_offset_y').val(data.config.offset_y);
                        }

                        // Display filenames
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
                    el.find('#lbl_front').text("");
                    el.find('#lbl_outline').text("");
                    el.find('#lbl_drill').text("");
                    
                    // 2. Clear internal data
                    currentGcodeData = { front: null, outline: null, drill: null };
                    currentDimensions = { front: null, outline: null, drill: null };
                    
                    // 3. Clear editor
                    if (typeof editor !== 'undefined' && editor.session) editor.session.setValue("");
                    if (typeof parseGcodeInWebWorker === "function") parseGcodeInWebWorker("");
                    if (typeof resetView === "function") resetView();

                    // 4. Reset form and inputs (increased robustness)
                    try {
                        el.find('#gerberForm')[0].reset();
                        ['#file_front', '#file_outline', '#file_drill'].forEach(id => {
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
                
                var fFront = el.find('#file_front')[0].files[0];
                var fOutline = el.find('#file_outline')[0].files[0];
                var fDrill = el.find('#file_drill')[0].files[0];

                if(fFront) formData.append("front", fFront);
                if(fOutline) formData.append("outline", fOutline);
                if(fDrill) formData.append("drill", fDrill);

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
                        renderViewButtons();
                        
                        // Update filenames (if newly uploaded)
                        if (data.filenames) {
                            if(data.filenames.front) el.find('#lbl_front').text("(" + data.filenames.front + ")");
                            if(data.filenames.outline) el.find('#lbl_outline').text("(" + data.filenames.outline + ")");
                            if(data.filenames.drill) el.find('#lbl_drill').text("(" + data.filenames.drill + ")");
                        }

                        // Show Front by default
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