// Group inventory by presentation and sort by line, name, presentation
function groupAndSortInventory(data) {
    // Group by line, name, presentation
    const grouped = {};
    data.forEach(item => {
        const key = `${item.line}|${item.name}|${item.presentation}`;
        if (!grouped[key]) {
            grouped[key] = {
                line: item.line,
                name: item.name,
                presentation: item.presentation,
                stock: new Set()
            };
        }
        grouped[key].stock.add(item.stock);
    });
    // Convert sets to arrays
    const groupedArray = Object.values(grouped).map(v => ({
        ...v,
        stock: Array.from(v.stock)
    }));
    // Sort by line (custom order), then name, then presentation
    const lineOrder = [
        "COCA COLA", "PEPSI", "VARIOS", "CERVEZA", "CIGARROS", "BOTANAS", "DESECHABLE"
    ];
    function lineKey(line) {
        const idx = lineOrder.indexOf(line);
        return idx === -1 ? lineOrder.length : idx;
    }
    groupedArray.sort((a, b) => {
        const lineCmp = lineKey(a.line) - lineKey(b.line);
        if (lineCmp !== 0) return lineCmp;
        if (a.name < b.name) return -1;
        if (a.name > b.name) return 1;
        if (a.presentation < b.presentation) return -1;
        if (a.presentation > b.presentation) return 1;
        return 0;
    });
    return groupedArray;
}

// Export for use in other scripts
window.groupAndSortInventory = groupAndSortInventory;
