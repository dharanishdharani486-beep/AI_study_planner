from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime, date, timedelta
from google import genai
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

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
MIN_STUDY_MINUTES = 30

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
    'Computer Science': [
        'Introduction to Computers and Digital Devices',
        'Internet, Web and Cyber Safety',
        'MS Office / Productivity Tools',
        'HTML and Basic Web Page Design',
        'Python Basics (Variables, Input/Output, Operators)',
        'Control Statements (if-else, loops)',
        'Functions and Modular Programming',
        'Lists, Strings and Dictionaries',
        'Database Concepts and SQL Basics',
        'Computer Networks Basics',
        'Data Representation and Number System',
        'Ethics, AI Awareness and Digital Citizenship'
    ],
    'Mathematics': ['Linear Algebra', 'Calculus', 'Probability & Statistics', 'Discrete Math', 'Differential Equations'],
    'Physics': ['Mechanics', 'Thermodynamics', 'Electromagnetism', 'Quantum Physics', 'Optics']
}

SCHOOL_SUBJECTS_BY_GRADE = {
    '1-5':            ['Mathematics', 'English', 'Science', 'Social Studies', 'Hindi', 'EVS', 'Art & Craft', 'Moral Science', 'Physical Education'],
    '6-8':            ['Mathematics', 'Science', 'Social Science', 'English', 'Hindi', 'Sanskrit', 'Computer Science', 'Physical Education', 'Art'],
    '9-10':           ['Mathematics', 'Science', 'Social Science', 'English', 'Hindi', 'Computer Science', 'Sanskrit', 'Physical Education'],
    '11-12 Science':  ['Physics', 'Chemistry', 'Mathematics', 'Biology', 'Computer Science', 'English', 'Physical Education'],
    '11-12 Commerce': ['Accountancy', 'Business Studies', 'Economics', 'Mathematics', 'English', 'Computer Science', 'Entrepreneurship'],
    '11-12 Arts':     ['History', 'Geography', 'Political Science', 'Economics', 'English', 'Sociology', 'Psychology', 'Fine Arts', 'Physical Education'],
}

# Default school subjects when no specific grade is selected yet
SCHOOL_SUBJECTS_DEFAULT = [
    'Mathematics', 'Science', 'English', 'Social Science', 'Hindi',
    'Computer Science', 'Sanskrit', 'Physical Education', 'Art', 'Moral Science'
]

SCHOOL_GRADES = [
    '1', '2', '3', '4', '5',
    '6', '7', '8',
    '9', '10',
    '11 Science', '11 Commerce', '11 Arts',
    '12 Science', '12 Commerce', '12 Arts',
]

COLLEGE_STREAMS = [
    'Engineering & Technology',
    'Science',
    'Commerce & Accountancy',
    'Arts & Humanities',
    'Medical & Paramedical',
    'Law',
    'Management / MBA',
]

COLLEGE_SUBJECTS_BY_STREAM = {
    'Engineering & Technology': [
        'Mathematics', 'Physics', 'Chemistry', 'Programming', 'Data Structures',
        'Algorithms', 'DBMS', 'Operating Systems', 'Computer Networks',
        'Software Engineering', 'Artificial Intelligence', 'Machine Learning',
        'Computer Architecture', 'Web Development', 'Cyber Security',
    ],
    'Science': [
        'Physics', 'Chemistry', 'Mathematics', 'Biology', 'Statistics',
        'Biochemistry', 'Microbiology', 'Environmental Science', 'Geology', 'Zoology',
    ],
    'Commerce & Accountancy': [
        'Accountancy', 'Business Studies', 'Economics', 'Mathematics', 'Statistics',
        'Finance', 'Marketing', 'Human Resource Management',
        'Business Law', 'Entrepreneurship', 'Taxation',
    ],
    'Arts & Humanities': [
        'History', 'Geography', 'Political Science', 'Economics', 'Sociology',
        'Psychology', 'Philosophy', 'Literature', 'Journalism',
        'Fine Arts', 'Linguistics', 'Public Administration',
    ],
    'Medical & Paramedical': [
        'Biology', 'Chemistry', 'Physics', 'Anatomy', 'Physiology',
        'Biochemistry', 'Pharmacology', 'Pathology', 'Microbiology',
        'Nursing', 'Community Medicine',
    ],
    'Law': [
        'Constitutional Law', 'Criminal Law', 'Civil Law', 'Commercial Law',
        'International Law', 'Family Law', 'Legal Research', 'Jurisprudence',
        'Corporate Law', 'Human Rights', 'Environmental Law',
    ],
    'Management / MBA': [
        'Marketing', 'Finance', 'Human Resource Management', 'Operations Management',
        'Business Strategy', 'Economics', 'Accounting', 'Entrepreneurship',
        'Business Analytics', 'Organisational Behaviour', 'International Business',
    ],
}


