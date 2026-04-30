const SETTING_INPUTS = [
    'appointment_url',
    'check_interval_seconds',
    'interval_jitter_fraction',
    'check_days_ahead',
    'notification_provider',
    'notification_endpoint',
    'notification_auth',
    'dashboard_refresh_rate_seconds',
];

async function initSettingsPage() {
    // Load all settings
    const response = await fetch('/api/settings');
    const settings = await response.json();

    // Populate form fields
    SETTING_INPUTS.forEach(key => {
        const input = document.getElementById(key);
        if (input && settings[key]) {
            input.value = settings[key].value;

            // Set up auto-save on change
            input.addEventListener('change', () => {
                saveSetting(key, input.value);
            });
        }
    });

    // Set up test buttons
    document.getElementById('test-notification-btn').addEventListener('click', testNotification);
    document.getElementById('test-data-btn').addEventListener('click', testDataRetrieval);
}

async function saveSetting(key, value) {
    try {
        const response = await fetch(`/api/settings/${key}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value }),
        });

        if (!response.ok) {
            console.error(`Failed to save ${key}`);
        }
    } catch (error) {
        console.error('Save failed:', error);
    }
}

async function testNotification() {
    const btn = document.getElementById('test-notification-btn');
    const resultDiv = document.getElementById('notification-result');

    btn.disabled = true;
    btn.textContent = 'Testen...';
    resultDiv.innerHTML = '<div class="spinner"></div>';
    resultDiv.classList.remove('hidden');

    try {
        const response = await fetch('/api/test/notification', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<span class="success">✓ ${data.message}</span>`;
        } else {
            resultDiv.innerHTML = `<span class="error">✗ ${data.message}</span>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<span class="error">✗ ${error.message}</span>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test Notificatie';
    }
}

async function testDataRetrieval() {
    const btn = document.getElementById('test-data-btn');
    const resultDiv = document.getElementById('data-result');

    btn.disabled = true;
    btn.textContent = 'Testen...';
    resultDiv.innerHTML = '<div class="spinner"></div>';
    resultDiv.classList.remove('hidden');

    try {
        const response = await fetch('/api/test/data-retrieval', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<span class="success">✓ ${data.message}</span>`;
        } else {
            resultDiv.innerHTML = `<span class="error">✗ ${data.message}</span>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<span class="error">✗ ${error.message}</span>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test Gegevens Ophalen';
    }
}
