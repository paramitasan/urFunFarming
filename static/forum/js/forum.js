// Submits the search/filter form as soon as a sort or filter option changes.
document.addEventListener("change", (event) => {
    if (!event.target.matches("[data-autosubmit]")) return;

    const form = document.getElementById("forum-filters");
    if (form) form.requestSubmit();
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