def get_subjects_for_grade(grade, student_type=None):
    """Return subjects list based on grade (school) or college stream."""
    if not grade:
        return SCHOOL_SUBJECTS_DEFAULT if student_type == 'school' else SUBJECTS
    # College stream lookup
    if grade in COLLEGE_SUBJECTS_BY_STREAM:
        return COLLEGE_SUBJECTS_BY_STREAM[grade]
    # School grade lookup
    g = str(grade).strip().lower()
    parts = g.split()
    try:
        num = int(parts[0])
    except (ValueError, IndexError):
        return SUBJECTS
    stream = parts[1] if len(parts) > 1 else ''
    if num <= 5:
        return SCHOOL_SUBJECTS_BY_GRADE['1-5']
    elif num <= 8:
        return SCHOOL_SUBJECTS_BY_GRADE['6-8']
    elif num <= 10:
        return SCHOOL_SUBJECTS_BY_GRADE['9-10']
    elif num in (11, 12):
        if 'commerce' in stream:
            return SCHOOL_SUBJECTS_BY_GRADE['11-12 Commerce']
        elif 'arts' in stream or 'art' in stream:
            return SCHOOL_SUBJECTS_BY_GRADE['11-12 Arts']
        else:
            return SCHOOL_SUBJECTS_BY_GRADE['11-12 Science']
    return SUBJECTS


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
            email TEXT,
            last_login_at TEXT
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            exam_type TEXT DEFAULT 'exam',
            topics TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit(); conn.close()


