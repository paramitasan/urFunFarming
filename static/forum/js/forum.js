// Submits the search/filter form as soon as a sort or filter option changes.
document.addEventListener("change", (event) => {
    if (!event.target.matches("[data-autosubmit]")) return;

    const form = document.getElementById("forum-filters");
    if (form) form.requestSubmit();
});