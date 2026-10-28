// Filters: apply as soon as a select or radio changes (the search box submits on Enter)

document.querySelectorAll('form[data-autosubmit]').forEach((form) => {
    form.addEventListener('change', (e) => {
        if (e.target.type !== 'search') {
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
