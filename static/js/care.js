// "Change" in the weather card opens the thresholds panel it points to
document.querySelectorAll('[data-open-target]').forEach((link) => {
    link.addEventListener('click', () => {
        const panel = document.querySelector(link.getAttribute('href'));
        if (panel && panel.tagName === 'DETAILS') {
            panel.open = true;
            const field = panel.querySelector('input:not([type="hidden"])');
            if (field) {
                field.focus({ preventScroll: true });
            }
        }
    });
});
