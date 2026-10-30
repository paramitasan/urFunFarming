// Card menus: "Delete" opens the confirm overlay instead of going to the delete page
const deleteDialog = document.querySelector('[data-delete-dialog]');

if (deleteDialog) {
    const deleteForm = deleteDialog.querySelector('[data-delete-form]');
    const nameText = deleteDialog.querySelector('[data-delete-name]');

    document.addEventListener('click', (event) => {
        const deleteLink = event.target.closest('a[data-delete-name]');
        if (!deleteLink) {
            return;
        }
        event.preventDefault();
        // The form posts to the same delete address the link would have opened
        deleteForm.action = deleteLink.href;
        nameText.textContent = deleteLink.dataset.deleteName;
        // Close the card's menu behind the overlay
        deleteLink.closest('details')?.removeAttribute('open');
        deleteDialog.showPopover();
    });
}
