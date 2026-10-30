// Flips the timeline between newest first and oldest first without reloading the page.
// Without JavaScript the link still works, it just loads the page normally.
document.addEventListener('click', async (event) => {
    const toggle = event.target.closest('[data-order-toggle]');
    if (!toggle) {
        return;
    }
    event.preventDefault();

    try {
        const response = await fetch(toggle.href);
        if (!response.ok) {
            throw new Error('Failed to load the timeline');
        }
        const page = new DOMParser().parseFromString(await response.text(), 'text/html');
        // Swap only the timeline, the sidebar stays the same in both orders
        document.querySelector('#timeline').replaceWith(page.querySelector('#timeline'));
        // Keep the address bar in step, so refreshing keeps the chosen order
        history.replaceState(null, '', toggle.href);
    } catch (error) {
        // If the fetch fails, fall back to a normal page load
        window.location.href = toggle.href;
    }
});