def ensure_schema_updates():
    conn = get_db_connection()
    c = conn.cursor()
    # users table
    columns = c.execute('PRAGMA table_info(users)').fetchall()
    column_names = {row['name'] for row in columns}
    if 'last_login_at' not in column_names:
        c.execute('ALTER TABLE users ADD COLUMN last_login_at TEXT')
        conn.commit()
    # student_profile table — add school-specific columns
    sp_cols = c.execute('PRAGMA table_info(student_profile)').fetchall()
    sp_col_names = {row['name'] for row in sp_cols}
    for col, coltype in [
        ('grade', 'TEXT'), ('section', 'TEXT'), ('board', 'TEXT'),
        ('parent_email', 'TEXT'), ('student_type', "TEXT DEFAULT 'college'")
    ]:
        if col not in sp_col_names:
            c.execute(f'ALTER TABLE student_profile ADD COLUMN {col} {coltype}')
    conn.commit()
    # ensure homework and exams tables exist (for DBs created before this feature)
    c.execute('''CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        title TEXT NOT NULL, subject TEXT NOT NULL, due_date TEXT NOT NULL,
        priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        name TEXT NOT NULL, subject TEXT NOT NULL, exam_date TEXT NOT NULL,
        exam_type TEXT DEFAULT 'exam', topics TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()


def mark_user_active_today():
    user_id = session.get('user_id')
    if not user_id:
        return

    conn = get_db_connection()
    user = conn.execute('SELECT last_login_at FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return

    if user['last_login_at']:
        try:
            if datetime.fromisoformat(user['last_login_at']).date() == date.today():
                conn.close()
                return
        except ValueError:
            pass

    conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


@app.before_request
def setup():
    if not os.path.exists(DB_PATH):
        init_db()
    ensure_schema_updates()
    mark_user_active_today()


def current_user():
    if 'user_id' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return user
    return None


@app.context_processor
def inject_current_profile():
    """Make current_profile available in every template (for conditional nav)."""
    user = current_user()
    if user:
        conn = get_db_connection()
        prof = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
        conn.close()
        return {'current_profile': prof}
    return {'current_profile': None}


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
        email = request.form.get('email', '').strip()
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('signup.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('signup.html')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                         (username, password, email))
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
        if user:
            conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
            profile = conn.execute('SELECT student_type FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
            conn.close()
            session['user_id'] = user['id']
            if not profile or not (profile['student_type'] or '').strip():
                flash('Login successful. Please complete your profile and choose School or College student.', 'info')
                return redirect(url_for('profile'))

            flash('Login successful.', 'success')
            return redirect(url_for('dashboard'))
        conn.close()
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
        student_type = request.form.get('student_type', 'college').strip().lower()
        if student_type not in ('school', 'college'):
            student_type = 'college'
        full_name = request.form.get('full_name', '').strip()
        school = request.form.get('school', '').strip()
        department = request.form.get('department', '').strip()
        grade = request.form.get('grade', '').strip()
        section = request.form.get('section', '').strip()
        board = request.form.get('board', '').strip()
        email = request.form.get('email', '').strip()
        parent_email = request.form.get('parent_email', '').strip()
        subjects = ','.join(request.form.getlist('subjects'))
        daily_goal = int(request.form.get('daily_goal') or 60)
        if daily_goal < MIN_STUDY_MINUTES:
            daily_goal = MIN_STUDY_MINUTES
            flash(f'Daily study goal updated to minimum {MIN_STUDY_MINUTES} minutes.', 'info')

        # Keep board and parent email strictly school-only.
        if student_type != 'school':
            board = ''
            parent_email = ''

        conn.execute('UPDATE users SET email = ? WHERE id = ?', (email, user['id']))
        if profile:
            conn.execute(
                '''UPDATE student_profile
                   SET full_name=?, school=?, department=?, grade=?, section=?, board=?,
                       parent_email=?, subjects=?, daily_goal=?, student_type=?
                   WHERE user_id = ?''',
                (full_name, school, department, grade, section, board, parent_email, subjects, daily_goal, student_type, user['id']))
        else:
            conn.execute(
                '''INSERT INTO student_profile
                   (user_id, full_name, school, department, grade, section, board, parent_email, subjects, daily_goal, student_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user['id'], full_name, school, department, grade, section, board, parent_email, subjects, daily_goal, student_type))
        conn.commit()
        conn.close()
        flash('Profile saved.', 'success')
        return redirect(url_for('dashboard'))
    conn.close()
    stype = profile['student_type'] if profile else 'college'
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None, stype)
    return render_template('profile.html', user=user, profile=profile,
                           subjects=grade_subjects, all_grades=SCHOOL_GRADES,
                           school_subjects_by_grade=SCHOOL_SUBJECTS_BY_GRADE,
                           school_subjects_default=SCHOOL_SUBJECTS_DEFAULT,
                           college_subjects=SUBJECTS,
                           college_streams=COLLEGE_STREAMS,
                           college_subjects_by_stream=COLLEGE_SUBJECTS_BY_STREAM)


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


def get_latest_reminder_plan(user_id):
    conn = get_db_connection()
    reminder = conn.execute(
        '''
        SELECT * FROM reminders
        WHERE user_id = ? AND is_enabled = 1
        ORDER BY id DESC
        LIMIT 1
        ''',
        (user_id,)
    ).fetchone()
    conn.close()
    return reminder


