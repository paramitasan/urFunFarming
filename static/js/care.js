// List page: the thresholds card. Hide / Show is remembered on this device, −/+ change a value
// by its step, Reset fills the defaults, and the preview chips follow the numbers before saving.
const thresholdPanel = document.querySelector('[data-threshold-panel]');
if (thresholdPanel) {
    document.documentElement.classList.add('js');
    const toggle = thresholdPanel.querySelector('[data-threshold-toggle]');
    const body = thresholdPanel.querySelector('[data-threshold-body]');
    const inputs = [...body.querySelectorAll('input[type="number"]')];
    const HIDDEN_KEY = 'care-thresholds-hidden';

    function setOpen(open) {
        thresholdPanel.classList.toggle('is-collapsed', !open);
        body.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        toggle.querySelector('span').textContent = open ? 'Hide thresholds' : 'Show thresholds';
    }

    let startHidden = false;
    try {
        startHidden = localStorage.getItem(HIDDEN_KEY) === 'yes';
    } catch (e) {
        // Storage blocked (private window): the card simply starts open
    }
    toggle.hidden = false;
    setOpen(!startHidden);

    toggle.addEventListener('click', () => {
        const open = body.hidden;
        setOpen(open);
        try {
            localStorage.setItem(HIDDEN_KEY, open ? 'no' : 'yes');
        } catch (e) {
            // Nothing to remember it in; it still works for this visit
        }
    });

    function updatePreview() {
        const [rain, temp, wind] = inputs.map((input) => Number(input.value));
        thresholdPanel.querySelectorAll('.care-preview-chip').forEach((chip) => {
            // Same rule as meets_thresholds in weather/services.py
            const good = Number(chip.dataset.rain) <= rain && Number(chip.dataset.temp) <= temp && Number(chip.dataset.wind) <= wind;
            chip.classList.toggle('is-good', good);
            chip.querySelector('.visually-hidden').textContent = good ? 'within your limits' : 'outside your limits';
        });
    }

    thresholdPanel.querySelectorAll('[data-step]').forEach((button) => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.getAttribute('aria-controls'));
            const step = Number(input.step) || 1;
            const max = input.max === '' ? Infinity : Number(input.max);
            const next = (Number(input.value) || 0) + step * Number(button.dataset.step);
            // Round to one decimal so 0.5 steps never show as 2.4999
            input.value = String(Math.min(max, Math.max(0, Math.round(next * 10) / 10)));
            updatePreview();
        });
    });

    thresholdPanel.querySelector('[data-threshold-reset]').addEventListener('click', () => {
        inputs.forEach((input) => {
            input.value = input.dataset.default;
        });
        updatePreview();
        inputs[0].focus();
    });

    inputs.forEach((input) => input.addEventListener('input', updatePreview));
}

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
