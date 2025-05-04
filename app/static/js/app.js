// API URL base path
const API_BASE_URL = '/api/v1';

// Toast notification system
function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    const toastId = `toast-${Date.now()}`;
    const bgClass = type === 'success' ? 'bg-success' : 'bg-danger';

    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center ${bgClass} text-white border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
    toast.show();
    
    // Remove toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// Format date string
function formatDate(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).format(date);
}

// ======== Subscriptions ========
// Load subscriptions
async function loadSubscriptions() {
    try {
        const response = await fetch(`${API_BASE_URL}/subscriptions/`);
        if (!response.ok) throw new Error('Failed to load subscriptions');
        
        const subscriptions = await response.json();
        displaySubscriptions(subscriptions);
        populateSubscriptionDropdowns(subscriptions);
    } catch (error) {
        console.error('Error loading subscriptions:', error);
        showToast('Failed to load subscriptions: ' + error.message, 'error');
    }
}

// Display subscriptions in table
function displaySubscriptions(subscriptions) {
    const tableBody = document.getElementById('subscriptions-table-body');
    tableBody.innerHTML = '';
    
    if (!subscriptions.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center">No subscriptions found. Create one to get started.</td>
            </tr>
        `;
        return;
    }
    
    subscriptions.forEach(sub => {
        const eventTypes = sub.event_types ? sub.event_types.join(', ') : 'All events';
        const secretDisplay = sub.masked_secret || 'None';
        
        const row = `
            <tr>
                <td>${sub.id}</td>
                <td>${sub.target_url}</td>
                <td>${eventTypes}</td>
                <td>${secretDisplay}</td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-primary edit-subscription" data-id="${sub.id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger delete-subscription" data-id="${sub.id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        tableBody.insertAdjacentHTML('beforeend', row);
    });
    
    // Add event listeners for edit and delete buttons
    document.querySelectorAll('.edit-subscription').forEach(button => {
        button.addEventListener('click', () => editSubscription(button.dataset.id));
    });
    
    document.querySelectorAll('.delete-subscription').forEach(button => {
        button.addEventListener('click', () => deleteSubscription(button.dataset.id));
    });
}

// Populate subscription dropdowns (for webhook testing and logs)
function populateSubscriptionDropdowns(subscriptions) {
    const selectors = ['#subscription-select', '#log-subscription-select'];
    
    selectors.forEach(selector => {
        const dropdown = document.querySelector(selector);
        
        // Preserve the first option
        const firstOption = dropdown.options[0];
        dropdown.innerHTML = '';
        dropdown.appendChild(firstOption);
        
        // Add subscription options
        subscriptions.forEach(sub => {
            const option = document.createElement('option');
            option.value = sub.id;
            option.textContent = `${sub.target_url} ${sub.event_types ? '(' + sub.event_types.join(', ') + ')' : ''}`;
            dropdown.appendChild(option);
        });
    });
}

// Create new subscription
async function createSubscription() {
    const targetUrl = document.getElementById('target-url').value;
    const secret = document.getElementById('secret').value;
    const eventTypesInput = document.getElementById('event-types').value;
    
    // Parse event types if provided
    let eventTypes = null;
    if (eventTypesInput.trim()) {
        eventTypes = eventTypesInput.split(',').map(type => type.trim());
    }
    
    const subscriptionData = {
        target_url: targetUrl,
        secret: secret || null,
        event_types: eventTypes
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/subscriptions/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscriptionData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to create subscription');
        }
        
        const result = await response.json();
        showToast('Subscription created successfully!');
        
        // Close modal and reset form
        const modal = bootstrap.Modal.getInstance(document.getElementById('createSubscriptionModal'));
        modal.hide();
        document.getElementById('subscriptionForm').reset();
        
        // Reload subscriptions
        loadSubscriptions();
    } catch (error) {
        console.error('Error creating subscription:', error);
        showToast('Failed to create subscription: ' + error.message, 'error');
    }
}

