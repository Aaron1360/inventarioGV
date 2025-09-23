import { setupAuth } from './auth.js';
import { setupInventory } from './inventory.js';
import { setupStoreDropdown } from './store.js';

document.addEventListener('DOMContentLoaded', function() {
    setupAuth();
    setupInventory();
    setupStoreDropdown();
    // On page load, ensure table is hidden and message is shown
    const preTableMessage = document.getElementById('preTableMessage');
    const tableContainer = document.getElementById('tableContainer');
    if (preTableMessage) preTableMessage.classList.remove('d-none');
    if (tableContainer) tableContainer.classList.add('d-none');
});