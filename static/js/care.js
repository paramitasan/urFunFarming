/* Plant care: the parts of the page that talk to the server without a reload.
   Everything here is an enhancement. Without JavaScript the same forms submit
   normally and the same links work, the page just reloads each time. */

const CSRF_NAME = 'csrftoken';

function getCookie(name) {
    const match = document.cookie.split(';').map((c) => c.trim()).find((c) => c.startsWith(name + '='));
    return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

// Marks a request as AJAX. The views answer with JSON instead of a redirect
// when they see this header.
function ajaxHeaders(extra = {}) {
    return { 'X-Requested-With': 'fetch', ...extra };
}

async function postForm(form) {
    const response = await fetch(form.action, {
        method: 'POST',
        headers: ajaxHeaders({ 'X-CSRFToken': getCookie(CSRF_NAME) }),
        body: new FormData(form),
        credentials: 'same-origin',
    });
    const payload = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, payload };
}

/* 1. Ticking a task off, without losing the scroll position */

function wireDoneButtons(root) {
    root.querySelectorAll('[data-toggle-done]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const card = form.closest('[data-task]');
            card.classList.add('care-is-loading');
            try {
                const { ok, payload } = await postForm(form);
                if (!ok) {
                    form.submit(); // fall back to a normal post
                    return;
                }
                card.classList.toggle('is-done', payload.is_done);
                card.classList.toggle('is-overdue', payload.is_overdue);
                const button = form.querySelector('.care-done-button');
                button.setAttribute('aria-pressed', payload.is_done ? 'true' : 'false');
                button.querySelector('.care-done-mark').textContent = payload.is_done ? '✓' : '';
                refreshList();
            } finally {
                card.classList.remove('care-is-loading');
            }
        });
    });
}

/* 2. Filtering, which replaces only the list */

const taskArea = document.querySelector('[data-task-area]');
const filterForm = document.querySelector('[data-filter-form]');
let listController;

async function refreshList() {
    if (!taskArea || !filterForm) return;
    // A newer request makes the previous one pointless, so cancel it.
    if (listController) listController.abort();
    listController = new AbortController();

    const query = new URLSearchParams(new FormData(filterForm)).toString();
    taskArea.classList.add('care-is-loading');
    try {
        const response = await fetch(`${filterForm.action}?${query}`, {
            headers: ajaxHeaders({ Accept: 'application/json' }),
            credentials: 'same-origin',
            signal: listController.signal,
        });
        if (!response.ok) return;
        const payload = await response.json();
        taskArea.innerHTML = payload.html;
        wireDoneButtons(taskArea);
        // The counts travel with the list, otherwise the chips keep yesterday's numbers.
        Object.entries(payload.counts || {}).forEach(([bucket, total]) => {
            const slot = document.querySelector(`[data-count="${bucket}"]`);
            if (slot) slot.textContent = total;
        });
        // Keep the address bar in step, so a reload shows the same filtering.
        window.history.replaceState({}, '', query ? `?${query}` : window.location.pathname);
    } catch (error) {
        if (error.name !== 'AbortError') console.error('Could not refresh the task list:', error);
    } finally {
        taskArea.classList.remove('care-is-loading');
    }
}

if (filterForm) {
    filterForm.addEventListener('submit', (event) => {
        event.preventDefault();
        refreshList();
    });
    filterForm.querySelectorAll('input, select').forEach((field) => {
        field.addEventListener('change', refreshList);
    });
    // The submit button is only needed without JavaScript.
    const submit = filterForm.querySelector('.care-filter-submit');
    if (submit) submit.hidden = true;
}

/* 3. Saving the weather limits from the card */

const limitsForm = document.querySelector('[data-limits-form]');
if (limitsForm) {
    limitsForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        limitsForm.querySelectorAll('[data-error-for]').forEach((slot) => { slot.textContent = ''; });

        const { ok, payload } = await postForm(limitsForm);
        const outlook = document.querySelector('[data-outlook]');
        if (ok && outlook) {
            outlook.textContent = payload.outlook.text;
            outlook.dataset.outlookState = payload.outlook.state;
            refreshList();
        } else if (payload.errors) {
            Object.entries(payload.errors).forEach(([field, errors]) => {
                const slot = limitsForm.querySelector(`[data-error-for="${field}"]`);
                if (slot) slot.textContent = errors.join(' ');
            });
        }
    });
}

/* 4. Judging the chosen time while the grower is still picking it */

const taskForm = document.querySelector('[data-task-form]');
if (taskForm) {
    const checkUrl = taskForm.dataset.weatherUrl;
    const dateField = taskForm.querySelector('#id_planned_for');
    const timeField = taskForm.querySelector('#id_planned_time');
    const verdict = document.querySelector('[data-verdict]');
    let checkTimer;
    let checkController;

    async function checkWeather() {
        if (!verdict || !dateField) return;
        if (checkController) checkController.abort();
        checkController = new AbortController();

        const query = new URLSearchParams({ date: dateField.value || '', time: timeField.value || '' });
        try {
            const response = await fetch(`${checkUrl}?${query}`, {
                headers: ajaxHeaders({ Accept: 'application/json' }),
                credentials: 'same-origin',
                signal: checkController.signal,
            });
            if (!response.ok) return;
            const payload = await response.json();
            verdict.textContent = payload.verdict.text;
            verdict.dataset.verdictState = payload.verdict.state;
        } catch (error) {
            if (error.name !== 'AbortError') console.error('Weather check failed:', error);
        }
    }

    // Typing a date fires several change events, so wait until it settles.
    function scheduleCheck() {
        clearTimeout(checkTimer);
        checkTimer = setTimeout(checkWeather, 250);
    }

    [dateField, timeField].forEach((field) => {
        if (field) field.addEventListener('change', scheduleCheck);
    });

    document.querySelectorAll('.care-suggestion').forEach((button) => {
        button.addEventListener('click', () => {
            if (dateField) dateField.value = button.dataset.date;
            if (timeField) timeField.value = button.dataset.time;
            document.querySelectorAll('.care-suggestion').forEach((other) => {
                other.classList.toggle('is-selected', other === button);
            });
            checkWeather();
        });
    });
}

if (taskArea) wireDoneButtons(taskArea);
