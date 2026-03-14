from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime, date, timedelta
from google import genai
from dotenv import load_dotenv


# Load environment variables from a .env file (optional; requires python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Load environment variables from a .env file
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Configure Gemini
DB_PATH = os.path.join(os.path.dirname(__file__), 'studycoach.db')

SUBJECTS = [
    'DBMS', 'Operating Systems', 'Computer Networks', 'Data Structures',
    'Algorithms', 'Software Engineering', 'Artificial Intelligence',
    'Machine Learning', 'Computer Architecture', 'Web Development',
    'Cyber Security', 'Mathematics', 'Physics'
]

SUBJECT_TOPICS = {
    'DBMS': ['Normalization', 'SQL Queries', 'Transactions & Concurrency', 'Relational Algebra', 'Indexing'],
    'Operating Systems': ['Process Management', 'Memory Management', 'File Systems', 'Deadlocks', 'Threads'],
    'Computer Networks': ['OSI Model', 'TCP/IP', 'Routing Algorithms', 'Network Security', 'Application Protocols'],
    'Data Structures': ['Arrays & Linked Lists', 'Stacks & Queues', 'Trees & Graphs', 'Hashing', 'Heaps'],
    'Algorithms': ['Sorting & Searching', 'Dynamic Programming', 'Greedy Algorithms', 'Graph Algorithms', 'Divide and Conquer'],
    'Software Engineering': ['SDLC', 'Agile Methodologies', 'Software Testing', 'Design Patterns', 'Requirements'],
    'Artificial Intelligence': ['Search Algorithms', 'Knowledge Representation', 'Machine Reasoning', 'Fuzzy Logic', 'NLP Basics'],
    'Machine Learning': ['Supervised Learning', 'Unsupervised Learning', 'Neural Networks', 'Model Evaluation', 'SVM'],
    'Computer Architecture': ['Instruction Set', 'Pipelining', 'Memory Hierarchy', 'I/O Organization', 'Multiprocessors'],
    'Web Development': ['HTML & CSS', 'JavaScript & DOM', 'React Frontend', 'Node.js Backend', 'REST APIs'],
    'Cyber Security': ['Cryptography', 'Network Security', 'Ethical Hacking', 'Malware Analysis', 'Web App Security'],
    'Mathematics': ['Linear Algebra', 'Calculus', 'Probability & Statistics', 'Discrete Math', 'Differential Equations'],
    'Physics': ['Mechanics', 'Thermodynamics', 'Electromagnetism', 'Quantum Physics', 'Optics']
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT,
            school TEXT,
            department TEXT,
            subjects TEXT,
            daily_goal INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            topic TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            is_enabled INTEGER DEFAULT 1,
            last_sent TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit(); conn.close()


@app.before_request
def setup():
    if not os.path.exists(DB_PATH):
        init_db()


def current_user():
    if 'user_id' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return user
    return None


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)

    return wrapper


