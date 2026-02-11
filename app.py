import sqlite3
import re
import random
import string
import requests
# Если используешь AI, не забудь импортировать библиотеку (например: import google.generativeai as genai)
# и настроить API ключ.
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'nur_key_2026'
DB_NAME = 'nur_base.db'

# === ПОДКЛЮЧЕНИЕ К БАЗЕ ===
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_NAME, timeout=10)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

# === ИНИЦИАЛИЗАЦИЯ ===
def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS users (
                        email TEXT PRIMARY KEY, password TEXT NOT NULL,
                        role TEXT DEFAULT 'client', telegram_id TEXT, reset_code TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT,
                        name TEXT, contact TEXT, service TEXT, message TEXT,
                        status TEXT DEFAULT 'Новая заявка', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        db.commit()
        
        # Создаем админа, если нет
        admin_email = 'admin@nurcom.tel'
        if not db.execute('SELECT 1 FROM users WHERE email = ?', (admin_email,)).fetchone():
            hashed_pw = generate_password_hash('AdminPower2026!')
            db.execute('INSERT INTO users (email, password, role) VALUES (?, ?, ?)',
                       (admin_email, hashed_pw, 'admin'))
            print(f"✅ Админ {admin_email} создан!")

# --- НОВЫЙ МАРШРУТ: API ЧАТА ---
@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_email' not in session:
        return jsonify({'response': 'Пожалуйста, войдите в аккаунт.'}), 401
    
    data = request.get_json()
    user_msg = data.get('message')
    
    # ВАЖНО: Убедись, что переменные client и SYSTEM_PROMPT определены выше, 
    # если ты используешь Gemini API. Иначе здесь будет ошибка.
    try:
        # Пример вызова (раскомментируй и настрой, если подключен AI):
        # response = client.models.generate_content(
        #     model="gemini-1.5-flash",
        #     contents=user_msg,
        #     config={'system_instruction': SYSTEM_PROMPT}
        # )
        # return jsonify({'response': response.text})
        
        # Заглушка, пока AI не настроен:
        return jsonify({'response': 'Я пока настраиваюсь, но скоро смогу отвечать!'})
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return jsonify({'response': 'Ошибка ИИ. Попробуйте позже.'})

# --- ОСТАЛЬНЫЕ МАРШРУТЫ ---
@app.route("/")
def index():
    return render_template("index.html", is_logged_in='user_email' in session)

@app.route("/submit_request", methods=['POST'])
def submit_request():
    name = request.form.get('name')
    contact = request.form.get('contact')
    service = request.form.get('service')
    message = request.form.get('message')
    user_email = session.get('user_email', 'anonymous') 

    if name and contact:
        try:
            db = get_db()
            db.execute('INSERT INTO requests (user_email, name, contact, service, message) VALUES (?, ?, ?, ?, ?)',
                       (user_email, name, contact, service, message))
            
            # Ищем админа для уведомления
            admin = db.execute("SELECT telegram_id FROM users WHERE email = 'admin@nurcom.tel'").fetchone()
            db.commit()

            # Здесь должна быть функция отправки в TG (send_telegram_message), если она у тебя определена
            
        except Exception as e:
            print(f"❌ Ошибка при заявке: {e}")
    
    return redirect(url_for('index'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_email'], session['user_role'] = user['email'], user['role']
            return redirect(url_for('admin_panel' if user['role'] == 'admin' else 'dashboard'))
    return render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        try:
            db = get_db()
            db.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, generate_password_hash(password)))
            db.commit()
            session['user_email'] = email
            return redirect(url_for('dashboard'))
        except: return render_template("register.html", error="Email занят")
    return render_template("register.html")

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session: return redirect(url_for('login'))
    db = get_db()
    reqs = db.execute('SELECT * FROM requests WHERE user_email = ?', (session['user_email'],)).fetchall()
    return render_template('dashboard.html', requests=reqs, user=session['user_email'])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

# === АДМИНКА ===
@app.route("/admin")
def admin_panel():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    
    db = get_db()
    requests_list = db.execute('SELECT * FROM requests ORDER BY id DESC').fetchall()
    users_list = db.execute("SELECT email, role FROM users WHERE email != 'admin@nurcom.tel'").fetchall()
    
    return render_template("admin.html", requests=requests_list, users=users_list)

@app.route("/admin/reset_user/<email>", methods=['POST'])
def admin_reset_user(email):
    if session.get('user_role') != 'admin': 
        return redirect(url_for('login'))
    
    default_pw = "12345678" 
    hashed_pw = generate_password_hash(default_pw)
    
    db = get_db()
    db.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_pw, email))
    db.commit()
    
    print(f"✅ Пароль для {email} сброшен на {default_pw}")
    return redirect(url_for('admin_panel'))

@app.route("/admin/update_status/<int:req_id>", methods=['POST'])
def update_status(req_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    
    new_status = request.form.get('status')
    db = get_db()
    db.execute('UPDATE requests SET status = ? WHERE id = ?', (new_status, req_id))
    db.commit()
    return redirect(url_for('admin_panel'))

# === ВОССТАНОВЛЕНИЕ И ПРОФИЛЬ ===

@app.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        db = get_db()
        user = db.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
        
        if user:
            db.execute('INSERT INTO requests (user_email, name, contact, service, message) VALUES (?, ?, ?, ?, ?)',
                       (email, "🔑 СБРОС ПАРОЛЯ", email, "Техподдержка", f"Запрос на сброс пароля для {email}"))
            db.commit()
            return render_template("forgot_password.html", success="Запрос отправлен! Админ скоро сбросит ваш пароль.")
        
        return render_template("forgot_password.html", error="Email не найден")
    
    return render_template("forgot_password.html")

@app.route('/profile')
def profile():
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    msg = request.args.get('msg')
    return render_template('profile.html', user=session['user_email'], msg=msg)

@app.route("/update_password", methods=['POST'])
def update_password():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')
    email = session['user_email']

    if new_pw != confirm_pw:
        return render_template('profile.html', user=email, msg="❌ Пароли не совпадают!")

    db = get_db()
    user = db.execute('SELECT password FROM users WHERE email = ?', (email,)).fetchone()

    if user and check_password_hash(user['password'], current_pw):
        hashed_new = generate_password_hash(new_pw)
        db.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_new, email))
        db.commit()
        return redirect(url_for('profile', msg="✅ Пароль успешно изменен!"))
    else:
        return render_template('profile.html', user=email, msg="❌ Неверный текущий пароль!")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)