def get_reminder_payload(user, profile=None, reminder=None):
    profile_subjects = []
    if profile and profile['subjects']:
        profile_subjects = [item.strip() for item in profile['subjects'].split(',') if item.strip()]

    mandatory_subject = None
    extra_subjects = []

    if reminder:
        mandatory_subject = (reminder['subject'] or '').strip() or None
        extra_subjects = [item.strip() for item in (reminder['topic'] or '').split(',') if item.strip()]

    if not mandatory_subject and profile_subjects:
        mandatory_subject = profile_subjects[0]

    if not extra_subjects and len(profile_subjects) > 1:
        extra_subjects = profile_subjects[1:3]

    student_type = (profile['student_type'] or '').strip().lower() if profile and 'student_type' in profile.keys() and profile['student_type'] else 'college'
    full_name = (profile['full_name'] or user['username']).strip() if profile and 'full_name' in profile.keys() and profile['full_name'] else user['username']
    grade_or_stream = (profile['grade'] or '').strip() if profile and 'grade' in profile.keys() and profile['grade'] else ''
    board = (profile['board'] or '').strip() if profile and 'board' in profile.keys() and profile['board'] else ''
    department = (profile['department'] or '').strip() if profile and 'department' in profile.keys() and profile['department'] else ''
    school_or_college = (profile['school'] or '').strip() if profile and 'school' in profile.keys() and profile['school'] else ''

    topic = f"Primary focus: {mandatory_subject}" if mandatory_subject else "Review today's study focus"
    daily_goal = profile['daily_goal'] if profile and profile['daily_goal'] else 60
    if daily_goal < MIN_STUDY_MINUTES:
        daily_goal = MIN_STUDY_MINUTES

    return {
        'user_id': user['id'],
        'recipient': user['email'],
        'mandatory_subject': mandatory_subject or SUBJECTS[0],
        'extra_subjects': extra_subjects,
        'topic': topic,
        'minutes': daily_goal,
        'student_type': student_type,
        'full_name': full_name,
        'grade_or_stream': grade_or_stream,
        'board': board,
        'department': department,
        'school_or_college': school_or_college,
    }


def mark_reminder_sent(reminder_id):
    if not reminder_id:
        return

    conn = get_db_connection()
    conn.execute('UPDATE reminders SET last_sent = ? WHERE id = ?', (datetime.now().isoformat(), reminder_id))
    conn.commit()
    conn.close()


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()

    if not profile or not (profile['student_type'] or '').strip():
        conn.close()
        flash('Please complete your profile first and choose School or College student.', 'warning')
        return redirect(url_for('profile'))

    study_logs = conn.execute('SELECT * FROM study_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user['id'],)).fetchall()
    today_str = date.today().isoformat()
    upcoming_hw = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status = 'pending' AND due_date >= ? ORDER BY due_date ASC LIMIT 5",
        (user['id'], today_str)
    ).fetchall()
    overdue_hw = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status = 'pending' AND due_date < ? ORDER BY due_date ASC",
        (user['id'], today_str)
    ).fetchall()
    next_exam = conn.execute(
        'SELECT * FROM exams WHERE user_id = ? AND exam_date >= ? ORDER BY exam_date ASC LIMIT 1',
        (user['id'], today_str)
    ).fetchone()
    conn.close()

    today_logs = get_today_logs(user['id'])
    total_today = sum([row['minutes'] for row in today_logs])
    total_all = sum([row['minutes'] for row in study_logs])
    streak = calculate_streak(user['id'])

    # Resolve student mode reliably (supports old profiles without student_type).
    raw_type = (profile['student_type'] or '').strip().lower() if profile and profile['student_type'] else ''
    grade_value = (profile['grade'] or '').strip() if profile and profile['grade'] else ''
    inferred_school = False
    if grade_value and grade_value not in COLLEGE_STREAMS:
        first_token = grade_value.split()[0]
        if first_token.isdigit():
            inferred_school = True
    student_type = raw_type if raw_type in ('school', 'college') else ('school' if inferred_school else 'college')
    is_school = student_type == 'school'

    grade = profile['grade'] if profile else None
    grade_subjects = get_subjects_for_grade(grade, student_type)
    subject_topics_for_grade = {s: SUBJECT_TOPICS.get(s, []) for s in grade_subjects}

    return render_template('dashboard.html', user=user, profile=profile,
                           today_logs=today_logs, total_today=total_today,
                           total_all=total_all, streak=streak,
                           subjects=grade_subjects, subject_topics=subject_topics_for_grade,
                           upcoming_hw=upcoming_hw, overdue_hw=overdue_hw,
                           next_exam=next_exam, is_school=is_school,
                           student_type=student_type)


