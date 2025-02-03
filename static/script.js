const socket = io('http://127.0.0.1:5000/');
let currentUser = null;

// Initialize App
$(document).ready(() => {
    checkSession();
    loadPredictions();
    loadStoreItems(1); // Load store for kick.com/naru (streamer_id=1)
});

// Authentication
function checkSession() {
    fetch('/api/check_session')
        .then(r => r.json())
        .then(data => currentUser = data)
        .catch(() => window.location = '/login');
}

// Prediction System
function loadPredictions() {
    fetch('/api/predictions')
        .then(r => r.json())
        .then(predictions => {
            $('#predictions-container').html(
                predictions.map(pred => `
                    <div class="prediction" data-id="${pred.id}">
                        <h3>${pred.event}</h3>
                        <div class="options">
                            ${Object.entries(pred.options).map(([opt, val]) => `
                                <div class="option">
                                    <input type="radio" name="pred-${pred.id}" 
                                           id="opt-${pred.id}-${opt}" value="${opt}">
                                    <label for="opt-${pred.id}-${opt}">
                                        ${opt}: ${val}%
                                    </label>
                                </div>
                            `).join('')}
                        </div>
                        <button onclick="submitPrediction(${pred.id})">Submit</button>
                    </div>
                `).join('')
            );
        });
}

function submitPrediction(predId) {
    const selected = $(`input[name="pred-${predId}"]:checked`).val();
    fetch('/api/predictions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            prediction_id: predId,
            selected_option: selected
        })
    }).then(loadPredictions);
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

// Real-Time Updates
socket.on('vote_update', data => {
    const pred = $(`.prediction[data-id="${data.prediction_id}"]`);
    Object.entries(data.votes).forEach(([opt, votes]) => {
        pred.find(`#opt-${data.prediction_id}-${opt} + label`)
            .text(`${opt}: ${((votes/total)*100).toFixed(1)}%`);
    });
});

socket.on('points_update', data => {
    if(data.user_id === currentUser.id) {
        currentUser.points = data.new_balance;
        updatePointsDisplay();
    }
});

function updatePointsDisplay() {
    $('#points-display').text(`Points: ${currentUser.points}`);
}