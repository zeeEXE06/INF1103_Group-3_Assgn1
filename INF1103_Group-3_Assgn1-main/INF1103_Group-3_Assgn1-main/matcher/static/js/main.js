/*
 * Drag-and-drop file uploads and a loading spinner on the submit button.
 * Forms still submit normally to the Django views.
 */

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-dropzone]").forEach(initDropzone);
    document.querySelectorAll("form[data-submit-btn], form").forEach(initSubmitSpinner);
});

function initDropzone(zone) {
    const input = zone.querySelector("input[type='file']");
    if (!input) return;

    const isMultiple = zone.dataset.multiple === "true";
    const filenameEl = zone.querySelector("[data-filename]");
    const filelistEl = zone.querySelector("[data-filelist]");

    const showFiles = (files) => {
        if (isMultiple && filelistEl) {
            filelistEl.innerHTML = "";
            if (files.length) {
                filelistEl.hidden = false;
                Array.from(files).forEach((file) => {
                    const li = document.createElement("li");
                    li.textContent = file.name;
                    filelistEl.appendChild(li);
                });
            } else {
                filelistEl.hidden = true;
            }
        } else if (filenameEl) {
            if (files.length) {
                filenameEl.hidden = false;
                filenameEl.textContent = `Selected: ${files[0].name}`;
            } else {
                filenameEl.hidden = true;
            }
        }
    };

    input.addEventListener("change", () => showFiles(input.files));

    ["dragenter", "dragover"].forEach((eventName) => {
        zone.addEventListener(eventName, (event) => {
            event.preventDefault();
            zone.classList.add("is-dragover");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        zone.addEventListener(eventName, (event) => {
            event.preventDefault();
            zone.classList.remove("is-dragover");
        });
    });

    zone.addEventListener("drop", (event) => {
        const files = event.dataTransfer.files;
        if (files && files.length) {
            input.files = files;
            showFiles(files);
        }
    });
}

function initSubmitSpinner(form) {
    const btn = form.querySelector("[data-submit-btn]");
    if (!btn) return;

    form.addEventListener("submit", () => {
        if (!form.checkValidity()) return;
        const label = btn.querySelector("[data-btn-label]");
        const spinner = btn.querySelector("[data-btn-spinner]");
        btn.setAttribute("disabled", "disabled");
        if (spinner) spinner.hidden = false;
        if (label) label.textContent = "Processing…";
    });
}
