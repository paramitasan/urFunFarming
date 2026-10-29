// Journal list: picking a dropdown option sends the filter form straight away.
// Listening on the whole page means it still works after the list is refreshed by a delete
document.addEventListener('change', (event) => {
    if (event.target.matches('[data-filter-form] select')) {
        event.target.form.submit();
    }
});
