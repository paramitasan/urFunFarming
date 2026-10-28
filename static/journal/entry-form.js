// Photos on the entry form: uploads and links together, up to a set number
const photoBox = document.querySelector('[data-photo-box]');

if (photoBox) {
    const maxPhotos = Number(photoBox.dataset.maxPhotos);
    const keptPhotos = Number(photoBox.dataset.keptPhotos || 0);
    const trashIcon = photoBox.dataset.trashIcon;
    const list = photoBox.querySelector('[data-photo-list]');
    const dropzone = photoBox.querySelector('[data-dropzone]');
    const fileInput = dropzone.querySelector('input[type="file"]');
    const uploadError = photoBox.querySelector('[data-upload-error]');
    const fullNote = photoBox.querySelector('[data-photo-full]');
    const linkInput = photoBox.querySelector('[data-link-input]');
    const linkButton = photoBox.querySelector('[data-link-add]');
    const linkError = photoBox.querySelector('[data-link-error]');
    const linkFields = [1, 2, 3, 4, 5].map((n) => photoBox.querySelector(`input[name="photo_${n}"]`));

    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    const maxSize = 5 * 1024 * 1024;
    let chosenFiles = [];

    function linkCount() {
        return linkFields.filter((field) => field.value).length;
    }

    function photoCount() {
        return keptPhotos + chosenFiles.length + linkCount();
    }

    // The file input is what gets sent, so keep it in step with chosenFiles
    function syncFileInput() {
        const transfer = new DataTransfer();
        chosenFiles.forEach((file) => transfer.items.add(file));
        fileInput.files = transfer.files;
    }

    // Filled links move to the front, so the free fields are always at the end
    function packLinks() {
        const urls = linkFields.map((field) => field.value).filter(Boolean);
        linkFields.forEach((field, i) => {
            field.value = urls[i] || '';
        });
    }

    function makeSlot(src, label, onRemove) {
        const slot = document.createElement('div');
        slot.className = 'photo-slot';

        const img = document.createElement('img');
        img.src = src;
        img.alt = label;

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'photo-remove';
        remove.setAttribute('aria-label', `Remove ${label.toLowerCase()}`);
        const icon = document.createElement('img');
        icon.src = trashIcon;
        icon.alt = '';
        icon.width = 14;
        icon.height = 14;
        remove.append(icon);
        remove.addEventListener('click', onRemove);

        slot.append(img, remove);
        return slot;
    }

    function showPhotos() {
        // Free the old preview addresses before making new ones
        list.querySelectorAll('img[data-preview]').forEach((img) => URL.revokeObjectURL(img.src));
        list.innerHTML = '';
        let number = keptPhotos;

        chosenFiles.forEach((file, i) => {
            number += 1;
            const slot = makeSlot(URL.createObjectURL(file), `Photo ${number}`, () => {
                chosenFiles.splice(i, 1);
                syncFileInput();
                showPhotos();
            });
            slot.querySelector('img').dataset.preview = '';
            list.append(slot);
        });

        linkFields.forEach((field) => {
            if (!field.value) {
                return;
            }
            number += 1;
            list.append(makeSlot(field.value, `Photo ${number}`, () => {
                field.value = '';
                packLinks();
                showPhotos();
            }));
        });

        const full = photoCount() >= maxPhotos;
        dropzone.classList.toggle('is-full', full);
        linkInput.disabled = full;
        linkButton.disabled = full;
        fullNote.hidden = !full;
    }

    function addFiles(files) {
        let rejected = false;
        Array.from(files).forEach((file) => {
            if (photoCount() >= maxPhotos) {
                return;
            }
            if (!allowedTypes.includes(file.type) || file.size > maxSize) {
                rejected = true;
                return;
            }
            chosenFiles.push(file);
        });
        uploadError.hidden = !rejected;
        syncFileInput();
        showPhotos();
    }

    fileInput.addEventListener('change', () => {
        // The picker only gives the new selection, so add it to what was already chosen
        const newFiles = Array.from(fileInput.files).filter((file) => !chosenFiles.includes(file));
        syncFileInput();
        addFiles(newFiles);
    });

    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        if (!dropzone.classList.contains('is-full')) {
            dropzone.classList.add('is-dragging');
        }
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('is-dragging');
    });

    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragging');
        if (!dropzone.classList.contains('is-full')) {
            addFiles(event.dataTransfer.files);
        }
    });

    function addLink() {
        const url = linkInput.value.trim();
        if (!url || photoCount() >= maxPhotos) {
            return;
        }
        // Load the image off-screen first, so broken links never reach the form
        const test = new Image();
        test.onload = () => {
            linkFields.find((field) => !field.value).value = url;
            linkInput.value = '';
            linkError.hidden = true;
            linkInput.setAttribute('aria-invalid', 'false');
            showPhotos();
        };
        test.onerror = () => {
            linkError.hidden = false;
            linkInput.setAttribute('aria-invalid', 'true');
        };
        test.src = url;
    }

    linkButton.addEventListener('click', addLink);

    // Enter in the link box adds the link instead of sending the whole form
    linkInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            addLink();
        }
    });

    // Links kept after a failed save are shown again
    showPhotos();
}
