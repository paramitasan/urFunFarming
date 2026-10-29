// Description box: live "0 / 5000" counter.
document.querySelectorAll("[data-char-counter]").forEach((box) => {
    const textarea = box.querySelector("textarea");
    const counter = box.querySelector(".ff-counter");
    if (!textarea || !counter) return;

    const update = () => {
        counter.textContent = `${textarea.value.length} / ${textarea.maxLength}`;
    };
    textarea.addEventListener("input", update);
    update();
});

// Image picker: shows a thumbnail, the file name and a remove button once a file is chosen.
document.querySelectorAll("[data-upload]").forEach((upload) => {
    const input = upload.querySelector("input[type=file]");
    const dropzone = upload.querySelector(".ff-dropzone");
    const row = upload.querySelector(".ff-file");
    const thumb = upload.querySelector(".ff-file-thumb");
    const name = upload.querySelector(".ff-file-name");
    const size = upload.querySelector(".ff-file-size");
    const remove = upload.querySelector(".ff-file-remove");
    const removeFlag = upload.querySelector("input[name=remove_image]");
    if (!input || !dropzone || !row) return;

    let previewUrl = null;

    const formatSize = (bytes) => {
        if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    };

    const clearPreview = () => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
        thumb.removeAttribute("src");
    };

    const reset = () => {
        input.value = "";
        if (removeFlag) removeFlag.value = "1";   // tells the server to delete the saved image
        clearPreview();
        row.hidden = true;
        dropzone.hidden = false;
    };

    input.addEventListener("change", () => {
        const file = input.files[0];
        if (!file) {
            reset();
            return;
        }
        clearPreview();
        previewUrl = URL.createObjectURL(file);
        thumb.src = previewUrl;
        name.textContent = file.name;
        size.textContent = formatSize(file.size);
        dropzone.hidden = true;
        row.hidden = false;
    });

    remove.addEventListener("click", reset);

    ["dragenter", "dragover"].forEach((type) =>
        dropzone.addEventListener(type, () => dropzone.classList.add("is-dragging"))
    );
    ["dragleave", "drop"].forEach((type) =>
        dropzone.addEventListener(type, () => dropzone.classList.remove("is-dragging"))
    );
});