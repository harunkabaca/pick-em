from flask import Flask, request, jsonify, redirect, url_for, render_template, session, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psycopg2, bcrypt, json

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_strong_secret_key'
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")


# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "prediction_game",
    "user": "haruka",
    "password": "haruka"
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
def get_user_from_db(user_id):
    # Fetch user data from the database based on user_id
    # ... (Database query logic goes here) ...
    user_data = {
        'username': 'JohnDoe', 
        'profile_picture': '/static/default_profile.jpg' 
    }  # Replace with actual data from the database
    return user_data


# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        user_id = session['user_id']
        current_user = get_user_from_db(user_id) 
        return render_template('index.html', current_user=current_user)
    else:
        return redirect(url_for('login'))

    
@app.route('/register')
def register_page():
    return render_template('register.html') 

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, password, points, is_streamer
                    FROM users WHERE username = %s
                """, (username,))
                user = cur.fetchone()

                if user and bcrypt.checkpw(password, user[1].strip().encode('utf-8')):
                    session['user_id'] = user[0]
                    session['points'] = user[2]
                    session['is_streamer'] = user[3]
                    return redirect(url_for('index'))
                else:
                    error = 'Invalid credentials'

    return render_template('login.html', error=error)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
                
                cur.execute("""
                    INSERT INTO users (username, password)
                    VALUES (%s, %s) RETURNING id
                """, (data['username'], hashed_password.decode('utf-8')))
                user_id = cur.fetchone()[0]
                conn.commit()
                session['user_id'] = user_id
                return jsonify({"message": "Registration successful"})
            except psycopg2.IntegrityError:
                conn.rollback()
                return jsonify({"error": "Username already exists"}), 400
  
@app.route('/api/check_session')
def check_session():
    if 'user_id' in session:
        return jsonify({
            "user_id": session['user_id'],
            "points": session.get('points', 0),
            "is_streamer": session.get('is_streamer', False)
        })
    return jsonify({"error": "Not logged in"}), 401

@app.route('/api/predictions', methods=['GET', 'POST'])
def predictions():
    if request.method == 'GET':
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.id, p.event_name, p.options, p.created_at, p.status,
                           COALESCE(v.votes, '{}'::json) as votes
                    FROM predictions p
                    LEFT JOIN (
                        SELECT prediction_id, json_object_agg(selected_option, cnt) as votes
                        FROM (
                            SELECT prediction_id, selected_option, COUNT(*) as cnt
                            FROM user_predictions
                            GROUP BY prediction_id, selected_option
                        ) sub
                        GROUP BY prediction_id
                    ) v ON p.id = v.prediction_id
                    WHERE p.status = 'aktif'
                """)
                return jsonify([
                    dict(zip(['id', 'event', 'options', 'created', 'status'], row))
                    for row in cur.fetchall()
                ])

    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check for duplicate vote
            cur.execute("""
                SELECT 1 FROM user_predictions 
                WHERE user_id = %s AND prediction_id = %s
            """, (session['user_id'], data['prediction_id']))
            
            if cur.fetchone():
                return jsonify({"error": "You have already voted for this prediction."}), 400

            # Insert new vote
            cur.execute("""
                INSERT INTO user_predictions 
                (user_id, prediction_id, selected_option)
                VALUES (%s, %s, %s)
            """, (session['user_id'], data['prediction_id'], data['selected_option']))
            conn.commit()

            # Fetch updated votes
            cur.execute("""
                SELECT selected_option, COUNT(*) 
                FROM user_predictions 
                WHERE prediction_id = %s 
                GROUP BY selected_option
            """, (data['prediction_id'],))
            votes = {k: v for k, v in cur.fetchall()}
            socketio.emit('vote_update', {
                'prediction_id': data['prediction_id'],
                'votes': votes
            })
            return jsonify({"message": "Prediction saved"})

@app.route('/api/store/<int:streamer_id>', methods=['GET'])
def get_store(streamer_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, item_name, description, price 
                FROM store_items WHERE streamer_id = %s
            """, (streamer_id,))
            return jsonify([
                dict(zip(['id', 'name', 'description', 'price'], row))
                for row in cur.fetchall()
            ])

@app.route('/api/store/purchase', methods=['POST'])
def purchase():
    if 'user_id' not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT price, streamer_id 
                FROM store_items WHERE id = %s
            """, (data['item_id'],))
            item = cur.fetchone()

            if not item or session['points'] < item[0]:
                item = cur.fetchone()

            if not item or session['points'] < item[0]:
                return jsonify({"error": "Invalid purchase"}), 400

            # Process transaction
            cur.execute("""
                BEGIN;
                UPDATE users SET points = points - %s WHERE id = %s;
                INSERT INTO purchases (user_id, item_id, streamer_id)
                VALUES (%s, %s, %s);
                COMMIT;
            """, (item[0], session['user_id'], 
                   session['user_id'], data['item_id'], item[1]))

            session['points'] -= item[0]
            socketio.emit('points_update', {
                'user_id': session['user_id'],
                'new_balance': session['points']
            })
            return jsonify({"new_balance": session['points']})

@app.route('/api/admin/questions', methods=['POST'])
def add_question():
    if not session.get('is_streamer'):
        return jsonify({"error": "Streamer access required"}), 403

    data = request.get_json()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO questions 
                (question_text, option_a, option_b, option_c, option_d)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                data['text'],
                data['options']['A'],
                data['options']['B'],
                data['options'].get('C'),
                data['options'].get('D')
            ))
            conn.commit()
            socketio.emit('new_question', broadcast=True)
            return jsonify({"message": "Question added"})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# WebSocket Handlers
@socketio.on('connect')
def handle_connect():
    emit('connection_status', {'status': 'connected'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)