// Shared search debounce for every list page (Gardens, Marketplace, Forum).
// A search box inside .list-search submits its form 500 ms after the user stops typing.
// Pages that reload keep the cursor in the box afterwards; the marketplace catches the
// submit event itself and fetches the results instead of reloading.
(() => {
    'use strict';
    const DELAY = 500;
    const FOCUS_KEY = 'list-search-focus:' + window.location.pathname;

    // Safari before 16 has no requestSubmit(), so send the same submit event by hand
    const submitForm = (form) => {
        if (form.requestSubmit) form.requestSubmit();
        else if (form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))) form.submit();
    };

    document.querySelectorAll('.list-search input[type="search"]').forEach((input) => {
        const form = input.form;
        if (!form) return;
        let lastSent = input.value.trim();
        let timer;

        // Back in the box after the page reloaded, with the cursor at the end
        if (sessionStorage.getItem(FOCUS_KEY)) {
            sessionStorage.removeItem(FOCUS_KEY);
            input.focus({ preventScroll: true });
            input.setSelectionRange(input.value.length, input.value.length);
        }

        input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                const value = input.value.trim();
                if (value === lastSent) return;
                lastSent = value;
                sessionStorage.setItem(FOCUS_KEY, '1');
                submitForm(form);
            }, DELAY);
        });

        // Enter searches at once; the pending timer must not send it twice
        form.addEventListener('submit', () => {
            clearTimeout(timer);
            lastSent = input.value.trim();
        });
    });
})();
