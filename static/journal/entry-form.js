// Photos on the entry form: uploads and links together, up to a set number
const photoBox = document.querySelector('[data-photo-box]');

// Scrolling the page over the height box shouldn't change the number, so the box lets go of focus
const heightInput = document.querySelector('input[name="height_cm"]');
if (heightInput) {
    heightInput.addEventListener('wheel', () => heightInput.blur());
}

if (photoBox) {
    const maxPhotos = Number(photoBox.dataset.maxPhotos);
    const trashIcon = photoBox.dataset.trashIcon;
    const list = photoBox.querySelector('[data-photo-list]');
    // The big dropzone shows until the first photo, then the photos sit in a row with the "Add photo" tile
    const dropzone = photoBox.querySelector('[data-dropzone]');
    const addTile = photoBox.querySelector('[data-add-tile]');
    const photoHint = photoBox.querySelector('[data-photo-hint]');
    const fileInput = photoBox.querySelector('input[type="file"]');
    const keptBoxes = Array.from(photoBox.querySelectorAll('input[name="remove_photos"]'));
    const uploadError = photoBox.querySelector('[data-upload-error]');
    const limitWarning = photoBox.querySelector('[data-photo-limit]');
    const fullNote = photoBox.querySelector('[data-photo-full]');
    const linkBox = photoBox.querySelector('[data-link-box]');
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

    // Saved photos on the edit page that aren't ticked for removal
    function keptCount() {
        return keptBoxes.filter((box) => !box.checked).length;
    }

    function photoCount() {
        return keptCount() + chosenFiles.length + linkCount();
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
        remove.addEventListener('click', () => {
            limitWarning.hidden = true;
            onRemove();
        });

        slot.append(img, remove);
        return slot;
    }

    function showPhotos() {
        // Take away the new photos shown last time (saved photos stay), freeing their preview addresses
        list.querySelectorAll('[data-new-photo]').forEach((slot) => {
            const preview = slot.querySelector('img[data-preview]');
            if (preview) {
                URL.revokeObjectURL(preview.src);
            }
            slot.remove();
        });
        let number = keptCount();

        chosenFiles.forEach((file, i) => {
            number += 1;
            const slot = makeSlot(URL.createObjectURL(file), `Photo ${number}`, () => {
                chosenFiles.splice(i, 1);
                syncFileInput();
                showPhotos();
            });
            slot.querySelector('img').dataset.preview = '';
            slot.dataset.newPhoto = '';
            // Always before the "Add photo" tile, so the tile stays last in the row
            list.insertBefore(slot, addTile);
        });

        linkFields.forEach((field) => {
            if (!field.value) {
                return;
            }
            number += 1;
            const slot = makeSlot(field.value, `Photo ${number}`, () => {
                field.value = '';
                packLinks();
                showPhotos();
            });
            slot.dataset.newPhoto = '';
            list.insertBefore(slot, addTile);
        });

        const count = photoCount();
        const full = count >= maxPhotos;
        // Only a page without saved photos has the dropzone, and only while nothing is chosen yet
        const showDropzone = Boolean(dropzone) && count === 0;
        // At 5 photos the ways of adding more are hidden
        fullNote.hidden = !full;
        linkBox.hidden = full;
        if (dropzone) {
            dropzone.hidden = !showDropzone;
        }
        addTile.hidden = full || showDropzone;
        photoHint.hidden = addTile.hidden;
    }

    function addFiles(files) {
        let rejected = false;
        let skipped = 0;
        Array.from(files).forEach((file) => {
            if (photoCount() >= maxPhotos) {
                skipped += 1;
                return;
            }
            if (!allowedTypes.includes(file.type) || file.size > maxSize) {
                rejected = true;
                return;
            }
            chosenFiles.push(file);
        });
        uploadError.hidden = !rejected;
        // Say how many photos didn't fit, instead of leaving them out without a word
        limitWarning.hidden = skipped === 0;
        limitWarning.querySelector('[data-photo-limit-text]').textContent =
            `One entry can have up to ${maxPhotos} photos, so ${skipped} ${skipped === 1 ? "wasn't" : "weren't"} added.`;
        syncFileInput();
        showPhotos();
    }

    fileInput.addEventListener('change', () => {
        // The picker only gives the new selection, so add it to what was already chosen
        const newFiles = Array.from(fileInput.files).filter((file) => !chosenFiles.includes(file));
        syncFileInput();
        addFiles(newFiles);
    });

    // Photos can be dropped on the big dropzone and on the "Add photo" tile
    [dropzone, addTile].filter(Boolean).forEach((zone) => {
        zone.addEventListener('dragover', (event) => {
            event.preventDefault();
            zone.classList.add('is-dragging');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('is-dragging');
        });

        zone.addEventListener('drop', (event) => {
            event.preventDefault();
            zone.classList.remove('is-dragging');
            addFiles(event.dataTransfer.files);
        });
    });

    // Edit page: the trash button on a saved photo ticks its hidden remove box, and CSS hides the photo
    photoBox.querySelectorAll('[data-remove-kept]').forEach((button) => {
        button.addEventListener('click', () => {
            button.closest('.photo-slot').querySelector('input[name="remove_photos"]').checked = true;
            limitWarning.hidden = true;
            showPhotos();
        });
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
