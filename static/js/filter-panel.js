// Shared filter panel fold for phones and tablets (Gardens, Marketplace, Forum).
// Adds a "Show filters" button to every .filter-panel heading; the CSS in style.css hides the
// panel's groups on small screens until the button opens them. Desktop always shows them.
(() => {
    'use strict';
    document.documentElement.classList.add('js');

    document.querySelectorAll('.filter-panel').forEach((panel, index) => {
        const heading = panel.querySelector('.filter-panel-heading');
        if (!heading) return;
        if (!panel.id) panel.id = `filter-panel-${index + 1}`;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'filter-panel-toggle';
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-controls', panel.id);
        button.textContent = 'Show filters';
        heading.insertBefore(button, heading.querySelector('a'));

        button.addEventListener('click', () => {
            const open = panel.classList.toggle('is-open');
            button.setAttribute('aria-expanded', String(open));
            button.textContent = open ? 'Hide filters' : 'Show filters';
        });
    });
})();
