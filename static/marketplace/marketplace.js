/* Progressive enhancement: every operation also has a normal Django form or link. */
(() => {
    'use strict';
    document.documentElement.classList.add('market-js');
    const filterForm = document.getElementById('marketplace-filters');
    let catalogController;
    // Safari before 16 has no requestSubmit(), so send the same submit event by hand
    const submitForm = (form) => {
        if (form.requestSubmit) form.requestSubmit();
        else if (form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))) form.submit();
    };

    function restorePhotos(root = document) {
        root.querySelectorAll('.harvest-user-photo').forEach((photo) => {
            const fallback = () => {
                photo.hidden = true;
                const icon = photo.parentElement.querySelector('.harvest-photo-fallback');
                if (icon) icon.hidden = false;
            };
            photo.addEventListener('error', fallback, { once: true });
            if (photo.complete && photo.naturalWidth === 0) fallback();
        });
    }
    restorePhotos();

    async function loadCatalog(url) {
        if (catalogController) catalogController.abort();
        const controller = new AbortController();
        catalogController = controller;
        const results = document.getElementById('market-results');
        const feedback = document.getElementById('market-filter-feedback');
        results.setAttribute('aria-busy', 'true');
        feedback.hidden = true;
        try {
            const response = await fetch(url, { headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin', signal: controller.signal });
            if (response.status === 401) {
                const data = await response.json();
                if (data.redirect) window.location.assign(data.redirect);
                return;
            }
            if (!response.ok) throw new Error('Unable to update harvests. Please try again.');
            const body = await response.text();
            if (controller.signal.aborted) return;
            results.innerHTML = body;
            restorePhotos(results);
            window.history.pushState({}, '', url);
        } catch (error) {
            if (error.name !== 'AbortError') {
                feedback.textContent = 'Unable to update harvests. Please try again.';
                feedback.hidden = false;
            }
        } finally {
            if (catalogController === controller) results.setAttribute('aria-busy', 'false');
        }
    }

    if (filterForm) {
        const toggle = document.getElementById('market-filter-toggle');
        toggle.addEventListener('click', () => {
            const open = filterForm.querySelector('.market-filters').classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', String(open));
            toggle.textContent = open ? 'Hide filters' : 'Show filters';
        });
        filterForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const params = new URLSearchParams(new FormData(filterForm));
            for (const [key, value] of [...params.entries()]) if (value === '') params.delete(key);
            loadCatalog(`${filterForm.action}?${params.toString()}`);
        });
        filterForm.addEventListener('change', (event) => {
            if (event.target.matches('select, input[type=radio], input[type=number]')) submitForm(filterForm);
        });
        // Typing in the search box: the shared static/js/list-search.js submits after 500 ms
        filterForm.addEventListener('click', (event) => {
            const link = event.target.closest('[data-market-page]');
            if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            loadCatalog(link.href);
        });
        window.addEventListener('popstate', () => window.location.reload());
    }

    document.addEventListener('submit', async (event) => {
        const form = event.target;
        if (form.matches('[data-weather-form]')) {
            event.preventDefault();
            const button = form.querySelector('button[type=submit]');
            button.disabled = true;
            const target = document.getElementById('pickup-weather-results');
            try {
                const url = new URL(form.action);
                url.search = new URLSearchParams(new FormData(form)).toString();
                const response = await fetch(url, { headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' });
                if (![200, 400, 503].includes(response.status)) throw new Error('Request failed');
                target.innerHTML = await response.text();
            } catch (error) {
                let message = target.querySelector('[data-weather-network-error]');
                if (!message) {
                    message = document.createElement('p');
                    message.dataset.weatherNetworkError = '';
                    message.className = 'market-error';
                    message.setAttribute('role', 'alert');
                    target.appendChild(message);
                }
                message.textContent = 'Weather is unavailable right now. Please try again.';
            } finally {
                button.disabled = false;
            }
            return;
        }
        if (!form.matches('[data-market-write]')) return;
        event.preventDefault();
        const summary = form.querySelector('[data-form-errors]');
        summary.replaceChildren();
        summary.hidden = true;
        form.querySelectorAll('.market-field-error').forEach((node) => { node.textContent = ''; });
        form.querySelectorAll('[aria-invalid]').forEach((node) => node.removeAttribute('aria-invalid'));
        const button = form.querySelector('button[type=submit]');
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = 'Saving…';
        try {
            const response = await fetch(form.action || window.location.href, {
                method: 'POST', body: new FormData(form), credentials: 'same-origin',
                headers: { 'X-Requested-With': 'fetch', Accept: 'application/json', 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value },
            });
            if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Your session may have expired. Reload this page and try again.');
            const data = await response.json();
            if (data.redirect && (response.ok || response.status === 401)) {
                window.location.assign(data.redirect);
                return;
            }
            if (!response.ok) {
                summary.textContent = data.message || 'Please check the highlighted fields.';
                summary.hidden = false;
                for (const [field, errors] of Object.entries(data.errors || {})) {
                    const errorTarget = document.getElementById(`id_${field}_error`);
                    const input = form.elements.namedItem(field);
                    if (errorTarget) {
                        errorTarget.textContent = errors.join(' ');
                        if (input) input.setAttribute('aria-invalid', 'true');
                    } else {
                        const p = document.createElement('p');
                        p.textContent = errors.join(' ');
                        summary.appendChild(p);
                    }
                }
                summary.focus();
            }
        } catch (error) {
            summary.textContent = error.message || 'Unable to save your harvest. Please try again.';
            summary.hidden = false;
            summary.focus();
        } finally {
            button.disabled = false;
            button.textContent = originalLabel;
        }
    });
})();