// Load subscription for editing
async function editSubscription(subscriptionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/subscriptions/${subscriptionId}`);
        if (!response.ok) throw new Error('Failed to get subscription details');
        
        const subscription = await response.json();
        
        document.getElementById('edit-subscription-id').value = subscription.id;
        document.getElementById('edit-target-url').value = subscription.target_url;
        document.getElementById('edit-secret').value = ''; // Don't prefill secret
        
        if (subscription.event_types && subscription.event_types.length) {
            document.getElementById('edit-event-types').value = subscription.event_types.join(', ');
        } else {
            document.getElementById('edit-event-types').value = '';
        }
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('editSubscriptionModal'));
        modal.show();
    } catch (error) {
        console.error('Error loading subscription for editing:', error);
        showToast('Failed to load subscription details: ' + error.message, 'error');
    }
}

// Update subscription
async function updateSubscription() {
    const subscriptionId = document.getElementById('edit-subscription-id').value;
    const targetUrl = document.getElementById('edit-target-url').value;
    const secret = document.getElementById('edit-secret').value;
    const eventTypesInput = document.getElementById('edit-event-types').value;
    
    // Prepare update data (only include fields that are set)
    const updateData = { target_url: targetUrl };
    
    // Only include secret if it was changed (non-empty)
    if (secret) {
        updateData.secret = secret;
    }
    
    // Parse event types if provided
    if (eventTypesInput.trim()) {
        updateData.event_types = eventTypesInput.split(',').map(type => type.trim());
    } else {
        updateData.event_types = null; // Clear event types if empty
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/subscriptions/${subscriptionId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to update subscription');
        }
        
        const result = await response.json();
        showToast('Subscription updated successfully!');
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('editSubscriptionModal'));
        modal.hide();
        
        // Reload subscriptions
        loadSubscriptions();
    } catch (error) {
        console.error('Error updating subscription:', error);
        showToast('Failed to update subscription: ' + error.message, 'error');
    }
}

// Delete subscription
async function deleteSubscription(subscriptionId) {
    if (!confirm('Are you sure you want to delete this subscription? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/subscriptions/${subscriptionId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete subscription');
        }
        
        showToast('Subscription deleted successfully!');
        
        // Reload subscriptions
        loadSubscriptions();
    } catch (error) {
        console.error('Error deleting subscription:', error);
        showToast('Failed to delete subscription: ' + error.message, 'error');
    }
}

// ======== Webhook Testing ========
// Send test webhook
async function sendTestWebhook() {
    const subscriptionId = document.getElementById('subscription-select').value;
    if (!subscriptionId) {
        showToast('Please select a subscription', 'error');
        return;
    }
    
    let payload;
    try {
        payload = JSON.parse(document.getElementById('webhook-payload').value);
    } catch (error) {
        showToast('Invalid JSON payload. Please check your input.', 'error');
        return;
    }
    
    const eventType = document.getElementById('event-type-input').value;
    const headers = {};
    
    if (eventType) {
        headers['X-Event-Type'] = eventType;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/ingest/${subscriptionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...headers
            },
            body: JSON.stringify(payload)
        });
        
        const responseData = await response.json();
        const responseElement = document.getElementById('webhook-response');
        responseElement.textContent = JSON.stringify(responseData, null, 2);
        
        if (response.ok) {
            showToast('Webhook sent successfully!');
            
            // Add a button to check the delivery status
            const taskId = responseData.id;
            if (taskId) {
                const checkStatusButton = document.createElement('button');
                checkStatusButton.className = 'btn btn-info mt-3';
                checkStatusButton.innerHTML = '<i class="fas fa-sync-alt me-2"></i>Check Delivery Status';
                checkStatusButton.onclick = () => checkDeliveryStatus(taskId);
                
                // Add the button after the response display
                responseElement.parentNode.appendChild(checkStatusButton);
            }
        } else {
            showToast('Webhook failed: ' + (responseData.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error sending webhook:', error);
        showToast('Failed to send webhook: ' + error.message, 'error');
        document.getElementById('webhook-response').textContent = 'Error: ' + error.message;
    }
}

// Check delivery status by task ID
async function checkDeliveryStatus(taskId) {
    try {
        const response = await fetch(`${API_BASE_URL}/ingest/delivery/${taskId}`);
        
        if (response.ok) {
            const deliveryData = await response.json();
            
            // Display the delivery status in a modal
            const statusModalHtml = `
                <div class="modal fade" id="deliveryStatusModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Delivery Status: ${deliveryData.status}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <h6>Task Details</h6>
                                <table class="table table-bordered">
                                    <tr>
                                        <th>ID</th>
                                        <td>${deliveryData.id}</td>
                                    </tr>
                                    <tr>
                                        <th>Created At</th>
                                        <td>${formatDate(deliveryData.created_at)}</td>
                                    </tr>
                                    <tr>
                                        <th>Status</th>
                                        <td>${deliveryData.status}</td>
                                    </tr>
                                    <tr>
                                        <th>Attempt Count</th>
                                        <td>${deliveryData.attempt_count}</td>
                                    </tr>
                                    <tr>
                                        <th>Next Attempt</th>
                                        <td>${deliveryData.next_attempt_at ? formatDate(deliveryData.next_attempt_at) : 'None'}</td>
                                    </tr>
                                </table>
                                
                                <h6 class="mt-4">Delivery Logs</h6>
                                ${deliveryData.logs && deliveryData.logs.length > 0 ? `
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Attempt</th>
                                            <th>Status</th>
                                            <th>Status Code</th>
                                            <th>Details</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${deliveryData.logs.map(log => `
                                            <tr>
                                                <td>${formatDate(log.created_at)}</td>
                                                <td>${log.attempt_number}</td>
                                                <td>${log.status}</td>
                                                <td>${log.status_code || 'N/A'}</td>
                                                <td>${log.error_details || 'None'}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                                ` : '<p>No delivery logs available yet.</p>'}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-info" id="refresh-status-btn">Refresh Status</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove existing modal if any
            const existingModal = document.getElementById('deliveryStatusModal');
            if (existingModal) {
                existingModal.remove();
            }
            
            // Add the modal HTML to the page
            document.body.insertAdjacentHTML('beforeend', statusModalHtml);
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('deliveryStatusModal'));
            modal.show();
            
            // Add event listener to refresh button
            document.getElementById('refresh-status-btn').addEventListener('click', () => {
                modal.hide();
                checkDeliveryStatus(taskId);
            });
            
        } else {
            const errorData = await response.json();
            showToast('Failed to check delivery status: ' + (errorData.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error checking delivery status:', error);
        showToast('Failed to check delivery status: ' + error.message, 'error');
    }
}

// ======== Delivery Logs ========
// Load webhook delivery logs
async function loadDeliveryLogs() {
    try {
        const subscriptionId = document.getElementById('log-subscription-select').value;
        let logs = [];
        
        if (subscriptionId) {
            // If a subscription is selected, fetch logs for that subscription
            const response = await fetch(`${API_BASE_URL}/subscriptions/${subscriptionId}/deliveries`);
            if (!response.ok) throw new Error('Failed to load delivery logs');
            logs = await response.json();
        } else {
            // If no subscription is selected, we'll show no logs or fetch from subscriptions
            try {
                // Try to load all subscriptions first
                const subsResponse = await fetch(`${API_BASE_URL}/subscriptions/`);
                if (!subsResponse.ok) throw new Error('Failed to load subscriptions');
                
                const subscriptions = await subsResponse.json();
                
                // If there are subscriptions, fetch logs for the most recent ones
                if (subscriptions && subscriptions.length > 0) {
                    // Fetch logs for the first subscription (could be improved to fetch from multiple)
                    const logsResponse = await fetch(`${API_BASE_URL}/subscriptions/${subscriptions[0].id}/deliveries`);
                    if (logsResponse.ok) {
                        logs = await logsResponse.json();
                    }
                }
            } catch (subError) {
                console.error('Error loading subscriptions for logs:', subError);
            }
        }
        
        displayDeliveryLogs(logs);
    } catch (error) {
        console.error('Error loading delivery logs:', error);
        showToast('Failed to load delivery logs: ' + error.message, 'error');
    }
}

// Display delivery logs
function displayDeliveryLogs(logs) {
    const tableBody = document.getElementById('logs-table-body');
    tableBody.innerHTML = '';
    
    if (!logs || !logs.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">No delivery logs found.</td>
            </tr>
        `;
        return;
    }
    
    logs.forEach(log => {
        const statusClass = log.status === 'success' ? 'text-success' : 
                          log.status === 'failure' ? 'text-danger' : 'text-warning';
        
        const row = `
            <tr>
                <td>${formatDate(log.created_at)}</td>
                <td>${log.task_id}</td>
                <td>${log.target_url}</td>
                <td><span class="${statusClass}">${log.status}</span></td>
                <td>${log.attempt_number}</td>
                <td>${log.status_code || 'N/A'}</td>
                <td>${log.error_details || 'None'}</td>
            </tr>
        `;
        tableBody.insertAdjacentHTML('beforeend', row);
    });
}

