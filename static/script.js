$(document).ready(function() {
  const socket = io('http://localhost:5000', { transports: ['websocket'] });

  socket.on('connect', () => {
      console.log('Bağlantı kuruldu');
  });

  function loadPredictions() {
      $.ajax({
          url: '/api/predictions',
          type: 'GET',
          dataType: 'json',
          success: function(data) {
              console.log("API'den dönen veri:", data);

              if (!data || data.length === 0) {
                  $("#predictions-container").html("<p>Henüz tahmin yok.</p>");
                  return;
              }

              $("#predictions-container").empty();

              data.forEach(function(prediction) {
                  let predictionHtml = `
                      <div class="prediction">
                          <h2>${prediction.event_name}</h2>
                          <div class="options">
                  `;

                  let totalVotes = Object.values(prediction.options).reduce((acc, val) => acc + val, 0);

                  for (const option in prediction.options) {
                      let votes = prediction.options[option] || 0;
                      let percentage = totalVotes > 0 ? ((votes / totalVotes) * 100).toFixed(1) : 0;

                      predictionHtml += `
                          <div class="option">
                              <input type="radio" name="prediction-${prediction.id}" value="${option}" id="option-${prediction.id}-${option}">
                              <label for="option-${prediction.id}-${option}">${option}</label>
                              <span class="vote-count" id="vote-count-${prediction.id}-${option}">${votes} oy (%${percentage})</span>
                          </div>
                      `;
                  }

                  predictionHtml += `
                          </div>
                          <button class="submit-prediction" data-prediction-id="${prediction.id}">Tahmin Yap</button>
                      </div>
                  `;

                  $('#predictions-container').append(predictionHtml);
              });
          },
          error: function(error) {
              console.error("API hatası:", error);
              $("#predictions-container").html("<p>API hatası oluştu.</p>");
          }
      });
  }

  loadPredictions();

  $(document).on('click', '.submit-prediction', function() {
      const predictionId = $(this).data('prediction-id');
      const selectedOption = $(`input[name="prediction-${predictionId}"]:checked`).val();

      if (!selectedOption) {
          alert("Lütfen bir seçenek belirleyin.");
          return;
      }

      let userId = getUserId();

      $.ajax({
          url: '/api/predictions',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({
              user_id: userId,
              prediction_id: predictionId,
              selected_option: selectedOption
          }),
          dataType: 'json',
          success: function(data) {
              showNotification("Tahmininiz başarıyla kaydedildi!");
              loadPredictions();
          },
          error: function(error) {
              console.error("Tahmin gönderme hatası:", error);
              if (error.responseJSON && error.responseJSON.message) {
                  alert("Hata: " + error.responseJSON.message);
              } else if (error.status) {
                  alert("Hata Kodu: " + error.status);
              } else {
                  alert("Bir hata oluştu. Lütfen tekrar deneyin.");
              }
          }
      });
  });

  $(document).on('change', 'input[type="radio"]', function() {
      let predictionId = $(this).attr('name');
      $(`input[name="${predictionId}"] + label`).css({
          "background-color": "#3b3b5b",
          "color": "white",
          "font-weight": "normal"
      });

      $(this).next("label").css({
          "background-color": "#ff4d4d",
          "color": "white",
          "font-weight": "bold"
      });
  });

  socket.on('vote_update', function(data) {
      console.log('Güncellenmiş oylar:', data);
      let totalVotes = Object.values(data.options).reduce((acc, val) => acc + val, 0);

      for (const option in data.options) {
          let votes = data.options[option] || 0;
          let percentage = totalVotes > 0 ? ((votes / totalVotes) * 100).toFixed(1) : 0;

          $(`#vote-count-${data.prediction_id}-${option}`).text(`${votes} oy (%${percentage})`);
      }
  });

  function getUserId() {
      return localStorage.getItem("user_id") || 1;
  }

  // Bildirim gösterme fonksiyonu
  function showNotification(message) {
      let notificationHtml = `
          <div id="notification" style="position: fixed; bottom: 20px; right: 20px; background-color: #3b3b5b; color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.5);">
              <span>${message}</span>
              <button id="close-notification" style="background: none; border: none; color: white; font-weight: bold; margin-left: 10px; cursor: pointer;">×</button>
          </div>
      `;

      $('body').append(notificationHtml);

      $('#close-notification').on('click', function() {
          $('#notification').remove();
      });

      setTimeout(() => {
          $('#notification').fadeOut(300, function() {
              $(this).remove();
          });
      }, 5000); // 5 saniye sonra otomatik kapanır
  }
});
