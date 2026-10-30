// Filters: a mouse or touch change applies at once. Typing in the search box is handled by
// the shared static/js/list-search.js (500 ms debounce). Keyboard users move through the options
// freely (arrow keys also fire "change") and press Apply filters, which shows when it gets focus.

// Safari before 16 has no requestSubmit(), so send the same submit event by hand
function submitForm(form) {
    if (form.requestSubmit) {
        form.requestSubmit();
    } else if (form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))) {
        form.submit();
    }
}

let usingKeyboard = false;
document.addEventListener('keydown', () => { usingKeyboard = true; });
document.addEventListener('pointerdown', () => { usingKeyboard = false; });

document.querySelectorAll('form[data-autosubmit]').forEach((form) => {
    form.classList.add('is-live');
    form.addEventListener('change', (e) => {
        if (!usingKeyboard && e.target.type !== 'search') {
            submitForm(form);
        }
    });
});

// More menu: close it when clicking anywhere else

document.addEventListener('click', (e) => {
    document.querySelectorAll('.garden-more[open]').forEach((menu) => {
        if (!menu.contains(e.target)) {
            menu.removeAttribute('open');
        }
    });
});
