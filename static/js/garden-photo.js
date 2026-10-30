// Garden form: one photo, chosen from files, dropped on the box, or added by link
const photoBox = document.querySelector('[data-garden-photo]');

if (photoBox) {
    const fileInput = photoBox.querySelector('input[type="file"]');
    const clearBox = photoBox.querySelector('[data-photo-clear]');
    const preview = photoBox.querySelector('[data-photo-preview]');
    const previewImage = preview.querySelector('img');
    const dropzone = photoBox.querySelector('[data-dropzone]');
    const linkError = photoBox.querySelector('[data-photo-link-error]');
    const linkField = document.querySelector('[data-photo-link]');
    const linkInput = linkField.querySelector('input');

    // While there's a photo, the ways of adding one are hidden, because a garden has only one
    function showPhoto(src) {
        previewImage.src = src;
        preview.hidden = false;
        dropzone.hidden = true;
        linkField.hidden = true;
        linkError.hidden = true;
    }

    function hidePhoto() {
        previewImage.removeAttribute('src');
        preview.hidden = true;
        dropzone.hidden = false;
        linkField.hidden = false;
    }

    // Edit page with a saved photo: start with only the preview showing
    if (!preview.hidden) {
        showPhoto(previewImage.src);
    }

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (!file) {
            return;
        }
        // The new file replaces a saved photo or link
        if (clearBox) {
            clearBox.checked = false;
        }
        linkInput.value = '';
        showPhoto(URL.createObjectURL(file));
    });

    linkInput.addEventListener('change', () => {
        const link = linkInput.value.trim();
        if (link) {
            showPhoto(link);
        }
    });

    // A link that isn't an image: bring the box and the link field back, with a message
    previewImage.addEventListener('error', () => {
        if (linkInput.value) {
            hidePhoto();
            linkError.hidden = false;
        }
    });

    photoBox.querySelector('[data-photo-remove]').addEventListener('click', () => {
        fileInput.value = '';
        linkInput.value = '';
        // Ticks Django's "clear" box, so saving removes the photo that was saved before
        if (clearBox) {
            clearBox.checked = true;
        }
        hidePhoto();
    });

    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropzone.classList.add('is-dragging');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('is-dragging');
    });

    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragging');
        const file = event.dataTransfer.files[0];
        if (!file) {
            return;
        }
        // Put only the first dropped file into the input, then treat it like a chosen file
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        fileInput.dispatchEvent(new Event('change'));
    });
}