@app.route('/add_study', methods=['POST'])
@login_required
def add_study():
    user = current_user()
    subject = request.form.get('subject')
    minutes = int(request.form.get('minutes') or 0)
    topic = request.form.get('topic') or ''
    if not subject or minutes < MIN_STUDY_MINUTES:
        flash(f'Please provide subject and at least {MIN_STUDY_MINUTES} minutes.', 'danger')
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
        conn.execute('UPDATE reminders SET is_enabled = 0 WHERE user_id = ?', (user['id'],))
        conn.execute('INSERT INTO reminders (user_id, subject, topic, is_enabled, last_sent) VALUES (?, ?, ?, 1, ?)',
                     (user['id'], mandatory, ','.join(extra), None))
        conn.commit()
        reminder = conn.execute(
            'SELECT * FROM reminders WHERE user_id = ? ORDER BY id DESC LIMIT 1',
            (user['id'],)
        ).fetchone()
        profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
        payload = get_reminder_payload(user, profile=profile, reminder=reminder)

        if payload['recipient']:
            success = send_email_reminder(
                payload['user_id'],
                payload['recipient'],
                payload['mandatory_subject'],
                payload['topic'],
                payload['minutes'],
                payload['extra_subjects'],
                payload['student_type'],
                payload['full_name'],
                payload['grade_or_stream'],
                payload['board'],
                payload['department'],
                payload['school_or_college']
            )
            if success:
                mark_reminder_sent(reminder['id'])
                flash(f"Study plan emailed to {payload['recipient']}", 'success')
            else:
                flash('Plan saved, but email could not be sent. Check SMTP settings.', 'warning')
        else:
            flash('Plan saved. Add your email in Profile to receive automatic reminders.', 'warning')
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)
    return render_template('plan_subjects.html', subjects=grade_subjects, profile=profile)


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
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT grade FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)
    if request.method == 'POST':
        selected_subject = request.form.get('subject')
        if not selected_subject:
            flash('Select a subject first.', 'danger')
            return redirect(url_for('topic_generator'))
        prompt = f"Generate 5 concise study topic suggestions for the subject {selected_subject}. Return only the list of topics, one per line."
        generated = call_gemini(prompt)
    return render_template('topic_generator.html', subjects=grade_subjects, generated=generated, selected_subject=selected_subject)


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
            user = current_user()
            conn = get_db_connection()
            prof = conn.execute('SELECT grade FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
            conn.close()
            grade = prof['grade'] if prof and prof['grade'] else None
            grade_note = f' Please explain clearly for a Grade {grade} school student.' if grade else ''
            answer = call_gemini(f'Answer this study-related question.{grade_note} Question: {q}')
            if not answer:
                answer = 'No answer from AI.'
    return render_template('ai_chat.html', question=q, answer=answer)


@app.route('/focus_mode', methods=['GET', 'POST'])
@login_required
def focus_mode():
    topic = request.form.get('topic') if request.method == 'POST' else ''
    duration = int(request.form.get('duration') or 60)
    return render_template('focus_mode.html', topic=topic, duration=duration)


# ── Homework tracker ──────────────────────────────────────────────────────────

@app.route('/homework', methods=['GET', 'POST'])
@login_required
def homework():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subject = request.form.get('subject', '').strip()
        due_date = request.form.get('due_date', '').strip()
        priority = request.form.get('priority', 'medium')
        if not title or not subject or not due_date:
            flash('Title, subject and due date are required.', 'danger')
        else:
            conn.execute(
                'INSERT INTO homework (user_id, title, subject, due_date, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user['id'], title, subject, due_date, priority, 'pending', datetime.now().isoformat())
            )
            conn.commit()
            flash('Homework added.', 'success')
        conn.close()
        return redirect(url_for('homework'))

    today_str = date.today().isoformat()
    pending = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status = 'pending' ORDER BY due_date ASC",
        (user['id'],)
    ).fetchall()
    done = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status = 'done' ORDER BY due_date DESC LIMIT 20",
        (user['id'],)
    ).fetchall()
    conn.close()
    return render_template('homework.html', pending=pending, done=done,
                           subjects=grade_subjects, today=today_str)


