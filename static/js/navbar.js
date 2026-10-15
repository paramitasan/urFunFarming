// Navbar: menu button below 1024px and the "Scrolled" state from Figma

const nav = document.querySelector('.navbar');
const menuButton = nav.querySelector('.menu-button');

function setMenu(open) {
    nav.classList.toggle('open', open);
    menuButton.setAttribute('aria-expanded', open);
    menuButton.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
}

menuButton.addEventListener('click', () => setMenu(!nav.classList.contains('open')));

// Close after picking a link, or with Escape
nav.querySelectorAll('.nav-menu a').forEach((link) => link.addEventListener('click', () => setMenu(false)));
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('open')) {
        setMenu(false);
        menuButton.focus();
    }
});

function updateScrolled() {
    nav.classList.toggle('scrolled', window.scrollY > 8);
}
window.addEventListener('scroll', updateScrolled, { passive: true });
updateScrolled();
