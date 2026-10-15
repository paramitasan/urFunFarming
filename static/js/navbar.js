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

// Profile dropdown when signed in
const profileButton = nav.querySelector('.profile-button');
const profileDropdown = document.getElementById('profile-dropdown');

function setProfile(open) {
    profileDropdown.hidden = !open;
    profileButton.setAttribute('aria-expanded', open);
}

if (profileButton) {
    profileButton.addEventListener('click', () => setProfile(profileDropdown.hidden));
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.profile-menu')) setProfile(false);
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !profileDropdown.hidden) {
            setProfile(false);
            profileButton.focus();
        }
    });
}

// Log out with fetch, then go to the log in page
const logoutForm = document.querySelector('.logout-form');

if (logoutForm) {
    logoutForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const token = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='));
        try {
            await fetch(logoutForm.action, {
                method: 'POST',
                headers: { 'X-CSRFToken': token ? decodeURIComponent(token.split('=')[1]) : '' },
                credentials: 'same-origin',
            });
            window.location.href = logoutForm.dataset.redirect;
        } catch (error) {
            logoutForm.submit();
        }
    });
}
