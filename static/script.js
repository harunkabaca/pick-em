const socket = io('http://localhost:5000', { transports: ['websocket'] });

$(document).ready(() => {
    checkSession();
    loadPredictions();
    loadStoreItems(1); // Load store for kick.com/naru (streamer_id=1)
    
    socket.on('connect', () => {
        console.log('Socket bağlantısı kuruldu.');
    });

    socket.on('vote_update', (data) => updateVotes(data));
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
                                <div class="option" data-prediction-id="${pred.id}" data-option="${opt}">
                                    <input type="radio" name="pred-${pred.id}" id="opt-${pred.id}-${opt}" value="${opt}">
                                    <label for="opt-${pred.id}-${opt}">${opt}: <span class="vote-count">${val}</span></label>
                                    <div class="progress-bar-container">
                                        <div class="progress-bar" id="progress-${pred.id}-${opt}" style="width: ${val}%"></div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                        <button onclick="submitPrediction(${pred.id})" class="submit-prediction">Submit</button>
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
    }).then(response => response.json())
    .then(data => {
        if (data.error) {
            showToast(data.error);  // Zaten oy verildiyse hata mesajını göster
        } else {
            showToast("Prediction submitted successfully!");
        }
    })
    .catch(err => console.error('Error submitting prediction:', err));
}

// Update Votes (Socket)
function updateVotes(data) {
    const predictionId = data.prediction_id;
    const votes = data.votes;

    console.log('Gelen oy verileri:', votes);  // Debug için verileri konsola yazdır

    let totalVotes = Object.values(votes).reduce((acc, val) => acc + val, 0);

    for (const [option, count] of Object.entries(votes)) {
        const optionElement = $(`.option[data-prediction-id="${predictionId}"][data-option="${option}"]`);
        if (optionElement.length) {
            const percentage = totalVotes > 0 ? ((count / totalVotes) * 100).toFixed(1) : 0;
            optionElement.find('.vote-count').text(`${count} votes (${percentage}%)`);
            optionElement.find('.progress-bar').css('width', `${percentage}%`);
        }
    }
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
    $('#toast-message').text(message);
    toast.addClass('show');
    setTimeout(() => toast.removeClass('show'), 3000); 
}

// Update Points Display
function updatePointsDisplay() {
    $('#points-display').text(`Points: ${currentUser.points}`);
}
