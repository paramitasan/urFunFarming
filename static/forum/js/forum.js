// Submits the search/filter form as soon as a sort or filter option changes.
document.addEventListener("change", (event) => {
    if (!event.target.matches("[data-autosubmit]")) return;

    const form = document.getElementById("forum-filters");
    if (event.target.form) event.target.form.requestSubmit();
});

// "..." menu: close on outside click or Escape.
document.addEventListener("click", (event) => {
    document.querySelectorAll("details.forum-menu[open]").forEach((menu) => {
        if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
});

document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll("details.forum-menu[open]").forEach((menu) => {
        menu.removeAttribute("open");
        menu.querySelector("summary").focus();
    });
});

// "Post answer" stays disabled until the box has something other than spaces.
document.querySelectorAll("[data-reply-form]").forEach((form) => {
    const textarea = form.querySelector("textarea");
    const submit = form.querySelector("[data-reply-submit]");
    if (!textarea || !submit) return;

    const sync = () => {
        submit.disabled = textarea.value.trim() === "";
    };
    textarea.addEventListener("input", sync);
    sync();
});

// Edit answer: live "0 / 3000" counter.
document.querySelectorAll("[data-char-counter]").forEach((box) => {
    const textarea = box.querySelector("textarea");
    const counter = box.querySelector(".reply-counter");
    if (!textarea || !counter) return;

    const update = () => {
        counter.textContent = `${textarea.value.length} / ${textarea.maxLength}`;
    };
    textarea.addEventListener("input", update);
    update();
});

// Edit answer: focus the box with the caret at the end of the text.
const editingBox = document.querySelector(".answer-card textarea");
if (editingBox && editingBox.closest(".reply-edit-field")) {
    editingBox.focus();
    const end = editingBox.value.length;
    editingBox.setSelectionRange(end, end);
}