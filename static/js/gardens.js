// Filters: a mouse or touch change applies at once. Keyboard users move through the options
// freely (arrow keys also fire "change") and press Apply filters, which shows when it gets focus.

let usingKeyboard = false;
document.addEventListener('keydown', () => { usingKeyboard = true; });
document.addEventListener('pointerdown', () => { usingKeyboard = false; });

document.querySelectorAll('form[data-autosubmit]').forEach((form) => {
    form.classList.add('is-live');
    form.addEventListener('change', (e) => {
        if (!usingKeyboard && e.target.type !== 'search') {
            form.requestSubmit();
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
