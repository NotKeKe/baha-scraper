document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const globalStatusEl = document.getElementById('global-status');
    const pageCountEl = document.getElementById('page-count');
    const activeScrapersEl = document.getElementById('active-scrapers-count');
    const totalScrapersEl = document.getElementById('total-scrapers-count');
    const tasksCountEl = document.getElementById('tasks-count');
    const cpuUsageEl = document.getElementById('cpu-usage');
    const memUsageEl = document.getElementById('mem-usage');
    const lastUpdatedEl = document.getElementById('last-updated');
    const scrapersContainer = document.getElementById('scrapers-container');

    // Search & Pagination element
    const searchInput = document.getElementById('search-input');
    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');
    const pageInfo = document.getElementById('page-info');
    const refreshBtn = document.getElementById('refresh-btn');


    // State
    let currentPage = 1;
    const limit = 20;
    let searchQuery = '';
    let debounceTimer;

    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleString();
    }

    function getStatusColor(status) {
        status = status.toLowerCase();
        if (status.includes('running') || status.includes('active') || status.includes('fetching')) return 'var(--accent-color)';
        if (status.includes('done') || status.includes('complete') || status.includes('fetched')) return 'var(--success-color)';
        if (status.includes('error') || status.includes('fail')) return 'var(--error-color)';
        return 'var(--text-secondary)';
    }

    async function fetchStatus() {
        try {
            const queryParams = new URLSearchParams({
                page: currentPage,
                limit: limit,
                q: searchQuery
            });
            const response = await fetch(`/api/status?${queryParams}`);
            const data = await response.json();

            // Update Global Metrics
            globalStatusEl.textContent = data.curr_status;
            globalStatusEl.style.color = getStatusColor(data.curr_status);
            globalStatusEl.style.borderColor = getStatusColor(data.curr_status);

            pageCountEl.textContent = data.page_count;
            activeScrapersEl.textContent = data.active_scrapers_count;
            totalScrapersEl.textContent = data.total_scrapers_count;
            tasksCountEl.textContent = data.tasks_count;
            cpuUsageEl.innerHTML = `
                <div class="metric-value-group">
                    <span class="metric-primary">${data.system_metrics.cpu_usage}%</span>
                </div>`;

            const mem = data.system_metrics;
            memUsageEl.innerHTML = `
                <div class="metric-value-group">
                    <span class="metric-primary">${mem.memory_usage}%</span>
                    <span class="metric-secondary">${formatBytes(mem.memory_used)} / ${formatBytes(mem.memory_total)}</span>
                </div>`;
            lastUpdatedEl.textContent = new Date().toLocaleTimeString();

            // Update Scrapers List
            scrapersContainer.innerHTML = '';

            Object.entries(data.scrapers_status).forEach(([bsn, status]) => {
                const card = document.createElement('div');
                card.className = `scraper-card status-${status.post_list_status.toLowerCase()}`;

                const mainStatus = status.post_status || status.post_list_status;
                const statusColor = getStatusColor(mainStatus);
                const title = status.theme_title || bsn;

                card.innerHTML = `
                    <div class="scraper-header">
                        <div class="scraper-name" title="${bsn}">${title}</div>
                        <div class="scraper-status-pill" style="color: ${statusColor}; border: 1px solid ${statusColor}">${mainStatus}</div>
                    </div>
                    <div class="scraper-details">
                        <div class="detail-item">
                            <span>BSN</span>
                            <span>${bsn}</span>
                        </div>
                        <div class="detail-item">
                            <span>Post Status</span>
                            <span>${status.post_status}</span>
                        </div>
                        <div class="detail-item">
                            <span>List Status</span>
                            <span>${status.post_list_status}</span>
                        </div>
                        <div class="detail-item">
                            <span>Start Time</span>
                            <span>${formatDate(status.start_time)}</span>
                        </div>
                        <div class="detail-item">
                            <span>End Time</span>
                            <span>${formatDate(status.end_time)}</span>
                        </div>
                    </div>
                `;
                scrapersContainer.appendChild(card);
            });

            // Update Pagination Controls
            const totalItems = data.filtered_count;
            const totalPages = Math.ceil(totalItems / limit) || 1;

            pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
            prevBtn.disabled = currentPage <= 1;
            nextBtn.disabled = currentPage >= totalPages;

        } catch (error) {
            console.error('Error fetching status:', error);
            globalStatusEl.textContent = 'Connection Error';
            globalStatusEl.style.color = 'var(--error-color)';
        }
    }

    // Event Listeners
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = e.target.value.trim();
            currentPage = 1; // Reset to page 1 on search
            fetchStatus();
        }, 300);
    });

    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchStatus();
        }
    });

    nextBtn.addEventListener('click', () => {
        // We rely on disabled state, but double check
        currentPage++;
        fetchStatus();
    });

    refreshBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to restart the scraper?')) return;

        const originalText = refreshBtn.textContent;
        refreshBtn.disabled = true;
        refreshBtn.textContent = 'Requesting...';

        try {
            const res = await fetch('/api/refresh', { method: 'POST' });
            const data = await res.json();

            if (res.ok && data.status === 'success') {
                // Success
                fetchStatus();
            } else {
                alert(data.message || 'Failed to start scraper');
            }
        } catch (error) {
            console.error('Error restarting scraper:', error);
            alert('Connection Error');
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.textContent = originalText;
        }
    });

    // Initial fetch
    fetchStatus();

    // Poll every 2 seconds
    setInterval(fetchStatus, 2000);
});
