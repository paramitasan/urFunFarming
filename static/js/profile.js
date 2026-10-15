// Profile page: bio counter and saving both forms with fetch (uses getCookie and showErrors from auth.js)

const bio = document.getElementById('id_bio');
const bioCounter = document.getElementById('bio-counter');

if (bio) {
    bio.addEventListener('input', () => {
        bioCounter.textContent = `${bio.value.length} / 300`;
    });
}

function scrollToAlerts() {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.querySelector('.profile-heading').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
}

function showSaved(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-success';
    alert.setAttribute('role', 'status');
    alert.textContent = message;
    document.querySelector('.auth-alerts').append(alert);
}

function roleChip(text, isAdd) {
    const chip = document.createElement(isAdd ? 'a' : 'span');
    chip.className = isAdd ? 'role-chip role-chip-add' : 'role-chip';
    chip.textContent = text;
    if (isAdd) chip.href = '#roles';
    return chip;
}

// Keep the summary card and navbar in step with what was saved
function updateSummary(profile) {
    document.querySelector('[data-summary="display_name"]').textContent = profile.display_name;
    document.querySelector('[data-summary="initials"]').textContent = profile.initials;
    document.querySelector('[data-summary="place"]').textContent = [profile.area, profile.city].filter(Boolean).join(', ');

    const roles = document.querySelector('[data-summary="roles"]');
    roles.replaceChildren();
    if (profile.is_grower) roles.append(roleChip('Grower', false));
    if (profile.is_buyer) roles.append(roleChip('Buyer', false));
    if (!profile.is_grower) roles.append(roleChip('+ Add grower', true));
    if (!profile.is_buyer) roles.append(roleChip('+ Add buyer', true));

    const navName = document.querySelector('.profile-name');
    const navAvatar = document.querySelector('.profile-button .avatar');
    if (navName) navName.textContent = profile.display_name;
    if (navAvatar) navAvatar.textContent = profile.initials;
}

document.querySelectorAll('[data-profile-form]').forEach((form) => {
    form.addEventListener('submit', async (e) => {
        // Second pass after a network error: let the browser submit normally
        if (form.dataset.noFetch) return;
        e.preventDefault();

        const button = e.submitter;
        const body = new FormData(form);
        body.append(button.name, button.value);
        button.disabled = true;

        let data;
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'fetch' },
                body,
                credentials: 'same-origin',
            });
            data = await response.json();
        } catch (error) {
            button.disabled = false;
            form.dataset.noFetch = '1';
            form.requestSubmit(button);
            return;
        }

        button.disabled = false;
        showErrors(form, data.status === 'success' ? {} : data.errors);

        if (data.status === 'success') {
            showSaved(data.message);
            if (data.profile) updateSummary(data.profile);
            if (button.name === 'change_password') form.reset();
            scrollToAlerts();
        } else if (!form.querySelector('.has-error')) {
            scrollToAlerts();
        }
    });
});
