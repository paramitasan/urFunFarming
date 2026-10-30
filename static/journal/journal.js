// Shared by the journal pages: toasts, and the CSRF token for fetch

const toastArea = document.querySelector('[data-toast-area]');

// Load the toast icons now, so a toast shown later still has them, even if the server can't be reached by then
document.querySelectorAll('[data-toast-template]').forEach((template) => {
    template.content.querySelectorAll('img').forEach((icon) => {
        new Image().src = icon.getAttribute('src');
    });
});

// Plays the slide down, then takes the toast off the page once it has finished
function hideToast(toast) {
    toast.classList.add('is-leaving');
    toast.addEventListener('animationend', () => toast.remove());
}

function setUpToast(toast) {
    toast.querySelector('[data-toast-close]').addEventListener('click', () => hideToast(toast));
    // Success and info toasts go away by themselves, error toasts stay until closed
    if (toast.dataset.type !== 'error') {
        setTimeout(() => hideToast(toast), 4000);
    }
}

// type is 'success', 'error' or 'info'. action is optional, like { label: 'Retry', onClick: tryAgain }
function showToast(type, message, detail = '', action = null) {
    const template = document.querySelector(`[data-toast-template="${type}"]`);
    const toast = template.content.firstElementChild.cloneNode(true);
    toast.querySelector('[data-toast-message]').textContent = message;

    const detailText = toast.querySelector('[data-toast-detail]');
    detailText.textContent = detail;
    detailText.hidden = !detail;

    if (action) {
        const actionButton = toast.querySelector('[data-toast-action]');
        actionButton.textContent = action.label;
        actionButton.hidden = false;
        actionButton.addEventListener('click', () => {
            hideToast(toast);
            action.onClick();
        });
    }

    // Only one toast at a time: the new one takes the place of any toast still showing
    toastArea.replaceChildren(toast);
    setUpToast(toast);
}

// Toasts Django already put on the page from messages
toastArea.querySelectorAll('.toast').forEach(setUpToast);

// Same as the tutorial: read the csrftoken cookie, to send it in the X-CSRFToken header
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// A toast saved just before moving to this page, like "Entry deleted" after deleting on the Edit page
const savedToast = sessionStorage.getItem('journalToast');
if (savedToast) {
    sessionStorage.removeItem('journalToast');
    showToast('success', savedToast);
}
