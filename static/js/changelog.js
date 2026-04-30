async function initChangeLogPage() {
    await loadAndRenderChangeLog();
}

async function refreshChangeLogPage() {
    await loadAndRenderChangeLog();
    updateLastCheck();
}

async function loadAndRenderChangeLog() {
    try {
        const response = await fetch('/api/slot-history');
        const data = await response.json();

        if (!data.entries || data.entries.length < 2) {
            document.getElementById('changelog-content').innerHTML =
                '<p class="no-changes">Geen wijzigingen opgeslagen</p>';
            return;
        }

        const changes = computeChanges(data.entries);
        renderChangeLog(changes);
    } catch (error) {
        console.error('Failed to load changelog:', error);
    }
}

function computeChanges(entries) {
    // Diff consecutive entries to find added/removed slots
    const changes = [];

    for (let i = 1; i < entries.length; i++) {
        const prev = new Set(entries[i - 1].slots || []);
        const current = new Set(entries[i].slots || []);

        const added = [...current].filter(s => !prev.has(s));
        const removed = [...prev].filter(s => !current.has(s));

        if (added.length > 0 || removed.length > 0) {
            changes.push({
                checkedAt: entries[i].checked_at,
                added: added.sort(),
                removed: removed.sort(),
            });
        }
    }

    return changes.reverse(); // Most recent first
}

function formatChangeTime(timeStr) {
    const date = new Date(timeStr);
    return date.toLocaleString('nl-NL');
}

function formatSlotTime(slotStr) {
    const date = new Date(slotStr);
    return date.toLocaleString('nl-NL', {
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
}

function renderChangeLog(changes) {
    const container = document.getElementById('changelog-content');

    if (changes.length === 0) {
        container.innerHTML = '<p class="no-changes">Geen wijzigingen opgeslagen</p>';
        return;
    }

    let html = '<div class="timeline">';

    changes.forEach(change => {
        html += `
            <div class="timeline-entry">
                <div class="entry-time">${formatChangeTime(change.checkedAt)}</div>
                <div class="entry-changes">
        `;

        if (change.added.length > 0) {
            html += `
                <div class="change added">
                    <span class="change-badge">+${change.added.length}</span>
                    <div class="slot-list">
            `;
            change.added.forEach(slot => {
                html += `<div class="slot-tag">${formatSlotTime(slot)}</div>`;
            });
            html += '</div></div>';
        }

        if (change.removed.length > 0) {
            html += `
                <div class="change removed">
                    <span class="change-badge">-${change.removed.length}</span>
                    <div class="slot-list">
            `;
            change.removed.forEach(slot => {
                html += `<div class="slot-tag">${formatSlotTime(slot)}</div>`;
            });
            html += '</div></div>';
        }

        html += '</div></div>';
    });

    html += '</div>';
    container.innerHTML = html;
}
