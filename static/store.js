export async function refreshStoreDropdown() {
    const select = document.getElementById('storeSelect');
    if (!select) return [];
    try {
        const response = await fetch('/api/inventory/stores');
        if (!response.ok) return [];
        const { stores } = await response.json();
        select.innerHTML = '<option value="">Selecciona una sucursal</option>';
        stores.forEach(store => {
            const option = document.createElement('option');
            option.value = store;
            option.textContent = store;
            select.appendChild(option);
        });
        if (stores.length > 0) {
            select.value = stores[0];
        }
        return stores;
    } catch {
        select.innerHTML = '<option value="">Las sucursales no están disponibles</option>';
        return [];
    }
}

export async function setupStoreDropdown() {
    await refreshStoreDropdown();
}