@app.route('/homework/complete/<int:hw_id>')
@login_required
def homework_complete(hw_id):
    user = current_user()
    conn = get_db_connection()
    conn.execute("UPDATE homework SET status = 'done' WHERE id = ? AND user_id = ?", (hw_id, user['id']))
    conn.commit(); conn.close()
    flash('Homework marked as done! Great work.', 'success')
    return redirect(url_for('homework'))


@app.route('/homework/delete/<int:hw_id>')
@login_required
def homework_delete(hw_id):
    user = current_user()
    conn = get_db_connection()
    conn.execute('DELETE FROM homework WHERE id = ? AND user_id = ?', (hw_id, user['id']))
    conn.commit(); conn.close()
    flash('Homework deleted.', 'info')
    return redirect(url_for('homework'))


# ── Exam planner ──────────────────────────────────────────────────────────────

@app.route('/exams', methods=['GET', 'POST'])
@login_required
def exams():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        exam_date = request.form.get('exam_date', '').strip()
        exam_type = request.form.get('exam_type', 'exam')
        topics = request.form.get('topics', '').strip()
        if not name or not subject or not exam_date:
            flash('Name, subject and date are required.', 'danger')
        else:
            conn.execute(
                'INSERT INTO exams (user_id, name, subject, exam_date, exam_type, topics, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user['id'], name, subject, exam_date, exam_type, topics, datetime.now().isoformat())
            )
            conn.commit()
            flash('Exam added.', 'success')
        conn.close()
        return redirect(url_for('exams'))

    today_str = date.today().isoformat()
    upcoming = conn.execute(
        'SELECT * FROM exams WHERE user_id = ? AND exam_date >= ? ORDER BY exam_date ASC',
        (user['id'], today_str)
    ).fetchall()
    past = conn.execute(
        'SELECT * FROM exams WHERE user_id = ? AND exam_date < ? ORDER BY exam_date DESC LIMIT 20',
        (user['id'], today_str)
    ).fetchall()
    conn.close()
    return render_template('exams.html', upcoming=upcoming, past=past,
                           subjects=grade_subjects, today=today_str)


@app.route('/exams/delete/<int:exam_id>')
@login_required
def exam_delete(exam_id):
    user = current_user()
    conn = get_db_connection()
    conn.execute('DELETE FROM exams WHERE id = ? AND user_id = ?', (exam_id, user['id']))
    conn.commit(); conn.close()
    flash('Exam deleted.', 'info')
    return redirect(url_for('exams'))


import smtplib
from email.message import EmailMessage

