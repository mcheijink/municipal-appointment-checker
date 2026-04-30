let allSlots = {};
let slotTimelines = {};

async function initSlotsPage() {
    await loadSlotHistory();
    renderSlotsHierarchy();
}

async function refreshSlotsPage() {
    await loadSlotHistory();
    renderSlotsHierarchy();
    updateLastCheck();
}

async function loadSlotHistory() {
    try {
        const response = await fetch('/api/slot-history');
        const data = await response.json();

        if (!data.entries || data.entries.length === 0) {
            return;
        }

        // Get latest slots
        const latest = data.entries[data.entries.length - 1];
        allSlots = groupSlotsByDay(latest.slots || []);

        // Build timeline for each slot (first appeared, duration, closed, gaps)
        slotTimelines = buildSlotTimelines(data.entries);

        // Update last check time
        const lastCheckEl = document.getElementById('last-check');
        if (lastCheckEl) {
            lastCheckEl.textContent = new Date(latest.checked_at).toLocaleString('nl-NL');
        }
    } catch (error) {
        console.error('Failed to load slot history:', error);
    }
}

function groupSlotsByDay(slots) {
    const grouped = {};

    slots.forEach(slotStr => {
        const date = new Date(slotStr);
        const dayKey = date.toISOString().split('T')[0]; // YYYY-MM-DD

        if (!grouped[dayKey]) {
            grouped[dayKey] = [];
        }
        grouped[dayKey].push(slotStr);
    });

    // Sort days, sort times within each day
    Object.keys(grouped).forEach(day => {
        grouped[day].sort();
    });

    return grouped;
}

function getPeriod(timeStr) {
    // timeStr is "2026-04-22T10:30:00"
    const time = new Date(timeStr);
    const hour = time.getHours();

    if (hour < 11) return 'Early';
    if (hour < 13.5) return 'Mid';
    return 'Late';
}

function groupByPeriod(slots) {
    const periods = { Early: [], Mid: [], Late: [] };

    slots.forEach(slot => {
        const period = getPeriod(slot);
        periods[period].push(slot);
    });

    return periods;
}

function buildSlotTimelines(entries) {
    // For each unique slot across all history entries, track:
    // - cycles: array of {appeared, closed, duration}
    // - gaps: array of {closed, reopened, duration}
    const timelines = {};

    entries.forEach((entry, idx) => {
        const checkedAt = new Date(entry.checked_at);
        (entry.slots || []).forEach(slot => {
            if (!timelines[slot]) {
                timelines[slot] = {
                    cycles: [{
                        appeared: checkedAt,
                        closed: null,
                    }],
                    gaps: [],
                };
            } else {
                // If slot exists, update the last cycle's closed time if needed
                const lastCycle = timelines[slot].cycles[timelines[slot].cycles.length - 1];
                if (lastCycle.closed === null) {
                    lastCycle.closed = null; // Still open
                }
            }
        });

        // Mark slots that disappeared and detect re-openings
        if (idx > 0) {
            const prevSlots = new Set(entries[idx - 1].slots || []);
            const currentSlots = new Set(entries[idx].slots || []);

            prevSlots.forEach(slot => {
                if (!currentSlots.has(slot) && timelines[slot]) {
                    // Slot closed
                    const lastCycle = timelines[slot].cycles[timelines[slot].cycles.length - 1];
                    if (lastCycle.closed === null) {
                        lastCycle.closed = checkedAt;
                    }
                }
            });

            currentSlots.forEach(slot => {
                if (!prevSlots.has(slot) && timelines[slot]) {
                    // Slot reopened - check if this is a re-opening
                    const lastCycle = timelines[slot].cycles[timelines[slot].cycles.length - 1];
                    if (lastCycle.closed !== null) {
                        // Calculate gap duration
                        const gapDuration = checkedAt - lastCycle.closed;
                        timelines[slot].gaps.push({
                            closed: lastCycle.closed,
                            reopened: checkedAt,
                            duration: gapDuration,
                        });

                        // Start new cycle
                        timelines[slot].cycles.push({
                            appeared: checkedAt,
                            closed: null,
                        });
                    }
                }
            });
        }
    });

    return timelines;
}

function formatDayLabel(dayKey) {
    const date = new Date(dayKey + 'T00:00:00Z');
    const days = ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'];
    const months = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];

    const day = days[date.getUTCDay()];
    const date_num = date.getUTCDate();
    const month = months[date.getUTCMonth()];
    const year = date.getUTCFullYear();

    return `${day} ${date_num} ${month} ${year}`;
}

