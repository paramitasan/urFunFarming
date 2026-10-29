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

// Delete dialog: Escape does the same as "Keep it"
const keepLink = document.querySelector('[data-dialog-cancel]');
if (keepLink) {
    keepLink.focus();
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            window.location.href = keepLink.href;
        }
    });
}

// Add / Edit form: tapping a best time fills the date and time, and the weather check follows the fields
const dateField = document.getElementById('id_target_date');
const timeField = document.getElementById('id_target_time');
const check = document.querySelector('[data-weather-check]');
const slotData = document.getElementById('care-weather-slots');

if (dateField && timeField && check && slotData) {
    const slots = JSON.parse(slotData.textContent);
    const text = check.querySelector('[data-weather-check-text]');
    const SLOT_MS = 3 * 60 * 60 * 1000;

    // Each slot's message is written by the server (care/planning.py), so the wording lives in one place
    function updateCheck() {
        if (!slots.length || !dateField.value || !timeField.value) {
            return; // keep the server's message (weather unavailable, or the whole-day summary)
        }
        const chosen = new Date(`${dateField.value}T${timeField.value}:00+07:00`).getTime();
        const slot = slots.find((s) => {
            const start = new Date(s.start).getTime();
            return start <= chosen && chosen < start + SLOT_MS;
        });
        check.hidden = false;
        if (slot) {
            text.textContent = slot.text;
            check.dataset.good = slot.good ? 'true' : 'false';
        } else {
            text.textContent = 'BMKG has no forecast for this time yet. Forecasts cover the next 3 days.';
            check.dataset.good = 'none';
        }
    }

    function markSelected() {
        document.querySelectorAll('.care-best-time').forEach((link) => {
            const on = link.dataset.date === dateField.value && link.dataset.time === timeField.value;
            link.classList.toggle('is-selected', on);
            if (on) {
                link.setAttribute('aria-current', 'true');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    }

    document.querySelectorAll('.care-best-time').forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            dateField.value = link.dataset.date;
            timeField.value = link.dataset.time;
            markSelected();
            updateCheck();
            timeField.focus();
        });
    });

    dateField.addEventListener('change', () => { markSelected(); updateCheck(); });
    timeField.addEventListener('change', () => { markSelected(); updateCheck(); });
}
