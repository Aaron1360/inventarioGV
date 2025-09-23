// Fetch and populate store dropdown
export function setupStoreDropdown() {
    const storeSelect = document.getElementById('storeSelect');
    async function fetchStores() {
        try {
            const res = await fetch('/stores');
            const stores = await res.json();
            if (Array.isArray(stores) && stores.length > 0) {
                storeSelect.innerHTML = stores.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
            } else {
                storeSelect.innerHTML = '<option value="">No hay sucursales</option>';
            }
        } catch (err) {
            storeSelect.innerHTML = '<option value="">Error al cargar sucursales</option>';
        }
    }
    if (storeSelect) {
        fetchStores();
    }
}