def send_email_reminder(user_id, recipient, subject, topic, minutes, extra_subjects=None,
                        student_type='college', full_name='', grade_or_stream='',
                        board='', department='', school_or_college=''):
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')

    if not (smtp_user and smtp_password and recipient):
        return False

    extra_subjects = extra_subjects or []
    extra_line = ''
    if extra_subjects:
        extra_line = ', '.join(extra_subjects)

    if student_type == 'school':
        school_line = f"School: {school_or_college}\n" if school_or_college else ''
        grade_line = f"Class/Grade: {grade_or_stream}\n" if grade_or_stream else ''
        board_line = f"Board/Curriculum: {board}\n" if board else ''
        extra_block = f"Additional subjects: {extra_line}\n" if extra_line else ''
        message = (
            f"Hello {full_name or 'Student'},\n\n"
            f"This is your school study reminder for today.\n\n"
            f"{school_line}"
            f"{grade_line}"
            f"{board_line}"
            f"Main subject: {subject}\n"
            f"{extra_block}"
            f"Today's focus: {topic or subject}\n"
            f"Study target: {minutes} minutes\n\n"
            f"Complete your homework, revise important topics, and keep your study streak active today."
        )
        email_subject = 'Your School Study Reminder'
    else:
        college_line = f"College: {school_or_college}\n" if school_or_college else ''
        stream_line = f"Stream/Specialization: {grade_or_stream}\n" if grade_or_stream else ''
        department_line = f"Department: {department}\n" if department else ''
        extra_block = f"Supporting subjects: {extra_line}\n" if extra_line else ''
        message = (
            f"Hello {full_name or 'Student'},\n\n"
            f"This is your college study reminder for today.\n\n"
            f"{college_line}"
            f"{stream_line}"
            f"{department_line}"
            f"Primary subject: {subject}\n"
            f"{extra_block}"
            f"Focus note: {topic or subject}\n"
            f"Daily goal: {minutes} minutes\n\n"
            f"Keep your momentum up, finish one meaningful study block, and stay consistent with your plan."
        )
        email_subject = 'Your College Study Reminder'
    
    msg = EmailMessage()
    msg.set_content(message)
    msg['Subject'] = email_subject
    msg['From'] = smtp_user
    msg['To'] = recipient

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_all_automatic_reminders():
    auto_enabled = os.environ.get('AUTO_REMINDERS_ENABLED', 'true').strip().lower() == 'true'
    if not auto_enabled:
        return

    print("Running automatic background reminders...")
    conn = None
    try:
        conn = get_db_connection()
        reminder_interval_hours = int(os.environ.get('REMINDER_INTERVAL_HOURS', 1))
        users = conn.execute('''
            SELECT u.id, u.username, u.email, u.last_login_at,
                   p.subjects, p.daily_goal, p.parent_email, p.student_type,
                   p.full_name, p.grade, p.board, p.department, p.school
            FROM users u
            JOIN student_profile p ON u.id = p.user_id
        ''').fetchall()
        
        for u in users:
            email = u['email']
            if not email:
                continue

            # If user has logged in today, stop automatic reminders for the rest of the day.
            if u['last_login_at']:
                try:
                    if datetime.fromisoformat(u['last_login_at']).date() == date.today():
                        continue
                except ValueError:
                    pass

            reminder = conn.execute('SELECT * FROM reminders WHERE user_id = ? AND is_enabled = 1 ORDER BY id DESC LIMIT 1',
                                    (u['id'],)).fetchone()
            if reminder and reminder['last_sent']:
                last_sent_dt = datetime.fromisoformat(reminder['last_sent'])
                if datetime.now() - last_sent_dt < timedelta(hours=reminder_interval_hours):
                    continue

            payload = get_reminder_payload(u, profile=u, reminder=reminder)
            
            success = send_email_reminder(
                payload['user_id'],
                email,
                payload['mandatory_subject'],
                payload['topic'],
                payload['minutes'],
                payload['extra_subjects'],
                payload['student_type'],
                payload['full_name'],
                payload['grade_or_stream'],
                payload['board'],
                payload['department'],
                payload['school_or_college']
            )
            if success:
                if reminder:
                    conn.execute('UPDATE reminders SET last_sent = ? WHERE id = ?',
                                 (datetime.now().isoformat(), reminder['id']))
                    conn.commit()
                print(f"Sent automatic reminder to {email}")
                # Also send to parent if set
                parent_email = u['parent_email'] if 'parent_email' in u.keys() else None
                if parent_email and parent_email != email:
                    send_email_reminder(payload['user_id'], parent_email, payload['mandatory_subject'],
                                        payload['topic'], payload['minutes'], payload['extra_subjects'],
                                        payload['student_type'], payload['full_name'],
                                        payload['grade_or_stream'], payload['board'],
                                        payload['department'], payload['school_or_college'])
            else:
                print(f"Failed to send automatic reminder to {email}")
    except Exception as e:
        print(f"Error in background reminders: {e}")
    finally:
        if conn:
            conn.close()


def start_scheduler():
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return None

    auto_enabled = os.environ.get('AUTO_REMINDERS_ENABLED', 'true').strip().lower() == 'true'
    if not auto_enabled:
        return None

    reminder_interval_hours = int(os.environ.get('REMINDER_INTERVAL_HOURS', 1))
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=send_all_automatic_reminders,
        trigger='interval',
        hours=reminder_interval_hours,
        id='daily-email-reminders',
        replace_existing=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    return scheduler

scheduler = start_scheduler()

if __name__ == '__main__':
    app.run(debug=True)
