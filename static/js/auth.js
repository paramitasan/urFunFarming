// Show/Hide buttons on password fields
document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    const input = document.getElementById(button.dataset.togglePassword);

    button.addEventListener('click', () => {
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        button.textContent = show ? 'Hide' : 'Show';
        button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
});

function getCookie(name) {
    const row = document.cookie.split('; ').find((item) => item.startsWith(name + '='));
    return row ? decodeURIComponent(row.split('=')[1]) : '';
}

function addAlert(alerts, message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-error';
    alert.setAttribute('role', 'alert');
    alert.textContent = message;
    alerts.append(alert);
}

// Same banner and field errors as the server-rendered error state
function showErrors(form, errors) {
    const alerts = document.querySelector('.auth-alerts');
    alerts.innerHTML = '';
    form.querySelectorAll('.field-error').forEach((p) => p.remove());
    form.querySelectorAll('.has-error').forEach((field) => field.classList.remove('has-error'));

    Object.entries(errors).forEach(([name, messages]) => {
        const input = form.elements[name];
        const field = input && input.closest ? input.closest('.field') : null;

        if (!field) {
            messages.forEach((message) => addAlert(alerts, message));
            if (name === '__all__' && form.dataset.errorField) {
                form.elements[form.dataset.errorField].closest('.field').classList.add('has-error');
            }
            return;
        }

        field.classList.add('has-error');
        messages.forEach((message) => {
            const p = document.createElement('p');
            p.className = 'field-error';
            p.textContent = message;
            field.append(p);
        });
    });

    const firstInvalid = form.querySelector('.has-error input');
    if (firstInvalid) firstInvalid.focus();
}

// Log in and register without a page reload; the normal submit stays as the fallback
document.querySelectorAll('form[data-ajax-url]').forEach((form) => {
    const button = form.querySelector('[type="submit"]');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        button.disabled = true;

        let data;
        try {
            const response = await fetch(form.dataset.ajaxUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                body: new FormData(form),
                credentials: 'same-origin',
            });
            data = await response.json();
        } catch (error) {
            form.submit();
            return;
        }

        if (data.status === 'success') {
            window.location.href = data.redirect;
            return;
        }

        showErrors(form, data.errors);
        button.disabled = false;
    });
});
