// Scraper notification UI block
export function showScraperNotification() {
    const scraperNotification = document.getElementById('scraperNotification');
    if (scraperNotification) {
        scraperNotification.style.display = 'block';
        document.body.classList.add('scraper-blocked');
    }
}

export function hideScraperNotification() {
    const scraperNotification = document.getElementById('scraperNotification');
    if (scraperNotification) {
        scraperNotification.style.display = 'none';
        document.body.classList.remove('scraper-blocked');
    }
}
