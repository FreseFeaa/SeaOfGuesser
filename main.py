from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import math
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345',
    'database': 'seabase'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def calculate_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)

def calculate_points(distance):
    max_points = 1000
    if distance == 0:
        return max_points
    points = max(0, max_points - int(distance * 10))
    return points

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('game'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('game'))
    
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        
        # Проверка заполнения полей
        if not login or not password:
            flash('Пожалуйста, заполните все поля', 'error')
            return render_template('auth.html')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM users WHERE login = %s AND password = %s", (login, password))
            user = cursor.fetchone()
            
            if not user:
                flash('Неверный логин или пароль', 'error')
                return render_template('auth.html')
            
            session['user_id'] = user['id']
            session['login'] = user['login']
            session['email'] = user['email']
            session['points'] = user['points']
            return redirect(url_for('game'))
        
        except Exception as e:
            flash(f'Ошибка при входе: {str(e)}', 'error')
            return render_template('auth.html')
        
        finally:
            cursor.close()
            conn.close()
    
    return render_template('auth.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('game'))
    
    if request.method == 'POST':
        login = request.form.get('login')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Проверка заполнения полей
        if not all([login, email, password, confirm_password]):
            flash('Пожалуйста, заполните все поля', 'error')
            return render_template('auth.html')
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('auth.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Проверка существующего логина
            cursor.execute("SELECT id FROM users WHERE login = %s", (login,))
            if cursor.fetchone():
                flash('Пользователь с таким логином уже существует', 'error')
                return render_template('auth.html')
            
            # Проверка существующего email
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Пользователь с таким email уже существует', 'error')
                return render_template('auth.html')
            
            # Создание нового пользователя
            cursor.execute("INSERT INTO users (login, email, password, points) VALUES (%s, %s, %s, 0)", 
                         (login, email, password))
            conn.commit()
            user_id = cursor.lastrowid
            
            session['user_id'] = user_id
            session['login'] = login
            session['email'] = email
            session['points'] = 0
            return redirect(url_for('game'))
        
        except mysql.connector.Error as err:
            flash(f'Ошибка при регистрации: {err.msg}', 'error')
            return render_template('auth.html')
        
        finally:
            cursor.close()
            conn.close()
    
    return render_template('auth.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('game'))
    
    if request.method == 'POST':
        login = request.form.get('login')
        
        if not login:
            flash('Пожалуйста, введите ваш логин', 'error')
            return render_template('auth.html')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT email FROM users WHERE login = %s", (login,))
            user = cursor.fetchone()
            
            if user:
                flash(f'Функция восстановления пароля временно недоступна. Обратитесь к администратору. (Email: {user["email"]})', 'info')
            else:
                flash('Пользователь с таким логином не найден', 'error')
            
            return render_template('auth.html')
        
        finally:
            cursor.close()
            conn.close()
    
    # GET-запрос обрабатывается в auth.html
    return redirect(url_for('login'))

@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        place_id = request.form.get('place_id')
        user_guess_x = request.form.get('lat')
        user_guess_y = request.form.get('lon')
        
        # Если координаты не выбраны
        if not user_guess_x or not user_guess_y:
            cursor.execute("SELECT id, img, x, y FROM places WHERE id = %s", (place_id,))
            place = cursor.fetchone()
            return render_template('game.html',
                                 place=place,
                                 show_results=True,
                                 distance=0,
                                 points_earned=0,
                                 user_guess_x=0,
                                 user_guess_y=0,
                                 correct_x=place['x'],
                                 correct_y=place['y'])
        
        user_guess_x = float(user_guess_x)
        user_guess_y = float(user_guess_y)
        
        cursor.execute("SELECT id, img, x, y FROM places WHERE id = %s", (place_id,))
        place = cursor.fetchone()
        
        if place:
            correct_x = place['x']
            correct_y = place['y']
            distance = calculate_distance(user_guess_x, user_guess_y, correct_x, correct_y)
            points_earned = calculate_points(distance)
            
            cursor.execute("UPDATE users SET points = points + %s WHERE id = %s", 
                         (points_earned, session['user_id']))
            conn.commit()
            session['points'] += points_earned
            
            return render_template('game.html',
                                 place=place,
                                 show_results=True,
                                 distance=distance,
                                 points_earned=points_earned,
                                 user_guess_x=user_guess_x,
                                 user_guess_y=user_guess_y,
                                 correct_x=correct_x,
                                 correct_y=correct_y)
    
    # GET-запрос
    cursor.execute("SELECT id, img FROM places ORDER BY RAND() LIMIT 1")
    place = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('game.html', place=place)

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT login, points FROM users ORDER BY points DESC LIMIT 10")
    leaders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('leaderboard.html', leaders=leaders, user=session)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)