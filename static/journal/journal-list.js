// Journal list: picking a dropdown option sends the filter form straight away.
// Listening on the whole page means it still works after the list is refreshed by a delete
document.addEventListener('change', (event) => {
    if (event.target.matches('[data-filter-form] select')) {
        event.target.form.submit();
    }
});

// The lock next to the time switches a plant's journal between private and public
async function toggleVisibility(button) {
    const crop = button.dataset.crop;
    const wasPublic = button.dataset.public === 'true';
    button.disabled = true;
    try {
        const response = await fetch(button.dataset.visibilityUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(result.message);
        }

        button.dataset.public = result.is_public;
        button.setAttribute('aria-label', `Make ${crop} ${result.is_public ? 'private' : 'public'}`);
        // Undo just switches it back
        showToast('info', result.message, result.detail, { label: 'Undo', onClick: () => toggleVisibility(button) });
    } catch (error) {
        showToast(
            'error',
            `Couldn't make ${crop} ${wasPublic ? 'private' : 'public'}`,
            `Its journal is still ${wasPublic ? 'public' : 'private'}. Try again.`,
            { label: 'Retry', onClick: () => toggleVisibility(button) },
        );
    } finally {
        button.disabled = false;
    }
}

document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-visibility-url]');
    if (button) {
        toggleVisibility(button);
    }
});