function formatTimeLabel(slotStr) {
    const date = new Date(slotStr);
    return date.toLocaleString('nl-NL', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function renderSlotsHierarchy() {
    const container = document.getElementById('slots-content');

    if (Object.keys(allSlots).length === 0) {
        container.innerHTML = '<p class="no-slots">Geen afspraken beschikbaar</p>';
        return;
    }

    let html = '<div class="hierarchy">';

    // Days level
    Object.keys(allSlots).sort().forEach(dayKey => {
        const slotCount = allSlots[dayKey].length;
        const dayId = `day-${dayKey}`;

        html += `
            <div class="day-item">
                <button class="expander" data-day-id="${dayId}">
                    <span class="expander-icon">▶</span>
                    ${formatDayLabel(dayKey)} <span class="count">(${slotCount} slots)</span>
                </button>
                <div id="${dayId}" class="day-content hidden">
        `;

        // Periods level
        const periods = groupByPeriod(allSlots[dayKey]);
        ['Early', 'Mid', 'Late'].forEach(period => {
            const periodSlots = periods[period];
            if (periodSlots.length === 0) return;

            const periodId = `period-${dayKey}-${period}`;
            html += `
                <div class="period-item">
                    <button class="expander" data-period-id="${periodId}">
                        <span class="expander-icon">▶</span>
                        ${period} <span class="count">(${periodSlots.length} slots)</span>
                    </button>
                    <div id="${periodId}" class="period-content hidden">
            `;

            // Times level
            periodSlots.forEach(slot => {
                html += `
                    <div class="time-item" data-slot="${slot}">
                        ${formatTimeLabel(slot)}
                    </div>
                `;
            });

            html += '</div></div>';
        });

        html += '</div></div>';
    });

    html += '</div>';
    container.innerHTML = html;

    attachSlotsEventListeners();
}

function attachSlotsEventListeners() {
    // Day expanders
    document.querySelectorAll('[data-day-id]').forEach(btn => {
        btn.addEventListener('click', () => {
            const dayId = btn.dataset.dayId;
            const content = document.getElementById(dayId);
            const icon = btn.querySelector('.expander-icon');

            content.classList.toggle('hidden');
            icon.textContent = content.classList.contains('hidden') ? '▶' : '▼';
        });
    });

    // Period expanders
    document.querySelectorAll('[data-period-id]').forEach(btn => {
        btn.addEventListener('click', () => {
            const periodId = btn.dataset.periodId;
            const content = document.getElementById(periodId);
            const icon = btn.querySelector('.expander-icon');

            content.classList.toggle('hidden');
            icon.textContent = content.classList.contains('hidden') ? '▶' : '▼';
        });
    });

    // Time items (show detail panel)
    document.querySelectorAll('.time-item').forEach(item => {
        item.addEventListener('click', () => {
            const slot = item.dataset.slot;
            showDetailPanel(slot);
        });
    });
}

function formatDuration(ms) {
    const days = Math.floor(ms / (1000 * 60 * 60 * 24));
    const hours = Math.floor((ms % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

function showDetailPanel(slot) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    const timeline = slotTimelines[slot] || {};

    const date = new Date(slot);
    const day = date.toLocaleDateString('nl-NL');
    const time = date.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', hour12: false });

    let timelineHtml = '';

    // Display cycles and gaps
    if (timeline.cycles && timeline.cycles.length > 0) {
        timeline.cycles.forEach((cycle, idx) => {
            // Cycle header
            if (idx > 0) {
                timelineHtml += `<div class="cycle-separator">Cycle ${idx + 1}</div>`;
            }

            // Appeared
            timelineHtml += `
                <div class="timeline-event">
                    <span class="event-label">Appeared:</span>
                    <span class="event-time">${cycle.appeared?.toLocaleString('nl-NL') || '—'}</span>
                </div>
            `;

            // Duration or status
            if (cycle.closed) {
                const duration = cycle.closed - cycle.appeared;
                const durationStr = formatDuration(duration);
                timelineHtml += `
                    <div class="timeline-event">
                        <span class="event-label">Open for:</span>
                        <span class="event-time">${durationStr}</span>
                    </div>
                    <div class="timeline-event closed">
                        <span class="event-label">Closed:</span>
                        <span class="event-time">${cycle.closed.toLocaleString('nl-NL')}</span>
                    </div>
                `;
            } else {
                timelineHtml += `
                    <div class="timeline-event current">
                        <span class="event-label">Status:</span>
                        <span class="event-time">⚡ Currently available</span>
                    </div>
                `;
            }

            // Gap to next cycle
            if (idx < timeline.gaps.length) {
                const gap = timeline.gaps[idx];
                const gapDuration = formatDuration(gap.duration);
                timelineHtml += `
                    <div class="timeline-event gap">
                        <span class="event-label">Gap:</span>
                        <span class="event-time">${gapDuration}</span>
                    </div>
                    <div class="timeline-event">
                        <span class="event-label">Reopened:</span>
                        <span class="event-time">${gap.reopened.toLocaleString('nl-NL')}</span>
                    </div>
                `;
            }
        });
    }

    content.innerHTML = `
        <div class="detail-header">
            <h3>${day}, ${time}</h3>
            ${timeline.cycles && timeline.cycles.length > 1 ? `<span class="cycle-count">${timeline.cycles.length} cycles</span>` : ''}
        </div>
        <div class="detail-timeline">
            ${timelineHtml}
        </div>
    `;

    panel.classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.querySelector('.close-button');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            document.getElementById('detail-panel').classList.add('hidden');
        });
    }
});

function updateLastCheck() {
    // Called by refreshSlotsPage, updates last check time in footer
    // Logic already in loadSlotHistory
}
