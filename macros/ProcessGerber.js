// Makro für OpenBuilds CONTROL
// Upload von Gerber-Dateien, Verarbeitung via pcb2gcode und Leveling

(function() {
    var content = `
        <div class="p-2">
            <h5>Gerber Verarbeitung & Leveling</h5>
            <hr>
            <form id="gerberForm">
                <div class="mb-2">
                    <label>Front Copper (Gerber)</label>
                    <input type="file" id="file_front" data-role="file" data-mode="drop">
                </div>
                <div class="mb-2">
                    <label>Outline / Edge Cuts</label>
                    <input type="file" id="file_outline" data-role="file" data-mode="drop">
                </div>
                <div class="mb-2">
                    <label>Drill File</label>
                    <input type="file" id="file_drill" data-role="file" data-mode="drop">
                </div>
                <div class="row mb-2">
                    <div class="cell-6">
                        <label>Frästiefe (Z-Work)</label>
                        <input type="number" id="val_zwork" value="-0.1" step="0.05" data-role="input">
                    </div>
                    <div class="cell-6">
                        <label>Vorschub (Feed)</label>
                        <input type="number" id="val_feed" value="200" data-role="input">
                    </div>
                </div>
            </form>
            <div class="mt-4">
                <button class="button success w-100" id="btn_process">
                    <span class="mif-cogs"></span> Verarbeiten & Leveln
                </button>
            </div>
        </div>
    `;

    Metro.dialog.create({
        title: "PCB Bridge - Gerber",
        content: content,
        width: 500,
        actions: [{ caption: "Schließen", cls: "js-dialog-close" }],
        onShow: function(dialog) {
            var el = dialog.element;

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

                Metro.toast.create("Verarbeitung läuft...", null, 2000, "info");

                fetch('http://127.0.0.1:8000/process/pcb', {
                    method: 'POST',
                    body: formData
                })
                .then(r => r.json())
                .then(data => {
                    if(data.status === "success") {
                        Metro.toast.create("Erfolg! Datei gespeichert: " + data.file, null, 5000, "success");
                        dialog.close();
                    } else {
                        Metro.toast.create("Fehler: " + JSON.stringify(data), null, 5000, "alert");
                    }
                })
                .catch(e => {
                    Metro.toast.create("Backend Fehler: " + e, null, 3000, "alert");
                });
            });
        }
    });
})();