// Journal list: the filters, search and page buttons load new results with fetch instead of reloading the page.
// The form is still a normal GET form, so everything also works when JavaScript is off.

const SEARCH_DEBOUNCE_DELAY = 300;
let searchDebounceTimer;
let resultsAbortController;

// The list address for the current form values, like /journal/?stage=fruiting&sort=recent
function filterUrl(form) {
    const params = new URLSearchParams(new FormData(form));
    return `${window.location.pathname}?${params}`;
}

// A dropdown other than "All" gets the green tint, the same rule the template uses
function markActiveFilters(form) {
    form.querySelectorAll('select').forEach((select) => {
        select.parentElement.classList.toggle('is-active', select.name !== 'sort' && select.value !== '');
    });
}

async function loadResults(url) {
    // Cancel a request that hasn't finished yet, so old results never replace newer ones
    if (resultsAbortController) {
        resultsAbortController.abort();
    }
    resultsAbortController = new AbortController();

    try {
        const response = await fetch(url, { signal: resultsAbortController.signal });
        if (!response.ok) {
            throw new Error('Failed to load the list');
        }
        const page = new DOMParser().parseFromString(await response.text(), 'text/html');
        // Swap only the table, page buttons and count, so the search box keeps its focus while typing
        document.querySelector('[data-journal-results]').replaceWith(page.querySelector('[data-journal-results]'));
        document.querySelector('[data-count-badge]').textContent = page.querySelector('[data-count-badge]').textContent;
        // Keep the address bar in step, so refreshing or sharing the page shows the same results
        history.replaceState(null, '', url);
    } catch (error) {
        if (error.name === 'AbortError') {
            return;
        }
        // If fetch fails, open the page the normal way instead
        window.location.href = url;
    }
}

document.addEventListener('change', (event) => {
    const form = event.target.closest('[data-filter-form]');
    if (form && event.target.matches('select')) {
        markActiveFilters(form);
        loadResults(filterUrl(form));
    }
});

// Search once the grower stops typing for a moment, like the tutorial's debounce
document.addEventListener('input', (event) => {
    const form = event.target.closest('[data-filter-form]');
    if (form && event.target.name === 'q') {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => loadResults(filterUrl(form)), SEARCH_DEBOUNCE_DELAY);
    }
});

// Enter in the search box searches straight away
document.addEventListener('submit', (event) => {
    const form = event.target.closest('[data-filter-form]');
    if (form) {
        event.preventDefault();
        clearTimeout(searchDebounceTimer);
        loadResults(filterUrl(form));
    }
});

document.addEventListener('click', (event) => {
    const pageLink = event.target.closest('.pagination a');
    if (pageLink) {
        event.preventDefault();
        loadResults(pageLink.href);
        return;
    }

    const resetLink = event.target.closest('[data-filter-reset]');
    const form = document.querySelector('[data-filter-form]');
    if (resetLink && form) {
        event.preventDefault();
        // Every dropdown back to its first option ("All ..." or "Recently updated") and an empty search
        form.querySelectorAll('select').forEach((select) => {
            select.selectedIndex = 0;
        });
        form.querySelector('[name="q"]').value = '';
        markActiveFilters(form);
        loadResults(resetLink.href);
    }
});


// The lock next to the time switches a plant's journal between private and public
async function toggleVisibility(button) {
    const plantName = button.dataset.plantName;
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
        button.setAttribute('aria-label', `Make ${plantName} ${result.is_public ? 'private' : 'public'}`);
        showToast('info', result.message, result.detail);

    } catch (error) {
        showToast(
            'error',
            `Couldn't make ${plantName} ${wasPublic ? 'private' : 'public'}`,
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