// ======== System Health ========
// Load system health status
async function loadHealthStatus() {
    try {
        const statusResponse = await fetch(`${API_BASE_URL}/status`);
        
        if (!statusResponse.ok) {
            throw new Error(`Status endpoint returned ${statusResponse.status}`);
        }
        
        const statusData = await statusResponse.json();
        
        displayHealthStatus(statusData);
    } catch (error) {
        console.error('Error loading health status:', error);
        showToast('Failed to load health status: ' + error.message, 'error');
        
        document.getElementById('health-status-container').innerHTML = `
            <div class="alert alert-danger">
                <h5><i class="fas fa-exclamation-triangle me-2"></i>Error Loading Health Status</h5>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// Display health status
function displayHealthStatus(statusData) {
    const container = document.getElementById('health-status-container');
    
    // Overall status
    const overallStatus = statusData.status === 'healthy' ? 
        '<span class="status-healthy"><i class="fas fa-check-circle me-2"></i>Healthy</span>' :
        '<span class="status-unhealthy"><i class="fas fa-exclamation-circle me-2"></i>Degraded</span>';
    
    let html = `
        <div class="mb-4">
            <h4>Overall Status: ${overallStatus}</h4>
            <p>Service: ${statusData.service}</p>
        </div>
        
        <h5 class="mb-3">Dependencies</h5>
        <div class="row">
    `;
    
    // Database status
    const dbStatus = statusData.dependencies.database.status === 'healthy' ? 
        '<span class="status-healthy">Healthy</span>' : 
        '<span class="status-unhealthy">Unhealthy</span>';
    
    html += `
        <div class="col-md-4 mb-3">
            <div class="card h-100">
                <div class="card-header">
                    <i class="fas fa-database me-2"></i>Database
                </div>
                <div class="card-body">
                    <p>Status: ${dbStatus}</p>
                    ${statusData.dependencies.database.error ? 
                        `<p class="text-danger">Error: ${statusData.dependencies.database.error}</p>` : ''}
                </div>
            </div>
        </div>
    `;
    
    // Redis status
    const redisStatus = statusData.dependencies.redis.status === 'healthy' ? 
        '<span class="status-healthy">Healthy</span>' : 
        '<span class="status-unhealthy">Unhealthy</span>';
    
    html += `
        <div class="col-md-4 mb-3">
            <div class="card h-100">
                <div class="card-header">
                    <i class="fas fa-memory me-2"></i>Redis Cache
                </div>
                <div class="card-body">
                    <p>Status: ${redisStatus}</p>
                    ${statusData.dependencies.redis.error ? 
                        `<p class="text-danger">Error: ${statusData.dependencies.redis.error}</p>` : ''}
                </div>
            </div>
        </div>
    `;
    
    // Celery status
    const celeryStatus = statusData.dependencies.celery.status === 'healthy' ? 
        '<span class="status-healthy">Healthy</span>' : 
        '<span class="status-unhealthy">Unhealthy</span>';
    
    html += `
        <div class="col-md-4 mb-3">
            <div class="card h-100">
                <div class="card-header">
                    <i class="fas fa-tasks me-2"></i>Celery Worker
                </div>
                <div class="card-body">
                    <p>Status: ${celeryStatus}</p>
                    ${statusData.dependencies.celery.workers && statusData.dependencies.celery.workers.length ? 
                        `<p>Active Workers: ${statusData.dependencies.celery.workers.join(', ')}</p>` : ''}
                    ${statusData.dependencies.celery.error ? 
                        `<p class="text-danger">Error: ${statusData.dependencies.celery.error}</p>` : ''}
                </div>
            </div>
        </div>
    `;
    
    html += `
        </div>
    `;
    
    container.innerHTML = html;
}

// ======== Event Listeners ========
document.addEventListener('DOMContentLoaded', () => {
    // Initial data loading
    loadSubscriptions();
    
    // Tab change handlers
    document.getElementById('delivery-logs-tab').addEventListener('click', loadDeliveryLogs);
    document.getElementById('status-tab').addEventListener('click', loadHealthStatus);
    
    // Form submission handlers
    document.getElementById('save-subscription-btn').addEventListener('click', createSubscription);
    document.getElementById('update-subscription-btn').addEventListener('click', updateSubscription);
    document.getElementById('send-webhook-btn').addEventListener('click', sendTestWebhook);
    
    // Filter logs by subscription
    document.getElementById('log-subscription-select').addEventListener('change', loadDeliveryLogs);
    
    // Refresh buttons
    document.getElementById('subscriptions-tab').addEventListener('click', loadSubscriptions);
});