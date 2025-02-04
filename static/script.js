const socket = io('http://127.0.0.1:5000/'); 

let currentUser = null;

// Initialize App
$(document).ready(() => {
    checkSession();
    loadPredictions();
    loadStoreItems(1); // Load store for kick.com/naru (streamer_id=1)
});

// Authentication check
function checkSession() {
    fetch('/api/check_session')
        .then(r => r.json())
        .then(data => currentUser = data)
        .catch(() => window.location = '/login');
}

// Load Predictions
function loadPredictions() {
    fetch('/api/predictions')
        .then(r => r.json())
        .then(predictions => {
            $('#predictions-container').html(
                predictions.map(pred => `
                    <div class="prediction-card" data-id="${pred.id}">
                        <h3>${pred.event}</h3>
                        <div class="options">
                            ${Object.entries(pred.options).map(([opt, val]) => `
                                <div class="option">
                                    <input type="radio" name="pred-${pred.id}" id="opt-${pred.id}-${opt}" value="${opt}">
                                    <label for="opt-${pred.id}-${opt}">${opt}: ${val}%</label>
                                </div>
                            `).join('')}
                        </div>
                        <button onclick="submitPrediction(${pred.id})">Submit</button>
                    </div>
                `).join('')
            );
        });
}

// Submit Prediction
function submitPrediction(predId) {
    const selected = $(`input[name="pred-${predId}"]:checked`).val();
    if (!selected) {
        alert('Please select an option!');
        return;
    }

    fetch('/api/predictions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            prediction_id: predId,
            selected_option: selected
        })
    }).then(() => {
        loadPredictions();  // Reload predictions
        showToast("Prediction submitted successfully!");
    }).catch(err => console.error('Error submitting prediction:', err));
}

// Store System
function loadStoreItems(streamerId) {
    fetch(`/api/store/${streamerId}`)
        .then(r => r.json())
        .then(items => {
            $('#store-container').html(
                items.map(item => `
                    <div class="store-item">
                        <h4>${item.name}</h4>
                        <p>${item.description}</p>
                        <p class="price">${item.price} Points</p>
                        <button onclick="purchaseItem(${item.id})">Buy</button>
                    </div>
                `).join('')
            );
        });
}

// Purchase Item
function purchaseItem(itemId) {
    fetch('/api/store/purchase', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ item_id: itemId })
    }).then(r => r.json())
        .then(data => {
            currentUser.points = data.new_balance;
            updatePointsDisplay();
        });
}

// Show Toast (notification)
function showToast(message) {
    const toast = $('#toast');
    const toastMessage = $('#toast-message');
    toastMessage.text(message);
    toast.addClass('show');
    setTimeout(() => toast.removeClass('show'), 3000); // Hide toast after 3 seconds
}

// Real-Time Updates (via WebSocket)
socket.on('vote_update', data => {
    console.log('Vote update received:', data);

    const pred = $(`.prediction-card[data-id="${data.prediction_id}"]`); // Find the correct prediction card

    const totalVotes = Object.values(data.votes).reduce((acc, val) => acc + val, 0);

    Object.entries(data.votes).forEach(([opt, votes]) => {
        const percentage = (votes / totalVotes * 100).toFixed(1); // Calculate percentage of votes

        pred.find(`#opt-${data.prediction_id}-${opt} + label`)
            .text(`${opt}: ${votes} votes (${percentage}%)`);

        pred.find(`#opt-${data.prediction_id}-${opt} + .vote-count`)
            .text(`Votes: ${votes}`);
    });
});

// Update Points Display
function updatePointsDisplay() {
    $('#points-display').text(`Points: ${currentUser.points}`);
}
