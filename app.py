from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psycopg2

app = Flask(__name__, static_folder='static')
cors = CORS(app, resources={r"/api/*": {"origins": "http://localhost:5000"}})
socketio = SocketIO(app, cors_allowed_origins="*")


# Veritabanı bağlantı bilgileri
DB_HOST = "localhost"
DB_NAME = "prediction_game"
DB_USER = "haruka"
DB_PASSWORD = "haruka"

# Veritabanı bağlantısı
def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        return conn
    except Exception as e:
        print(f"Veritabanı bağlantı hatası: {e}")
        return None  # Bağlantı kurulamadıysa None döndür

#database connection test
try:
    conn = get_db_connection()
    if conn:
        print("Veritabanı bağlantısı başarılı!")
        conn.close()
except Exception as e:
    print(f"Veritabanı bağlantı hatası: {e}")


# Model: Prediction
class Prediction:
    def __init__(self, id, event_name, options, created_at, status):
        self.id = id
        self.event_name = event_name
        self.options = options
        self.created_at = created_at
        self.status = status
def __repr__(self):
    return f"<Prediction {self.id}>"
# Model: User
class User:
    def __init__(self, id, username, twitch_id):
        self.id = id
        self.username = username
        self.twitch_id = twitch_id

# Model: UserPrediction
class UserPrediction:
    def __init__(self, id, user_id, prediction_id, selected_option, created_at):
        self.id = id
        self.user_id = user_id
        self.prediction_id = prediction_id
        self.selected_option = selected_option
        self.created_at = created_at

@app.route('/')
def index():
    return render_template('index.html')

# Tahminleri getirme
@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Tahminleri çekiyoruz
        cur.execute("SELECT id, event_name, options, created_at, status FROM predictions WHERE status = 'aktif'")
        prediction_rows = cur.fetchall()

        predictions = []
        for row in prediction_rows:
            prediction_id, event_name, options, created_at, status = row

            # Oyları çekiyoruz
            cur.execute("SELECT selected_option, COUNT(*) FROM user_predictions WHERE prediction_id = %s GROUP BY selected_option", (prediction_id,))
            votes = cur.fetchall()

            # Seçeneklere göre oy sayısını oluşturuyoruz
            option_votes = {option: 0 for option in options}  # Tüm seçenekler sıfır oyla başlıyor
            for selected_option, count in votes:
                option_votes[selected_option] = count

            # Prediction objesini oluşturup ekliyoruz
            prediction = {
                'id': prediction_id,
                'event_name': event_name,
                'options': option_votes,
                'created_at': created_at,
                'status': status
            }
            predictions.append(prediction)

        cur.close()
        conn.close()
        return jsonify(predictions)
    
    except Exception as e:
        print(f"API Endpoint'inde Hata: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Kullanıcı tahminini kaydetme
@app.route('/api/predictions', methods=['POST'])
def create_prediction():
    data = request.get_json()
    user_id = data['user_id']
    prediction_id = data['prediction_id']
    selected_option = data['selected_option']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO user_predictions (user_id, prediction_id, selected_option) VALUES (%s, %s, %s)", (user_id, prediction_id, selected_option))
    conn.commit()

    # Güncel oyları çekip WebSocket üzerinden yayınla
    cur.execute("SELECT selected_option, COUNT(*) FROM user_predictions WHERE prediction_id = %s GROUP BY selected_option", (prediction_id,))
    votes = cur.fetchall()

    # Seçeneklere göre oy sayısı oluştur
    option_votes = {option: 0 for option in ['A', 'B', 'C', 'D']}  # Mevcut seçenekleri buraya koy
    for selected_option, count in votes:
        option_votes[selected_option] = count

    # WebSocket yayını
    socketio.emit('vote_update', {'prediction_id': prediction_id, 'options': option_votes})

    cur.close()
    conn.close()
    return jsonify({"message": "Tahmin kaydedildi"})


@socketio.on('connect')
def handle_connect():
    print('Bir kullanıcı bağlandı')

@socketio.on('new_prediction', namespace='/predictions')
def handle_new_prediction(data):
    # Yeni bir tahmin oluşturulduğunda diğer kullanıcılara bildir
    emit('new_prediction', data, broadcast=True)

@socketio.on('prediction_result', namespace='/predictions')
def handle_prediction_result(data):
    # Tahmin sonucu açıklandığında diğer kullanıcılara bildir
    emit('prediction_result', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)
    