@app.route('/')
def home():
    if current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        phone = request.form.get('phone').strip()
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('signup.html')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, phone) VALUES (?, ?, ?)',
                         (username, password, phone))
            conn.commit()
            flash('Signup successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            flash('Login successful.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    if request.method == 'POST':
        full_name = request.form.get('full_name').strip()
        school = request.form.get('school').strip()
        department = request.form.get('department').strip()
        subjects = ','.join(request.form.getlist('subjects'))
        daily_goal = int(request.form.get('daily_goal') or 60)
        if profile:
            conn.execute('''UPDATE student_profile SET full_name=?, school=?, department=?, subjects=?, daily_goal=? WHERE user_id = ?''',
                         (full_name, school, department, subjects, daily_goal, user['id']))
        else:
            conn.execute('''INSERT INTO student_profile (user_id, full_name, school, department, subjects, daily_goal) VALUES (?, ?, ?, ?, ?, ?)''',
                         (user['id'], full_name, school, department, subjects, daily_goal))
        conn.commit()
        conn.close()
        flash('Profile saved.', 'success')
        return redirect(url_for('dashboard'))
    conn.close()
    return render_template('profile.html', user=user, profile=profile, subjects=SUBJECTS)


def get_today_logs(uid):
    today = datetime.now().date().isoformat()
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM study_logs WHERE user_id = ? AND DATE(created_at)=?', (uid, today)).fetchall()
    conn.close()
    return logs


def calculate_streak(uid):
    conn = get_db_connection()
    rows = conn.execute('SELECT DISTINCT DATE(created_at) as d, SUM(minutes) as total FROM study_logs WHERE user_id = ? GROUP BY d ORDER BY d DESC LIMIT 30', (uid,)).fetchall()
    conn.close()
    if not rows:
        return 0
    streak = 0
    current = date.today()
    for row in rows:
        row_date = datetime.strptime(row['d'], '%Y-%m-%d').date()
        if row_date == current and row['total'] >= 60:
            streak += 1
            current -= timedelta(days=1)
        elif row_date == current - timedelta(days=1) and row['total'] >= 60:
            streak += 1
            current -= timedelta(days=1)
        elif row_date < current - timedelta(days=1):
            break
    return streak


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    study_logs = conn.execute('SELECT * FROM study_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user['id'],)).fetchall()
    conn.close()

    today_logs = get_today_logs(user['id'])
    total_today = sum([row['minutes'] for row in today_logs])
    total_all = sum([row['minutes'] for row in study_logs])
    streak = calculate_streak(user['id'])

    return render_template('dashboard.html', user=user, profile=profile,
                           today_logs=today_logs, total_today=total_today,
                           total_all=total_all, streak=streak,
                           subjects=SUBJECTS, subject_topics=SUBJECT_TOPICS)


@app.route('/add_study', methods=['POST'])
@login_required
def add_study():
    user = current_user()
    subject = request.form.get('subject')
    minutes = int(request.form.get('minutes') or 0)
    topic = request.form.get('topic') or ''
    if not subject or minutes <= 0:
        flash('Please provide subject and positive minutes.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    conn.execute('INSERT INTO study_logs (user_id, subject, minutes, topic, created_at) VALUES (?, ?, ?, ?, ?)',
                 (user['id'], subject, minutes, topic, datetime.now().isoformat()))
    conn.commit(); conn.close()
    flash('Study record added.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_log/<int:log_id>')
@login_required
def delete_log(log_id):
    user = current_user()
    conn = get_db_connection()
    conn.execute('DELETE FROM study_logs WHERE id = ? AND user_id = ?', (log_id, user['id']))
    conn.commit(); conn.close()
    flash('Record deleted.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/subject_planner', methods=['GET', 'POST'])
@login_required
def subject_planner():
    user = current_user()
    profile = None
    conn = get_db_connection()
    if request.method == 'POST':
        mandatory = request.form.get('mandatory_subject')
        extra = request.form.getlist('extra_subjects')
        msg = 'Today mandatory: %s' % mandatory
        if extra:
            msg += ', extra: %s' % ', '.join(extra)
        flash(msg, 'info')
        # save to reminders table as plan placeholder
        conn.execute('INSERT INTO reminders (user_id, subject, topic, is_enabled, last_sent) VALUES (?, ?, ?, 1, ?)',
                     (user['id'], mandatory, ','.join(extra), datetime.now().isoformat()))
        conn.commit()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()
    return render_template('plan_subjects.html', subjects=SUBJECTS, profile=profile)


def call_gemini(prompt_text):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key_here':
        return 'Gemini API key not set or invalid in .env file.'

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_text
        )
        return response.text.strip()
    except Exception as err:
        return f"Gemini request failed: {err}"


@app.route('/topic_generator', methods=['GET', 'POST'])
@login_required
def topic_generator():
    generated = None
    selected_subject = None
    if request.method == 'POST':
        selected_subject = request.form.get('subject')
        if not selected_subject:
            flash('Select a subject first.', 'danger')
            return redirect(url_for('topic_generator'))
        prompt = f"Generate 5 concise study topic suggestions for the subject {selected_subject}. Return only the list of topics, one per line."
        generated = call_gemini(prompt)
    return render_template('topic_generator.html', subjects=SUBJECTS, generated=generated, selected_subject=selected_subject)


@app.route('/ai_notes', methods=['POST'])
@login_required
def ai_notes():
    topic = request.form.get('topic')
    if not topic:
        flash('Select a topic first.', 'danger')
        return redirect(url_for('topic_generator'))
    prompt = f"Create study notes for '{topic}' with definition, explanation, examples, key points, and practice questions. Format the output nicely with markdown if possible."
    notes = call_gemini(prompt)
    return render_template('ai_notes.html', topic=topic, notes=notes)


@app.route('/ai_chat', methods=['GET', 'POST'])
@login_required
def ai_chat():
    answer = None
    q = None
    if request.method == 'POST':
        q = request.form.get('question')
        if q:
            answer = call_gemini(f"Answer this study-related question: {q}")
            if not answer:
                answer = 'No answer from AI.'
    return render_template('ai_chat.html', question=q, answer=answer)


@app.route('/focus_mode', methods=['GET', 'POST'])
@login_required
def focus_mode():
    topic = request.form.get('topic') if request.method == 'POST' else ''
    duration = int(request.form.get('duration') or 60)
    return render_template('focus_mode.html', topic=topic, duration=duration)


def send_whatsapp_reminder(user_id, recipient, subject, topic, minutes):
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')

    if not (account_sid and auth_token and recipient):
        return False

    from twilio.rest import Client
    client = Client(account_sid, auth_token)

    message = f"Hello {recipient}. Today's Study Topic: {topic or subject}. Goal {minutes} min. Keep your streak alive!"
    to_number = f"whatsapp:{recipient}"

    msg = client.messages.create(body=message, from_=from_number, to=to_number)
    return msg.sid


@app.route('/send_reminder')
@login_required
def send_reminder():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()
    if not profile:
        flash('Complete profile first.', 'warning')
        return redirect(url_for('profile'))

    subject = profile['subjects'].split(',')[0] if profile['subjects'] else SUBJECTS[0]
    topic = "Review today's study focus"
    minutes = profile['daily_goal'] or 60
    phone = user['phone'] or profile['phone'] if 'phone' in profile.keys() else None

    if not phone:
        flash('Phone number missing; cannot send WhatsApp reminder.', 'danger')
        return redirect(url_for('dashboard'))

    sid = send_whatsapp_reminder(user['id'], phone, subject, topic, minutes)
    if sid:
        flash('WhatsApp reminder sent!', 'success')
    else:
        flash('WhatsApp reminder could not be sent; configure Twilio credentials.', 'danger')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
