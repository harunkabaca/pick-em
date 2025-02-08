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
        'username': 'haruka', 
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
                    SELECT id, password, points, is_streamer, is_admin
                    FROM users WHERE username = %s
                """, (username,))
                user = cur.fetchone()

                if user and bcrypt.checkpw(password, user[1].strip().encode('utf-8')):
                    session['user_id'] = user[0]
                    session['points'] = user[2]
                    session['is_streamer'] = user[3]
                    session['is_admin'] = user[4]  # Admin bilgisi ekledik
                    # Admin kontrolü
                    if user[4]:
                        return redirect(url_for('admin_panel'))  # Admin ise admin paneline yönlendir
                    else:
                        return redirect(url_for('index'))  # Normal kullanıcı ise index sayfasına yönlendir
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

# Admin authentication decorator
def admin_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
                is_admin = cur.fetchone()
                
                if not is_admin or not is_admin[0]:
                    return jsonify({"error": "Admin authentication required"}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Admin login
@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password').encode('utf-8')  # Girilen şifreyi encode ettik
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, password, is_admin FROM users WHERE username = %s
            """, (username,))
            user = cur.fetchone()
            
            if user:
                stored_password = user[1].encode('utf-8')  # Veritabanındaki hashlenmiş şifreyi aldık
                if bcrypt.checkpw(password, stored_password) and user[2]:  # Şifre doğrulama ve admin kontrolü
                    session['user_id'] = user[0]
                    return redirect(url_for('admin_panel'))
            
            return jsonify({"error": "Invalid credentials or not an admin"}), 401

# Admin panel page
@app.route('/admin')
@admin_required
def admin_panel():
    if 'is_admin' in session and session['is_admin']:
        current_user = get_user_from_db(session['user_id'])
        return render_template('admin_panel.html', current_user = current_user) 
    else:
        return jsonify({"error": "Admin authentication required"}), 403 

def admin_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
                is_admin = cur.fetchone()

                if not is_admin or not is_admin[0]:
                    return jsonify({"error": "Admin authentication required"}), 403

        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Add a new prediction
@app.route('/admin/predictions', methods=['POST'])
@admin_required
def add_prediction():
    data = request.get_json()
    event_name = data['event_name']
    options = data['options']
    options_json = json.dumps(options)

    if len(options) < 2 or len(options) > 6:
        return jsonify({"error": "Options must be between 2 and 6."}), 400
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO predictions (event_name, options, status)
                VALUES (%s, %s, 'aktif')
            """, (event_name, options_json))
            
            conn.commit()
            
            # Notify users about the new prediction
            socketio.emit('new_prediction', {
                'event_name': event_name,
                'options': options
            })
            
            return jsonify({"message": "Prediction added successfully"})

# Update a prediction's answer and distribute points
@app.route('/admin/predictions/<int:prediction_id>/answer', methods=['POST'])
@admin_required
def update_prediction_answer(prediction_id):
    data = request.get_json()
    correct_option = data['correct_option']
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Update prediction status and correct answer
            cur.execute("""
                UPDATE predictions
                SET status = 'closed', correct_option = %s
                WHERE id = %s
            """, (correct_option, prediction_id))
            
            # Update user scores based on correct answer
            cur.execute("""
                UPDATE users
                SET score = score + 10
                WHERE id IN (
                    SELECT user_id FROM user_predictions
                    WHERE prediction_id = %s AND selected_option = %s
                )
            """, (prediction_id, correct_option))
            
            conn.commit()
            
            # Notify users about the result
            socketio.emit('result_update', {
                'prediction_id': prediction_id,
                'correct_option': correct_option
            })
            
            return jsonify({"message": "Answer updated and points distributed"})

# Get all predictions for admin view
@app.route('/admin/predictions', methods=['GET'])
@admin_required
def get_all_predictions():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, event_name, options, created_at, status, correct_option
                FROM predictions
            """)
            predictions = cur.fetchall()
            
            return jsonify([
                dict(zip(['id', 'event_name', 'options', 'created_at', 'status', 'correct_option'], row))
                for row in predictions
            ])

# Update user roles
@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def update_user_role(user_id):
    data = request.get_json()
    is_broadcaster = data.get('is_broadcaster')
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET is_broadcaster = %s WHERE id = %s
            """, (is_broadcaster, user_id))
            conn.commit()
            
            return jsonify({"message": "User role updated successfully"})



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

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# WebSocket Handlers
@socketio.on('connect')
def handle_connect():
    emit('connection_status', {'status': 'connected'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)