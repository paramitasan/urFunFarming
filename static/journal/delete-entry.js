// Deleting an entry: a trash button opens the dialog, and "Delete entry" sends the delete with fetch
const deleteDialog = document.querySelector('[data-delete-dialog]');

if (deleteDialog) {
    const confirmButton = deleteDialog.querySelector('[data-delete-confirm]');
    let deleteUrl = null;

    // Listen on the whole page, so trash buttons in a refreshed timeline still work
    document.addEventListener('click', (event) => {
        const trashButton = event.target.closest('[data-delete-url]');
        if (trashButton) {
            deleteUrl = trashButton.dataset.deleteUrl;
            deleteDialog.showPopover();
        }
    });

    // Ask the server for this page again and swap in the new header and timeline,
    // so the height changes, entry count and growth stage stay right
    async function refreshTimeline() {
        const response = await fetch(window.location.href);
        const page = new DOMParser().parseFromString(await response.text(), 'text/html');
        ['[data-journal-header]', '[data-journal-body]'].forEach((selector) => {
            document.querySelector(selector).replaceWith(page.querySelector(selector));
        });
    }

    async function deleteEntry(url) {
        confirmButton.disabled = true;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            const result = await response.json().catch(() => ({}));
            deleteDialog.hidePopover();

            if (response.ok && document.querySelector('[data-journal-body]')) {
                // On the plant page: show the toast and refresh the timeline here
                showToast('success', result.message);
                // If the refresh fails, reloading the page shows the same thing
                refreshTimeline().catch(() => window.location.reload());
            } else if (response.ok) {
                // On the Edit page the entry is gone, so go back to its plant and show the toast there
                sessionStorage.setItem('journalToast', result.message);
                window.location.href = result.plant_url;
            } else {
                showToast('error', "Couldn't delete this entry", result.message || 'Something went wrong. Try again.');
            }
        } catch (error) {
            // The server couldn't be reached, so offer to try again
            deleteDialog.hidePopover();
            showToast('error', "Couldn't delete this entry", 'Something went wrong. Try again.', {
                label: 'Retry',
                onClick: () => deleteEntry(url),
            });
        } finally {
            confirmButton.disabled = false;
        }
    }

    confirmButton.addEventListener('click', () => deleteEntry(deleteUrl));
}
