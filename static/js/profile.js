// Needs getCookie and showErrors from auth.js

const bio = document.getElementById('id_bio');
const bioCounter = document.getElementById('bio-counter');

if (bio) {
    bio.addEventListener('input', () => {
        bioCounter.textContent = `${bio.value.length} / 300`;
    });
}

// Location: turn the grouped village list into City, District and Village dropdowns.
// Each village group is labelled "District, City" by the server (accounts/locations.py).
const villageSelect = document.querySelector('[data-location-field] select[name="location"]');

if (villageSelect) {
    const citySelect = document.querySelector('[data-location-city]');
    const districtSelect = document.querySelector('[data-location-district]');
    const groups = Array.from(villageSelect.querySelectorAll('optgroup')).map((group) => {
        const cut = group.label.lastIndexOf(', ');
        return {
            district: group.label.slice(0, cut),
            city: group.label.slice(cut + 2),
            options: Array.from(group.children).map((option) => [option.value, option.textContent]),
        };
    });
    const cities = [...new Set(groups.map((g) => g.city))];
    const chosen = villageSelect.value;
    const start = groups.find((g) => g.options.some(([code]) => code === chosen));

    function fill(select, placeholder, items, selected) {
        select.replaceChildren(new Option(placeholder, ''));
        items.forEach(([value, text]) => select.add(new Option(text, value, false, value === selected)));
        select.disabled = items.length === 0;
    }

    function showDistricts(city, selected) {
        const districts = groups.filter((g) => g.city === city).map((g) => [g.district, g.district]);
        fill(districtSelect, 'Choose a district', districts, selected);
    }

    function showVillages(city, district, selected) {
        const group = groups.find((g) => g.city === city && g.district === district);
        fill(villageSelect, 'Choose a village', group ? group.options : [], selected);
    }

    fill(citySelect, 'Choose a city', cities.map((c) => [c, c]), start ? start.city : '');
    showDistricts(start ? start.city : '', start ? start.district : '');
    showVillages(start ? start.city : '', start ? start.district : '', chosen);
    document.querySelectorAll('[data-location-step]').forEach((step) => { step.hidden = false; });

    citySelect.addEventListener('change', () => {
        showDistricts(citySelect.value, '');
        showVillages('', '', '');
    });
    districtSelect.addEventListener('change', () => {
        showVillages(citySelect.value, districtSelect.value, '');
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

        // Safari before 15.4 has no e.submitter; each profile form has one submit button
        const button = e.submitter || form.querySelector('button[type=submit]');
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
            // click() resubmits with this button in every browser, unlike requestSubmit()
            button.click();
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
