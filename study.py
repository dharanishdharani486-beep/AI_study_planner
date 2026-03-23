from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import sqlite3
import os
import json
import time
import random
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import smtplib
from email.message import EmailMessage
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

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
if CORS is not None:
    CORS(app)

# Configure AI provider
DB_PATH = os.path.join(os.path.dirname(__file__), 'studycoach.db')
MIN_STUDY_MINUTES = 30
BASE_DIR = os.path.dirname(__file__)
UPLOAD_ROOT = os.path.join(BASE_DIR, 'uploads')
TEACHER_PROOF_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, 'teacher_proofs')
STUDY_MATERIAL_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, 'materials')
ALLOWED_MATERIAL_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx'}
ALLOWED_TEACHER_CERT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
TEACHER_DEGREE_KEYWORDS = {
    'bachelor', 'master', 'b.sc', 'b.e', 'b.tech', 'university', 'degree',
    'engineering', 'science', 'college', 'institute'
}
WEEKLY_TEST_MAX_MARKS = 50
TEACHER_VERIFICATION_ENABLED = os.environ.get('TEACHER_VERIFICATION_ENABLED', 'false').strip().lower() == 'true'
VIOLATION_SCORE_MAP = {
    'tab_switch': 2,
    'tab_switch_detected': 2,
    'fullscreen_exit': 3,
    'copy_attempt': 1,
    'paste_attempt': 1,
    'multiple_face': 4,
    'unusual_fast_answering': 2,
    'right_click': 1,
}
VIOLATION_SUSPICION_THRESHOLD = 6

app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE_BYTES

for _folder in (UPLOAD_ROOT, TEACHER_PROOF_UPLOAD_DIR, STUDY_MATERIAL_UPLOAD_DIR):
    os.makedirs(_folder, exist_ok=True)

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

EXAM_QUESTION_BANK = {
    'Mathematics': [
        {
            'id': 'math_1',
            'question': 'What is the value of x if 2x + 5 = 17?',
            'options': ['4', '5', '6', '7'],
            'answer': 2
        },
        {
            'id': 'math_2',
            'question': 'sin(90°) is equal to:',
            'options': ['0', '1', '1/2', 'Undefined'],
            'answer': 1
        },
        {
            'id': 'math_3',
            'question': 'Derivative of x^2 with respect to x is:',
            'options': ['x', '2x', 'x^2', '2'],
            'answer': 1
        },
        {
            'id': 'math_4',
            'question': 'Integral of 1/x dx is:',
            'options': ['x', 'ln|x| + C', '1/x^2 + C', 'e^x + C'],
            'answer': 1
        },
        {
            'id': 'math_5',
            'question': 'The quadratic formula is used to solve equations of form:',
            'options': ['ax + b = 0', 'ax^2 + bx + c = 0', 'ax^3 + bx + c = 0', 'a/x + b = 0'],
            'answer': 1
        },
        {
            'id': 'math_6',
            'question': 'If tan(theta) = 1, then theta can be:',
            'options': ['30°', '45°', '60°', '90°'],
            'answer': 1
        },
        {
            'id': 'math_7',
            'question': 'Limit of (1 + 1/n)^n as n approaches infinity is:',
            'options': ['1', '0', 'e', 'Infinity'],
            'answer': 2
        },
        {
            'id': 'math_8',
            'question': 'Value of cos(0°) is:',
            'options': ['0', '1', '-1', 'Undefined'],
            'answer': 1
        },
        {
            'id': 'math_9',
            'question': 'The sum of first n natural numbers is:',
            'options': ['n(n+1)/2', 'n^2', 'n(n-1)/2', '2n'],
            'answer': 0
        },
        {
            'id': 'math_10',
            'question': 'If f(x) = 3x + 2, then f(4) is:',
            'options': ['10', '12', '14', '18'],
            'answer': 2
        },
        {
            'id': 'math_11',
            'question': 'The angle sum of a triangle is:',
            'options': ['90°', '180°', '270°', '360°'],
            'answer': 1
        },
        {
            'id': 'math_12',
            'question': 'd/dx (sin x) =',
            'options': ['cos x', '-cos x', 'sin x', '-sin x'],
            'answer': 0
        },
    ],
    'Computer Science': [
        {
            'id': 'cs_1',
            'question': 'Which data structure uses LIFO order?',
            'options': ['Queue', 'Stack', 'Array', 'Graph'],
            'answer': 1
        },
        {
            'id': 'cs_2',
            'question': 'What is the output type of input() in Python?',
            'options': ['int', 'float', 'str', 'bool'],
            'answer': 2
        },
        {
            'id': 'cs_3',
            'question': 'Which SQL statement is used to retrieve data?',
            'options': ['UPDATE', 'INSERT', 'SELECT', 'DELETE'],
            'answer': 2
        },
        {
            'id': 'cs_4',
            'question': 'Time complexity of binary search is:',
            'options': ['O(n)', 'O(log n)', 'O(n log n)', 'O(1)'],
            'answer': 1
        },
        {
            'id': 'cs_5',
            'question': 'Which normal form removes partial dependency?',
            'options': ['1NF', '2NF', '3NF', 'BCNF'],
            'answer': 1
        },
        {
            'id': 'cs_6',
            'question': 'Which loop in Python checks condition before execution?',
            'options': ['for', 'while', 'do-while', 'repeat-until'],
            'answer': 1
        },
        {
            'id': 'cs_7',
            'question': 'Primary key in a database table must be:',
            'options': ['Nullable', 'Unique and non-null', 'Repeated', 'A text field only'],
            'answer': 1
        },
        {
            'id': 'cs_8',
            'question': 'Which traversal of BST gives sorted output?',
            'options': ['Preorder', 'Postorder', 'Inorder', 'Level-order'],
            'answer': 2
        },
        {
            'id': 'cs_9',
            'question': 'Which protocol is primarily used to load web pages?',
            'options': ['FTP', 'SSH', 'HTTP', 'SMTP'],
            'answer': 2
        },
        {
            'id': 'cs_10',
            'question': 'What does DBMS stand for?',
            'options': ['Data Backup Management System', 'Database Management System', 'Digital Base Model System', 'Database Mapping Service'],
            'answer': 1
        },
        {
            'id': 'cs_11',
            'question': 'In Python, which symbol starts a comment?',
            'options': ['//', '#', '--', '/*'],
            'answer': 1
        },
        {
            'id': 'cs_12',
            'question': 'Which data structure is best for FIFO operations?',
            'options': ['Stack', 'Queue', 'Tree', 'Heap'],
            'answer': 1
        },
    ],
    'Science': [
        {
            'id': 'sci_1',
            'question': 'SI unit of force is:',
            'options': ['Joule', 'Pascal', 'Newton', 'Watt'],
            'answer': 2
        },
        {
            'id': 'sci_2',
            'question': 'Chemical symbol of sodium is:',
            'options': ['So', 'Na', 'S', 'Sn'],
            'answer': 1
        },
        {
            'id': 'sci_3',
            'question': 'Basic structural and functional unit of life is:',
            'options': ['Atom', 'Cell', 'Tissue', 'Organ'],
            'answer': 1
        },
        {
            'id': 'sci_4',
            'question': 'Acceleration due to gravity on Earth is approximately:',
            'options': ['4.9 m/s^2', '9.8 m/s^2', '19.6 m/s^2', '98 m/s^2'],
            'answer': 1
        },
        {
            'id': 'sci_5',
            'question': 'pH value less than 7 indicates:',
            'options': ['Neutral solution', 'Acidic solution', 'Basic solution', 'Salt solution'],
            'answer': 1
        },
        {
            'id': 'sci_6',
            'question': 'Photosynthesis mainly occurs in:',
            'options': ['Mitochondria', 'Nucleus', 'Chloroplast', 'Ribosome'],
            'answer': 2
        },
        {
            'id': 'sci_7',
            'question': 'Law of inertia is given by:',
            'options': ['Newton\'s first law', 'Newton\'s second law', 'Newton\'s third law', 'Ohm\'s law'],
            'answer': 0
        },
        {
            'id': 'sci_8',
            'question': 'Water formula is:',
            'options': ['CO2', 'O2', 'H2O', 'NaCl'],
            'answer': 2
        },
        {
            'id': 'sci_9',
            'question': 'Human blood circulation is pumped by:',
            'options': ['Lungs', 'Brain', 'Heart', 'Kidneys'],
            'answer': 2
        },
        {
            'id': 'sci_10',
            'question': 'Speed is distance divided by:',
            'options': ['Mass', 'Time', 'Force', 'Energy'],
            'answer': 1
        },
        {
            'id': 'sci_11',
            'question': 'The lightest gas is:',
            'options': ['Helium', 'Hydrogen', 'Nitrogen', 'Oxygen'],
            'answer': 1
        },
        {
            'id': 'sci_12',
            'question': 'DNA stands for:',
            'options': ['Deoxyribonucleic acid', 'Dynamic Nuclear Acid', 'Double Nitrogen Atom', 'None of these'],
            'answer': 0
        },
    ],
    'English': [
        {
            'id': 'eng_1',
            'question': 'Choose the correct sentence:',
            'options': ['He go to school.', 'He goes to school.', 'He going to school.', 'He gone to school.'],
            'answer': 1
        },
        {
            'id': 'eng_2',
            'question': 'Synonym of "rapid" is:',
            'options': ['Slow', 'Quick', 'Weak', 'Calm'],
            'answer': 1
        },
        {
            'id': 'eng_3',
            'question': 'Antonym of "ancient" is:',
            'options': ['Old', 'Modern', 'Historic', 'Classic'],
            'answer': 1
        },
        {
            'id': 'eng_4',
            'question': 'Identify the noun in: "The cat sat on the mat."',
            'options': ['sat', 'on', 'cat', 'the'],
            'answer': 2
        },
        {
            'id': 'eng_5',
            'question': 'Which is a conjunction?',
            'options': ['Quickly', 'And', 'Beautiful', 'Under'],
            'answer': 1
        },
        {
            'id': 'eng_6',
            'question': 'Choose the correct punctuation: "What a beautiful day"',
            'options': ['What a beautiful day.', 'What a beautiful day?', 'What a beautiful day!', 'What a beautiful day,'],
            'answer': 2
        },
        {
            'id': 'eng_7',
            'question': 'Fill in the blank: She ____ reading a novel.',
            'options': ['is', 'are', 'am', 'be'],
            'answer': 0
        },
        {
            'id': 'eng_8',
            'question': 'A paragraph mainly consists of:',
            'options': ['Random sentences', 'A central idea', 'Only questions', 'Only dialogues'],
            'answer': 1
        },
        {
            'id': 'eng_9',
            'question': 'Choose the correct spelling:',
            'options': ['Definately', 'Definitely', 'Definatly', 'Defanitely'],
            'answer': 1
        },
        {
            'id': 'eng_10',
            'question': '"He is as brave as a lion" is an example of:',
            'options': ['Metaphor', 'Simile', 'Hyperbole', 'Personification'],
            'answer': 1
        },
        {
            'id': 'eng_11',
            'question': 'A story written by someone about their own life is:',
            'options': ['Biography', 'Autobiography', 'Novel', 'Essay'],
            'answer': 1
        },
        {
            'id': 'eng_12',
            'question': 'Choose the correct passive voice: "They completed the work."',
            'options': ['The work completed by them.', 'The work was completed by them.', 'The work is completed by them.', 'The work has complete by them.'],
            'answer': 1
        },
    ],
}

EXAM_TARGET_QUESTION_COUNT = 36

EXAM_SUBJECT_TOPIC_POOL = {
    'Mathematics': [
        'Algebra', 'Trigonometry', 'Calculus', 'Coordinate Geometry', 'Probability',
        'Statistics', 'Linear Equations', 'Quadratic Equations', 'Limits', 'Derivatives',
        'Integration', 'Matrices'
    ],
    'Computer Science': [
        'Python', 'Data Structures', 'DBMS', 'SQL', 'Operating Systems',
        'Computer Networks', 'Algorithms', 'Recursion', 'OOP', 'Complexity Analysis',
        'Stack and Queue', 'Trees and Graphs'
    ],
    'Science': [
        'Physics', 'Chemistry', 'Biology', 'Force and Motion', 'Atoms and Molecules',
        'Cell Structure', 'Electricity', 'Acids and Bases', 'Genetics', 'Periodic Table',
        'Photosynthesis', 'Newton Laws'
    ],
    'English': [
        'Grammar', 'Comprehension', 'Vocabulary', 'Tenses', 'Sentence Correction',
        'Synonyms and Antonyms', 'Parts of Speech', 'Punctuation', 'Active and Passive Voice',
        'Reported Speech', 'Reading Skills', 'Idioms and Phrases'
    ],
}


def _build_auto_exam_questions(subject, base_questions, target_count):
    if len(base_questions) >= target_count:
        return base_questions

    subject_topics = EXAM_SUBJECT_TOPIC_POOL.get(subject, [])
    if not subject_topics:
        return base_questions

    distractor_topics = []
    for other_subject, topics in EXAM_SUBJECT_TOPIC_POOL.items():
        if other_subject != subject:
            distractor_topics.extend(topics)

    if not distractor_topics:
        return base_questions

    existing_ids = {q['id'] for q in base_questions}
    prefix = ''.join(part[0].lower() for part in subject.split())
    auto_index = 1
    generated = []

    while len(base_questions) + len(generated) < target_count:
        topic = subject_topics[(auto_index - 1) % len(subject_topics)]
        wrong_options = []
        candidate_offset = (auto_index - 1) * 3
        candidate_index = 0

        while len(wrong_options) < 3:
            candidate = distractor_topics[(candidate_offset + candidate_index) % len(distractor_topics)]
            candidate_index += 1
            if candidate != topic and candidate not in wrong_options:
                wrong_options.append(candidate)

        correct_position = (auto_index - 1) % 4
        options = list(wrong_options)
        options.insert(correct_position, topic)

        stem_variant = (auto_index - 1) % 4
        if stem_variant == 0:
            question_text = f'Which of the following is a topic of {subject}?'
        elif stem_variant == 1:
            question_text = f'Identify the option that best belongs to {subject} syllabus.'
        elif stem_variant == 2:
            question_text = f'Pick the {subject} concept from the options below.'
        else:
            question_text = f'Choose the topic that is most closely related to {subject}.'

        generated_id = f'{prefix}_auto_{auto_index}'
        while generated_id in existing_ids:
            auto_index += 1
            generated_id = f'{prefix}_auto_{auto_index}'

        generated.append({
            'id': generated_id,
            'question': question_text,
            'options': options,
            'answer': correct_position,
        })
        existing_ids.add(generated_id)
        auto_index += 1

    return base_questions + generated


def build_large_exam_question_bank(base_bank, target_count=EXAM_TARGET_QUESTION_COUNT):
    expanded_bank = {}
    for subject, questions in base_bank.items():
        cleaned_questions = []
        seen_ids = set()

        for q in questions:
            qid = q.get('id')
            options = q.get('options', [])
            answer = q.get('answer')
            if not qid or qid in seen_ids:
                continue
            if not isinstance(options, list) or len(options) != 4:
                continue
            if not isinstance(answer, int) or answer < 0 or answer > 3:
                continue
            cleaned_questions.append(q)
            seen_ids.add(qid)

        expanded_bank[subject] = _build_auto_exam_questions(subject, cleaned_questions, target_count)

    return expanded_bank


EXAM_QUESTION_BANK = build_large_exam_question_bank(EXAM_QUESTION_BANK)

SUBJECT_ALIASES_FOR_EXAMS = {
    'Math': 'Mathematics',
    'Maths': 'Mathematics',
    'Programming': 'Computer Science',
    'Data Structures': 'Computer Science',
    'Algorithms': 'Computer Science',
    'DBMS': 'Computer Science',
    'Operating Systems': 'Computer Science',
    'Computer Networks': 'Computer Science',
    'Web Development': 'Computer Science',
    'Artificial Intelligence': 'Computer Science',
    'Machine Learning': 'Computer Science',
    'Physics': 'Science',
    'Chemistry': 'Science',
    'Biology': 'Science',
}


def resolve_exam_subject(subject):
    cleaned = (subject or '').strip()
    if cleaned in EXAM_QUESTION_BANK:
        return cleaned
    return SUBJECT_ALIASES_FOR_EXAMS.get(cleaned)

HOMEWORK_TITLE_BY_SUBJECT = {
    'Mathematics': 'Solve Practice Problems',
    'Math': 'Solve Practice Problems',
    'Computer Science': 'Write Code Exercise',
    'Programming': 'Write Code Exercise',
    'Data Structures': 'Write Code Exercise',
    'Algorithms': 'Write Code Exercise',
    'Science': 'Revise Concepts',
    'Physics': 'Revise Concepts',
    'Chemistry': 'Revise Concepts',
    'Biology': 'Revise Concepts',
    'English': 'Read and Summarize Chapter',
    'History': 'Prepare Revision Notes',
}

HOMEWORK_TOPICS_BY_SUBJECT = {
    'Mathematics': ['Algebra Problems', 'Trigonometry Practice', 'Calculus Basics'],
    'Math': ['Algebra Problems', 'Trigonometry Practice', 'Calculus Basics'],
    'Computer Science': ['Python Loops Practice', 'Data Structures - Stack', 'DBMS Normalization'],
    'Science': ['Newton Laws Revision', 'Periodic Table Study', 'Chemical Reactions'],
    'English': ['Essay Writing', 'Grammar Practice', 'Comprehension Reading'],
    'Physics': ['Laws of Motion Practice', 'Work-Energy Numericals', 'Current Electricity Revision'],
    'Chemistry': ['Periodic Trends Practice', 'Balancing Reactions', 'Organic Naming Drill'],
    'Biology': ['Cell Structure Revision', 'Genetics Question Set', 'Human Physiology Notes'],
}

HARD_SUBJECTS = {
    'Mathematics', 'Math', 'Physics', 'Chemistry', 'Biology', 'Computer Science',
    'Programming', 'Data Structures', 'Algorithms', 'Operating Systems',
    'Computer Networks', 'DBMS', 'Machine Learning', 'Artificial Intelligence'
}

MEDIUM_SUBJECTS = {
    'Science', 'Economics', 'Accountancy', 'Business Studies', 'Geography',
    'History', 'Civics', 'Social Science', 'English'
}


def get_topics_for_subject(subject):
    """Return configured topics for a subject, or sensible fallback topics."""
    configured = SUBJECT_TOPICS.get(subject)
    if configured:
        return configured
    return [
        f'{subject} Fundamentals',
        f'{subject} Problem Solving',
        f'{subject} Revision',
        f'{subject} Previous Year Questions',
        f'{subject} Practice Session',
    ]


def get_homework_title_suggestion(subject):
    cleaned = (subject or '').strip()
    if not cleaned:
        return 'Complete Assigned Homework'
    if cleaned in HOMEWORK_TITLE_BY_SUBJECT:
        return HOMEWORK_TITLE_BY_SUBJECT[cleaned]
    return f'Revise {cleaned} Concepts'


def get_homework_topics_for_subject(subject):
    cleaned = (subject or '').strip()
    if not cleaned:
        return []

    explicit_topics = HOMEWORK_TOPICS_BY_SUBJECT.get(cleaned)
    if explicit_topics:
        return explicit_topics

    base_topics = get_topics_for_subject(cleaned)
    if base_topics:
        trimmed = [t.strip() for t in base_topics[:6] if t and t.strip()]
        if trimmed:
            return [
                f'Practice {trimmed[0]}',
                f'Revise {trimmed[1] if len(trimmed) > 1 else trimmed[0]}',
                f'Solve {trimmed[2] if len(trimmed) > 2 else trimmed[0]} Questions',
            ]

    return [
        f'Practice {cleaned} Fundamentals',
        f'Revise {cleaned} Concepts',
        f'Solve {cleaned} Chapter Questions',
    ]


def generate_homework_topic_title(subject, last_title=None):
    topics = get_homework_topics_for_subject(subject)
    if not topics:
        return get_homework_title_suggestion(subject)

    filtered = [topic for topic in topics if topic != (last_title or '').strip()]
    pool = filtered if filtered else topics
    return random.choice(pool)


def get_subject_priority(subject):
    cleaned = (subject or '').strip()
    if cleaned in HARD_SUBJECTS:
        return 'high'
    if cleaned in MEDIUM_SUBJECTS:
        return 'medium'
    return 'low'


def normalize_priority(priority):
    cleaned = (priority or '').strip().lower()
    return cleaned if cleaned in ('low', 'medium', 'high') else 'medium'


def get_auto_due_date(priority):
    p = normalize_priority(priority)
    if p == 'high':
        return (date.today() + timedelta(days=1)).isoformat()
    if p == 'medium':
        return (date.today() + timedelta(days=3)).isoformat()
    return (date.today() + timedelta(days=5)).isoformat()


def apply_homework_deadline_penalties(user_id):
    """Apply one-time XP penalty when deadline is missed and mark active tasks as overdue."""
    conn = get_db_connection()
    today_iso = date.today().isoformat()

    overdue_rows = conn.execute(
        '''
        SELECT id, penalty_applied FROM homework
        WHERE user_id = ? AND status != 'completed' AND due_date < ?
        ''',
        (user_id, today_iso)
    ).fetchall()

    penalty_count = 0
    for row in overdue_rows:
        if (row['penalty_applied'] or 0) == 0:
            conn.execute('UPDATE users SET xp_points = xp_points - 10 WHERE id = ?', (user_id,))
            conn.execute(
                "UPDATE homework SET penalty_applied = 1, deadline_status = 'overdue' WHERE id = ?",
                (row['id'],)
            )
            penalty_count += 1
        else:
            conn.execute("UPDATE homework SET deadline_status = 'overdue' WHERE id = ?", (row['id'],))

    conn.commit()
    conn.close()
    return penalty_count


def apply_streak_decay_if_missed(user_id):
    """Reset streak to 0 when at least one day is missed since last completion."""
    conn = get_db_connection()
    user = conn.execute('SELECT streak, last_completed_date FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return

    last_completed = (user['last_completed_date'] or '').strip()
    if not last_completed:
        conn.close()
        return

    try:
        last_date = datetime.strptime(last_completed, '%Y-%m-%d').date()
    except ValueError:
        conn.close()
        return

    today_date = date.today()
    yesterday_date = today_date - timedelta(days=1)
    if last_date < yesterday_date and (user['streak'] or 0) != 0:
        conn.execute('UPDATE users SET streak = 0 WHERE id = ?', (user_id,))
        conn.commit()

    conn.close()

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
            role TEXT DEFAULT 'student',
            is_verified INTEGER DEFAULT 1,
            verification_status TEXT DEFAULT 'verified',
            standard TEXT,
            section TEXT,
            assigned_standard TEXT,
            assigned_section TEXT,
            last_login_at TEXT,
            xp_points INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_completed_date TEXT
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
            parent_phone TEXT,
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
            status TEXT DEFAULT 'not_started',
            started_at TEXT,
            completed_at TEXT,
            xp_reward INTEGER DEFAULT 0,
            deadline_status TEXT DEFAULT 'active',
            penalty_applied INTEGER DEFAULT 0,
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            student_id INTEGER,
            exam_id TEXT,
            class_id INTEGER,
            teacher_id INTEGER,
            timestamp TEXT,
            subject TEXT NOT NULL,
            exam_session_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            time_taken_seconds INTEGER,
            details_json TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            class_id INTEGER,
            section TEXT,
            subject TEXT,
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            class_id INTEGER,
            section TEXT,
            teacher_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS teacher_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            proof_file TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            submitted_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by INTEGER,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(reviewed_by) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            material_type TEXT NOT NULL,
            file_path TEXT,
            video_link TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_key TEXT NOT NULL,
            subject TEXT NOT NULL,
            teacher_id INTEGER,
            total_marks INTEGER DEFAULT 50,
            created_at TEXT NOT NULL,
            UNIQUE(week_key, subject),
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_test_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            question_id TEXT NOT NULL,
            marks INTEGER DEFAULT 5,
            UNIQUE(test_id, question_id),
            FOREIGN KEY(test_id) REFERENCES weekly_tests(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            exam_session_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            obtained_marks INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            answer_json TEXT,
            submitted_at TEXT NOT NULL,
            UNIQUE(user_id, test_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(test_id) REFERENCES weekly_tests(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS test_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            teacher_id INTEGER,
            test_id INTEGER,
            event_type TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(test_id) REFERENCES weekly_tests(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER,
            class_id INTEGER,
            section TEXT,
            test_id INTEGER,
            exam_session_id TEXT,
            violation_type TEXT NOT NULL,
            score_delta INTEGER DEFAULT 0,
            suspicion_score INTEGER DEFAULT 0,
            is_high_risk INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(test_id) REFERENCES weekly_tests(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            violation_id INTEGER,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(violation_id) REFERENCES violations(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard TEXT NOT NULL,
            section TEXT NOT NULL,
            class_teacher_id INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(standard, section),
            FOREIGN KEY(class_teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS teacher_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            UNIQUE(teacher_id, student_id),
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER,
            action_type TEXT NOT NULL,
            subject TEXT,
            description TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            class_id INTEGER,
            teacher_id INTEGER,
            subject TEXT,
            timestamp TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            class_id INTEGER,
            section TEXT,
            subject TEXT NOT NULL,
            total_marks INTEGER DEFAULT 50,
            duration INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            is_published INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            marks INTEGER DEFAULT 1,
            FOREIGN KEY(exam_id) REFERENCES school_exams(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(exam_id) REFERENCES school_exams(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answer TEXT NOT NULL,
            FOREIGN KEY(attempt_id) REFERENCES school_exam_attempts(id),
            FOREIGN KEY(question_id) REFERENCES school_questions(id)
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
    if 'xp_points' not in column_names:
        c.execute('ALTER TABLE users ADD COLUMN xp_points INTEGER DEFAULT 0')
        conn.commit()
    if 'streak' not in column_names:
        c.execute('ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0')
        conn.commit()
    if 'last_completed_date' not in column_names:
        c.execute('ALTER TABLE users ADD COLUMN last_completed_date TEXT')
        conn.commit()
    if 'role' not in column_names:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'student'")
        conn.commit()
    if 'is_verified' not in column_names:
        c.execute('ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 1')
        conn.commit()
    if 'verification_status' not in column_names:
        c.execute("ALTER TABLE users ADD COLUMN verification_status TEXT DEFAULT 'verified'")
        conn.commit()
    for col, coltype in [
        ('standard', 'TEXT'),
        ('section', 'TEXT'),
        ('assigned_standard', 'TEXT'),
        ('assigned_section', 'TEXT')
    ]:
        if col not in column_names:
            c.execute(f'ALTER TABLE users ADD COLUMN {col} {coltype}')
            conn.commit()
    # student_profile table — add school-specific columns
    sp_cols = c.execute('PRAGMA table_info(student_profile)').fetchall()
    sp_col_names = {row['name'] for row in sp_cols}
    for col, coltype in [
        ('grade', 'TEXT'), ('section', 'TEXT'), ('board', 'TEXT'),
        ('parent_email', 'TEXT'), ('student_type', "TEXT DEFAULT 'college'"),
        ('parent_phone', 'TEXT')
    ]:
        if col not in sp_col_names:
            c.execute(f'ALTER TABLE student_profile ADD COLUMN {col} {coltype}')
    conn.commit()
    # ensure homework and exams tables exist (for DBs created before this feature)
    c.execute('''CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        title TEXT NOT NULL, subject TEXT NOT NULL, due_date TEXT NOT NULL,
        priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'not_started',
        started_at TEXT, completed_at TEXT, xp_reward INTEGER DEFAULT 0,
        deadline_status TEXT DEFAULT 'active', penalty_applied INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))''')
    hw_cols = c.execute('PRAGMA table_info(homework)').fetchall()
    hw_col_names = {row['name'] for row in hw_cols}
    for col, coltype in [
        ('started_at', 'TEXT'),
        ('completed_at', 'TEXT'),
        ('xp_reward', 'INTEGER DEFAULT 0'),
        ('deadline_status', "TEXT DEFAULT 'active'"),
        ('penalty_applied', 'INTEGER DEFAULT 0')
    ]:
        if col not in hw_col_names:
            c.execute(f'ALTER TABLE homework ADD COLUMN {col} {coltype}')

    if 'status' in hw_col_names:
        c.execute("UPDATE homework SET status = 'not_started' WHERE status = 'pending'")
        c.execute("UPDATE homework SET status = 'completed' WHERE status = 'done'")

    c.execute(
        "UPDATE homework SET deadline_status = 'overdue' WHERE status != 'completed' AND due_date < DATE('now')"
    )
    c.execute(
        "UPDATE homework SET deadline_status = 'active' WHERE status != 'completed' AND due_date >= DATE('now') AND (deadline_status IS NULL OR deadline_status != 'overdue')"
    )
    c.execute('''CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        name TEXT NOT NULL, subject TEXT NOT NULL, exam_date TEXT NOT NULL,
        exam_type TEXT DEFAULT 'exam', topics TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS exam_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        student_id INTEGER,
        exam_id TEXT,
        class_id INTEGER,
        teacher_id INTEGER,
        timestamp TEXT,
        subject TEXT NOT NULL,
        exam_session_id TEXT NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        time_taken_seconds INTEGER,
        details_json TEXT,
        submitted_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
        teacher_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        class_id INTEGER,
        section TEXT,
        subject TEXT,
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        class_id INTEGER,
        section TEXT,
        teacher_id INTEGER,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id))''')

    exam_attempt_cols = c.execute('PRAGMA table_info(exam_attempts)').fetchall()
    exam_attempt_col_names = {row['name'] for row in exam_attempt_cols}
    for col, coltype in [
        ('student_id', 'INTEGER'),
        ('exam_id', 'TEXT'),
        ('class_id', 'INTEGER'),
        ('teacher_id', 'INTEGER'),
        ('timestamp', 'TEXT')
    ]:
        if col not in exam_attempt_col_names:
            c.execute(f'ALTER TABLE exam_attempts ADD COLUMN {col} {coltype}')

    teacher_cols = c.execute('PRAGMA table_info(teachers)').fetchall()
    teacher_col_names = {row['name'] for row in teacher_cols}
    for col, coltype in [
        ('class_id', 'INTEGER'),
        ('section', 'TEXT'),
        ('subject', 'TEXT')
    ]:
        if col not in teacher_col_names:
            c.execute(f'ALTER TABLE teachers ADD COLUMN {col} {coltype}')

    c.execute('''CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER,
        class_id INTEGER,
        section TEXT,
        test_id INTEGER,
        exam_session_id TEXT,
        violation_type TEXT NOT NULL,
        score_delta INTEGER DEFAULT 0,
        suspicion_score INTEGER DEFAULT 0,
        is_high_risk INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL,
        details TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(test_id) REFERENCES weekly_tests(id))''')
    violation_cols = c.execute('PRAGMA table_info(violations)').fetchall()
    violation_col_names = {row['name'] for row in violation_cols}
    for col, coltype in [
        ('student_id', 'INTEGER'),
        ('teacher_id', 'INTEGER'),
        ('class_id', 'INTEGER'),
        ('section', 'TEXT'),
        ('test_id', 'INTEGER'),
        ('exam_session_id', 'TEXT'),
        ('violation_type', 'TEXT'),
        ('score_delta', 'INTEGER DEFAULT 0'),
        ('suspicion_score', 'INTEGER DEFAULT 0'),
        ('is_high_risk', 'INTEGER DEFAULT 0'),
        ('timestamp', 'TEXT'),
        ('details', 'TEXT')
    ]:
        if col not in violation_col_names:
            c.execute(f'ALTER TABLE violations ADD COLUMN {col} {coltype}')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        violation_id INTEGER,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(violation_id) REFERENCES violations(id))''')
    notification_cols = c.execute('PRAGMA table_info(notifications)').fetchall()
    notification_col_names = {row['name'] for row in notification_cols}
    for col, coltype in [
        ('teacher_id', 'INTEGER'),
        ('violation_id', 'INTEGER'),
        ('message', 'TEXT'),
        ('is_read', 'INTEGER DEFAULT 0'),
        ('timestamp', 'TEXT')
    ]:
        if col not in notification_col_names:
            c.execute(f'ALTER TABLE notifications ADD COLUMN {col} {coltype}')
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_verification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        proof_file TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        submitted_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by INTEGER,
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(reviewed_by) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS study_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        material_type TEXT NOT NULL,
        file_path TEXT,
        video_link TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(teacher_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_key TEXT NOT NULL,
        subject TEXT NOT NULL,
        teacher_id INTEGER,
        total_marks INTEGER DEFAULT 50,
        created_at TEXT NOT NULL,
        UNIQUE(week_key, subject),
        FOREIGN KEY(teacher_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_test_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question_id TEXT NOT NULL,
        marks INTEGER DEFAULT 5,
        UNIQUE(test_id, question_id),
        FOREIGN KEY(test_id) REFERENCES weekly_tests(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        test_id INTEGER NOT NULL,
        exam_session_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        obtained_marks INTEGER NOT NULL,
        total_marks INTEGER NOT NULL,
        answer_json TEXT,
        submitted_at TEXT NOT NULL,
        UNIQUE(user_id, test_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(test_id) REFERENCES weekly_tests(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS test_violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        teacher_id INTEGER,
        test_id INTEGER,
        event_type TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(test_id) REFERENCES weekly_tests(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        standard TEXT NOT NULL,
        section TEXT NOT NULL,
        class_teacher_id INTEGER,
        created_at TEXT NOT NULL,
        UNIQUE(standard, section),
        FOREIGN KEY(class_teacher_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        assigned_at TEXT NOT NULL,
        UNIQUE(teacher_id, student_id),
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(student_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS student_activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        class_id INTEGER,
        action_type TEXT NOT NULL,
        subject TEXT,
        description TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        class_id INTEGER,
        teacher_id INTEGER,
        subject TEXT,
        timestamp TEXT NOT NULL,
        details TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id))''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS school_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            class_id INTEGER,
            section TEXT,
            subject TEXT NOT NULL,
            total_marks INTEGER DEFAULT 50,
            duration INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            is_published INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(class_id) REFERENCES classes(id))''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            part TEXT NOT NULL, -- PART1, PART2, PART3, PART4
            question_text TEXT NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_answer TEXT,
            marks INTEGER DEFAULT 1,
            either_group_id INTEGER, -- For PART4 pairing
            FOREIGN KEY(exam_id) REFERENCES school_exams(id))''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(exam_id) REFERENCES school_exams(id))''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS school_student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answer TEXT NOT NULL,
            FOREIGN KEY(attempt_id) REFERENCES school_exam_attempts(id),
            FOREIGN KEY(question_id) REFERENCES school_questions(id))''')

    school_exam_cols = c.execute('PRAGMA table_info(school_exams)').fetchall()
    school_exam_col_names = {row['name'] for row in school_exam_cols}
    if 'is_published' not in school_exam_col_names:
        c.execute('ALTER TABLE school_exams ADD COLUMN is_published INTEGER DEFAULT 0')

    activity_cols = c.execute('PRAGMA table_info(student_activity_logs)').fetchall()
    activity_col_names = {row['name'] for row in activity_cols}
    if 'class_id' not in activity_col_names:
        c.execute('ALTER TABLE student_activity_logs ADD COLUMN class_id INTEGER')
    if 'subject' not in activity_col_names:
        c.execute('ALTER TABLE student_activity_logs ADD COLUMN subject TEXT')

    activities_cols = c.execute('PRAGMA table_info(activities)').fetchall()
    activities_col_names = {row['name'] for row in activities_cols}
    for col, coltype in [
        ('student_id', 'INTEGER'),
        ('action', 'TEXT'),
        ('class_id', 'INTEGER'),
        ('teacher_id', 'INTEGER'),
        ('subject', 'TEXT'),
        ('timestamp', 'TEXT'),
        ('details', 'TEXT')
    ]:
        if col not in activities_col_names:
            c.execute(f'ALTER TABLE activities ADD COLUMN {col} {coltype}')

    # Backfill class-section fields in users from student_profile for existing students.
    c.execute('''
        UPDATE users
        SET standard = (
            SELECT sp.grade FROM student_profile sp WHERE sp.user_id = users.id
        )
        WHERE role IN ('student', 'college_student')
          AND (standard IS NULL OR TRIM(standard) = '')
          AND EXISTS (SELECT 1 FROM student_profile sp2 WHERE sp2.user_id = users.id)
    ''')
    c.execute('''
        UPDATE users
        SET section = (
            SELECT sp.section FROM student_profile sp WHERE sp.user_id = users.id
        )
        WHERE role IN ('student', 'college_student')
          AND (section IS NULL OR TRIM(section) = '')
          AND EXISTS (SELECT 1 FROM student_profile sp2 WHERE sp2.user_id = users.id)
    ''')

    # Keep student-teacher mapping in sync from assigned class teacher settings.
    c.execute(
        '''
        INSERT OR IGNORE INTO teacher_students (teacher_id, student_id, assigned_at)
        SELECT t.id, s.id, ?
        FROM users t
        JOIN users s
          ON TRIM(COALESCE(t.assigned_standard, '')) = TRIM(COALESCE(s.standard, ''))
         AND TRIM(COALESCE(t.assigned_section, '')) = TRIM(COALESCE(s.section, ''))
        WHERE t.role = 'teacher'
          AND s.role IN ('student', 'college_student')
          AND TRIM(COALESCE(t.assigned_standard, '')) != ''
          AND TRIM(COALESCE(t.assigned_section, '')) != ''
        ''',
        (datetime.now().isoformat(),)
    )

    # Ensure classes table has rows for existing class/section combinations.
    class_rows = c.execute(
        '''
        SELECT DISTINCT
            TRIM(COALESCE(s.standard, '')) AS standard,
            UPPER(TRIM(COALESCE(s.section, ''))) AS section,
            (
                SELECT t.id
                FROM users t
                WHERE t.role = 'teacher'
                  AND TRIM(COALESCE(t.assigned_standard, '')) = TRIM(COALESCE(s.standard, ''))
                  AND UPPER(TRIM(COALESCE(t.assigned_section, ''))) = UPPER(TRIM(COALESCE(s.section, '')))
                ORDER BY t.id ASC
                LIMIT 1
            ) AS class_teacher_id
        FROM users s
        WHERE s.role IN ('student', 'college_student')
          AND TRIM(COALESCE(s.standard, '')) != ''
          AND TRIM(COALESCE(s.section, '')) != ''
        '''
    ).fetchall()
    for row in class_rows:
        c.execute(
            '''
            INSERT INTO classes (standard, section, class_teacher_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(standard, section)
            DO UPDATE SET class_teacher_id = COALESCE(excluded.class_teacher_id, classes.class_teacher_id)
            ''',
            (row['standard'], row['section'], row['class_teacher_id'], datetime.now().isoformat())
        )

    c.execute(
        '''
        INSERT INTO teachers (teacher_id, name, class_id, section, subject)
        SELECT
            t.id,
            t.username,
            cls.id,
            UPPER(TRIM(COALESCE(t.assigned_section, ''))),
            COALESCE(tr.subject, '')
        FROM users t
        LEFT JOIN classes cls
          ON cls.standard = TRIM(COALESCE(t.assigned_standard, ''))
         AND cls.section = UPPER(TRIM(COALESCE(t.assigned_section, '')))
        LEFT JOIN teachers tr ON tr.teacher_id = t.id
        WHERE t.role = 'teacher'
        ON CONFLICT(teacher_id) DO UPDATE SET
            name = excluded.name,
            class_id = excluded.class_id,
            section = excluded.section,
            subject = COALESCE(NULLIF(excluded.subject, ''), teachers.subject)
        '''
    )

    c.execute(
        '''
        INSERT OR REPLACE INTO students (student_id, name, class_id, section, teacher_id)
        SELECT
            s.id,
            s.username,
            cls.id,
            UPPER(TRIM(COALESCE(s.section, ''))),
            (
                SELECT ts.teacher_id
                FROM teacher_students ts
                WHERE ts.student_id = s.id
                ORDER BY ts.id ASC
                LIMIT 1
            )
        FROM users s
        LEFT JOIN classes cls
          ON cls.standard = TRIM(COALESCE(s.standard, ''))
         AND cls.section = UPPER(TRIM(COALESCE(s.section, '')))
        WHERE s.role IN ('student', 'college_student')
        '''
    )

    c.execute(
        '''
        UPDATE exam_attempts
        SET student_id = user_id
        WHERE student_id IS NULL
        '''
    )

    c.execute(
        '''
        UPDATE exam_attempts
        SET exam_id = exam_session_id
        WHERE (exam_id IS NULL OR TRIM(exam_id) = '')
        '''
    )

    c.execute(
        '''
        UPDATE exam_attempts
        SET timestamp = submitted_at
        WHERE (timestamp IS NULL OR TRIM(timestamp) = '')
        '''
    )

    c.execute(
        '''
        UPDATE exam_attempts
        SET class_id = (
            SELECT st.class_id FROM students st WHERE st.student_id = exam_attempts.student_id
        )
        WHERE class_id IS NULL
        '''
    )

    c.execute(
        '''
        UPDATE exam_attempts
        SET teacher_id = (
            SELECT st.teacher_id FROM students st WHERE st.student_id = exam_attempts.student_id
        )
        WHERE teacher_id IS NULL
        '''
    )

    c.execute(
        '''
        INSERT INTO activities (student_id, action, class_id, teacher_id, subject, timestamp, details)
        SELECT
            sal.student_id,
            sal.action_type,
            sal.class_id,
            (
                SELECT st.teacher_id
                FROM students st
                WHERE st.student_id = sal.student_id
                LIMIT 1
            ) AS teacher_id,
            sal.subject,
            sal.timestamp,
            sal.description
        FROM student_activity_logs sal
        WHERE NOT EXISTS (
            SELECT 1
            FROM activities a
            WHERE a.student_id = sal.student_id
              AND a.action = sal.action_type
              AND COALESCE(a.timestamp, '') = COALESCE(sal.timestamp, '')
              AND COALESCE(a.details, '') = COALESCE(sal.description, '')
        )
        '''
    )

    # Backfill missing class_id for old activity logs.
    pending_activity_rows = c.execute(
        '''
        SELECT sal.id,
               TRIM(COALESCE(u.standard, '')) AS standard,
               UPPER(TRIM(COALESCE(u.section, ''))) AS section
        FROM student_activity_logs sal
        JOIN users u ON u.id = sal.student_id
        WHERE sal.class_id IS NULL
        '''
    ).fetchall()
    for row in pending_activity_rows:
        if not row['standard'] or not row['section']:
            continue
        class_row = c.execute(
            'SELECT id FROM classes WHERE standard = ? AND section = ? LIMIT 1',
            (row['standard'], row['section'])
        ).fetchone()
        if class_row:
            c.execute(
                'UPDATE student_activity_logs SET class_id = ? WHERE id = ?',
                (class_row['id'], row['id'])
            )

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


def current_user_role(user=None):
    selected_user = user or current_user()
    if not selected_user:
        return 'student'
    role = (selected_user['role'] or 'student').strip().lower() if 'role' in selected_user.keys() else 'student'
    return role if role in ('student', 'college_student', 'teacher', 'admin') else 'student'


def is_admin_user(user=None):
    selected_user = user or current_user()
    if not selected_user:
        return False
    return current_user_role(selected_user) == 'admin' or (selected_user['username'] or '').strip().lower() == 'admin'


def is_teacher_approved(user_id):
    if not TEACHER_VERIFICATION_ENABLED:
        return True

    conn = get_db_connection()
    row = conn.execute(
        'SELECT is_verified, verification_status FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return False
    return int(row['is_verified'] or 0) == 1 and (row['verification_status'] or '').strip().lower() == 'verified'


def get_teacher_verification_status(user_id):
    if not TEACHER_VERIFICATION_ENABLED:
        return 'verified'

    conn = get_db_connection()
    row = conn.execute(
        'SELECT verification_status FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    conn.close()
    return (row['verification_status'] or 'not_submitted') if row else 'not_submitted'


def get_current_week_key():
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f'{iso_year}-W{iso_week:02d}'


def role_required(allowed_roles):
    from functools import wraps

    allowed = set((allowed_roles or []))

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash('Please login first', 'warning')
                return redirect(url_for('login'))
            role = current_user_role(user)
            if role not in allowed:
                flash('Access denied for this role.', 'danger')
                return redirect(url_for('dashboard'))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def log_activity(student_id, action_type, description='', subject=''):
    if not student_id or not action_type:
        return
    action_aliases = {
        'subject_selection': 'subject_selected',
        'create_homework': 'add_homework',
        'start_homework': 'start_task',
        'complete_homework': 'complete_task',
        'exam_violation': 'tab_switch_detected',
        'start_weekly_test': 'weekly_test_started',
        'submit_weekly_test': 'weekly_test_submitted',
        'start_exam': 'start_exam',
        'submit_exam': 'submit_exam',
        'login': 'login',
        'logout': 'logout',
        'focus_session_started': 'focus_started',
        'focus_session_completed': 'focus_completed',
        'focus_session_stopped': 'focus_stopped',
    }
    normalized_action = action_aliases.get((action_type or '').strip(), (action_type or '').strip())
    cleaned_subject = (subject or '').strip()

    conn = get_db_connection()
    class_id, teacher_id = _resolve_student_exam_context(conn, student_id)
    
    # IMPORTANT: If teacher_id is NULL, still attempt to resolve but NEVER skip logging
    if teacher_id is None:
        print(f'[WARNING] Activity: student_id={student_id} has NO teacher mapping. Attempting re-sync...')
        # Force re-sync and retry fetch
        _sync_teacher_students_for_student(conn, student_id)
        row = conn.execute(
            'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
            (student_id,)
        ).fetchone()
        class_id = row['class_id'] if row else class_id
        teacher_id = row['teacher_id'] if row else None
        if teacher_id is None:
            print(f'[WARNING] Activity: student_id={student_id} still has NO teacher_id after sync. Logging with NULL teacher_id.')
    
    conn.execute(
        '''
        INSERT INTO student_activity_logs (student_id, class_id, action_type, subject, description, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (student_id, class_id, normalized_action, cleaned_subject, (description or '').strip(), datetime.now().isoformat())
    )
    conn.execute(
        '''
        INSERT INTO activities (student_id, action, class_id, teacher_id, subject, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            student_id,
            normalized_action,
            class_id,
            teacher_id,
            cleaned_subject,
            datetime.now().isoformat(),
            (description or '').strip(),
        )
    )
    conn.commit()
    print(
        f'[DEBUG Activity] ✓ Logged: student_id={student_id} teacher_id={teacher_id} class_id={class_id} '
        f'action={normalized_action} subject={cleaned_subject}'
    )
    conn.close()


def _record_exam_attempt(
    conn,
    student_id,
    exam_id,
    subject,
    score,
    total_questions,
    time_taken_seconds,
    details_json,
    submitted_at=None,
):
    timestamp_value = submitted_at or datetime.now().isoformat()
    class_id, teacher_id = _resolve_student_exam_context(conn, student_id)

    # IMPORTANT: If teacher_id is NULL, still attempt to resolve but NEVER skip the insert
    if teacher_id is None:
        print(f'[WARNING] Exam: student_id={student_id} exam_id={exam_id} has NO teacher mapping. Attempting re-sync...')
        # Force re-sync and retry fetch
        _sync_teacher_students_for_student(conn, student_id)
        row = conn.execute(
            'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
            (student_id,)
        ).fetchone()
        class_id = row['class_id'] if row else class_id
        teacher_id = row['teacher_id'] if row else None
        if teacher_id is None:
            print(f'[WARNING] Exam: student_id={student_id} exam_id={exam_id} still has NO teacher_id after sync. Inserting with NULL teacher_id.')

    conn.execute(
        '''
        INSERT INTO exam_attempts (
            user_id,
            student_id,
            exam_id,
            class_id,
            teacher_id,
            timestamp,
            subject,
            exam_session_id,
            score,
            total_questions,
            time_taken_seconds,
            details_json,
            submitted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            student_id,
            student_id,
            str(exam_id or ''),
            class_id,
            teacher_id,
            timestamp_value,
            (subject or '').strip(),
            str(exam_id or ''),
            int(score or 0),
            int(total_questions or 0),
            time_taken_seconds,
            details_json,
            timestamp_value,
        ),
    )

    print(
        f'[DEBUG Exam] ✓ Recorded: student_id={student_id} teacher_id={teacher_id} class_id={class_id} '
        f'exam_id={exam_id} subject={subject} score={score}/{total_questions}'
    )

    return class_id, teacher_id


def get_assigned_student_ids(teacher_id):
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT student_id FROM teacher_students WHERE teacher_id = ?',
        (teacher_id,)
    ).fetchall()
    conn.close()
    return [row['student_id'] for row in rows]


def _clean_class_value(value):
    return (value or '').strip()


def _clean_section_value(value):
    return (value or '').strip().upper()


def _ensure_class_record(conn, standard, section, class_teacher_id=None):
    cleaned_standard = _clean_class_value(standard)
    cleaned_section = _clean_section_value(section)
    if not cleaned_standard or not cleaned_section:
        return None

    existing = conn.execute(
        'SELECT id, class_teacher_id FROM classes WHERE standard = ? AND section = ? LIMIT 1',
        (cleaned_standard, cleaned_section)
    ).fetchone()
    if existing:
        if class_teacher_id and existing['class_teacher_id'] != class_teacher_id:
            conn.execute(
                'UPDATE classes SET class_teacher_id = ? WHERE id = ?',
                (class_teacher_id, existing['id'])
            )
        return existing['id']

    cur = conn.execute(
        '''
        INSERT INTO classes (standard, section, class_teacher_id, created_at)
        VALUES (?, ?, ?, ?)
        ''',
        (cleaned_standard, cleaned_section, class_teacher_id, datetime.now().isoformat())
    )
    return cur.lastrowid


def _upsert_teacher_record(conn, teacher_id, subject_override=None):
    if not teacher_id:
        return
    teacher = conn.execute(
        '''
        SELECT id, username, assigned_standard, assigned_section
        FROM users
        WHERE id = ? AND role = 'teacher'
        ''',
        (teacher_id,)
    ).fetchone()
    if not teacher:
        return
    # Resolve class_id from the teacher's assigned standard/section
    t_standard = _clean_class_value(teacher['assigned_standard'])
    t_section = _clean_section_value(teacher['assigned_section'])
    class_id = None
    if t_standard and t_section:
        class_row = conn.execute(
            'SELECT id FROM classes WHERE standard = ? AND section = ? LIMIT 1',
            (t_standard, t_section)
        ).fetchone()
        class_id = class_row['id'] if class_row else None
    existing_teacher_row = conn.execute(
        'SELECT subject FROM teachers WHERE teacher_id = ? LIMIT 1',
        (teacher_id,)
    ).fetchone()
    subject_value = (subject_override or '').strip()
    if not subject_value and existing_teacher_row:
        subject_value = (existing_teacher_row['subject'] or '').strip()

    conn.execute(
        '''
        INSERT INTO teachers (teacher_id, name, class_id, section, subject)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(teacher_id) DO UPDATE SET
            name = excluded.name,
            class_id = excluded.class_id,
            section = excluded.section,
            subject = excluded.subject
        ''',
        (teacher['id'], teacher['username'], class_id, t_section, subject_value)
    )


def _upsert_student_record(conn, student_id, class_id=None, teacher_id=None):
    student = conn.execute(
        '''
        SELECT id, username, standard, section
        FROM users
        WHERE id = ? AND role IN ('student', 'college_student')
        ''',
        (student_id,)
    ).fetchone()
    if not student:
        return

    section = _clean_section_value(student['section'])
    if class_id is None:
        class_row = conn.execute(
            '''
            SELECT id
            FROM classes
            WHERE standard = ? AND section = ?
            LIMIT 1
            ''',
            (_clean_class_value(student['standard']), section)
        ).fetchone()
        class_id = class_row['id'] if class_row else None

    if teacher_id is None:
        teacher_row = conn.execute(
            'SELECT teacher_id FROM teacher_students WHERE student_id = ? ORDER BY id ASC LIMIT 1',
            (student_id,)
        ).fetchone()
        teacher_id = teacher_row['teacher_id'] if teacher_row else None

    if teacher_id is None and class_id is not None and section:
        teacher_row = conn.execute(
            '''
            SELECT teacher_id
            FROM teachers
            WHERE class_id = ?
              AND UPPER(TRIM(COALESCE(section, ''))) = ?
            ORDER BY teacher_id ASC
            LIMIT 1
            ''',
            (class_id, section)
        ).fetchone()
        teacher_id = teacher_row['teacher_id'] if teacher_row else None

    conn.execute(
        '''
        INSERT OR REPLACE INTO students (student_id, name, class_id, section, teacher_id)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (student['id'], student['username'], class_id, section, teacher_id)
    )


def _resolve_student_exam_context(conn, student_id):
    class_id = _sync_teacher_students_for_student(conn, student_id)
    row = conn.execute(
        'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
        (student_id,)
    ).fetchone()

    resolved_class_id = row['class_id'] if row and row['class_id'] is not None else class_id
    resolved_teacher_id = row['teacher_id'] if row else None

    if resolved_teacher_id is None:
        teacher_row = conn.execute(
            'SELECT teacher_id FROM teacher_students WHERE student_id = ? ORDER BY id ASC LIMIT 1',
            (student_id,)
        ).fetchone()
        resolved_teacher_id = teacher_row['teacher_id'] if teacher_row else None

    if resolved_teacher_id is None and resolved_class_id is not None:
        class_row = conn.execute('SELECT class_teacher_id FROM classes WHERE id = ?', (resolved_class_id,)).fetchone()
        resolved_teacher_id = class_row['class_teacher_id'] if class_row else None

    _upsert_student_record(conn, student_id, class_id=resolved_class_id, teacher_id=resolved_teacher_id)
    return resolved_class_id, resolved_teacher_id


def _sync_teacher_students_for_student(conn, student_id):
    student = conn.execute(
        '''
        SELECT id, standard, section
        FROM users
        WHERE id = ? AND role IN ('student', 'college_student')
        ''',
        (student_id,)
    ).fetchone()
    if not student:
        return None

    student_standard = _clean_class_value(student['standard'])
    student_section = _clean_section_value(student['section'])

    # If the student has no standard/section yet, preserve any EXISTING mapping
    # instead of destructively deleting it. Only recreate when we have real data.
    if not student_standard or not student_section:
        print(f'[DEBUG Sync] student_id={student_id} has no standard/section — preserving existing mapping')
        # Still ensure student record exists
        _upsert_student_record(conn, student_id)
        return None

    class_id = _ensure_class_record(conn, student_standard, student_section)

    # Only delete+recreate when we have both standard AND section to match on
    conn.execute('DELETE FROM teacher_students WHERE student_id = ?', (student_id,))

    # Always initialize to prevent UnboundLocalError.
    teachers = []
    if class_id is not None:
        teachers = conn.execute(
            '''
            SELECT teacher_id AS id
            FROM teachers
            WHERE class_id = ?
              AND UPPER(TRIM(COALESCE(section, ''))) = ?
            ORDER BY teacher_id ASC
            ''',
            (class_id, student_section)
        ).fetchall()

    # Fallback for older data where teachers table has not been fully synced yet.
    if not teachers:
        teachers = conn.execute(
            '''
            SELECT id
            FROM users
            WHERE role = 'teacher'
              AND TRIM(COALESCE(assigned_standard, '')) = ?
              AND UPPER(TRIM(COALESCE(assigned_section, ''))) = ?
            ORDER BY id ASC
            ''',
            (student_standard, student_section)
        ).fetchall()

    for teacher in teachers:
        _upsert_teacher_record(conn, teacher['id'])
        conn.execute(
            '''
            INSERT OR IGNORE INTO teacher_students (teacher_id, student_id, assigned_at)
            VALUES (?, ?, ?)
            ''',
            (teacher['id'], student_id, datetime.now().isoformat())
        )

    class_teacher_id = teachers[0]['id'] if teachers else None
    class_id = _ensure_class_record(conn, student_standard, student_section, class_teacher_id=class_teacher_id)
    _upsert_student_record(conn, student_id, class_id=class_id, teacher_id=class_teacher_id)
    if class_teacher_id is None:
        print(f'[WARNING] Sync: no teacher mapped for student_id={student_id} standard={student_standard} section={student_section}')
    print(f'[DEBUG Sync] ✓ student_id={student_id} → teacher_id={class_teacher_id} class_id={class_id} standard={student_standard} section={student_section}')
    return class_id


def _sync_teacher_students_for_teacher(conn, teacher_id):
    teacher = conn.execute(
        '''
        SELECT id, assigned_standard, assigned_section
        FROM users
        WHERE id = ? AND role = 'teacher'
        ''',
        (teacher_id,)
    ).fetchone()
    if not teacher:
        return

    _upsert_teacher_record(conn, teacher_id)

    assigned_standard = _clean_class_value(teacher['assigned_standard'])
    assigned_section = _clean_section_value(teacher['assigned_section'])

    conn.execute('DELETE FROM teacher_students WHERE teacher_id = ?', (teacher_id,))
    if not assigned_standard or not assigned_section:
        return

    students = conn.execute(
        '''
        SELECT id
        FROM users
        WHERE role IN ('student', 'college_student')
          AND TRIM(COALESCE(standard, '')) = ?
          AND UPPER(TRIM(COALESCE(section, ''))) = ?
        ''',
        (assigned_standard, assigned_section)
    ).fetchall()

    class_id = _ensure_class_record(conn, assigned_standard, assigned_section, class_teacher_id=teacher_id)
    conn.execute(
        '''
        UPDATE teachers
        SET class_id = ?, section = ?
        WHERE teacher_id = ?
        ''',
        (class_id, assigned_section, teacher_id)
    )

    # Ensure pre-existing students are immediately linked when a teacher is created/assigned later.
    _sync_students_to_teacher(conn, teacher_id, class_id, assigned_section)

    for student in students:
        conn.execute(
            '''
            INSERT OR IGNORE INTO teacher_students (teacher_id, student_id, assigned_at)
            VALUES (?, ?, ?)
            ''',
            (teacher_id, student['id'], datetime.now().isoformat())
        )
        _upsert_student_record(conn, student['id'], class_id=class_id, teacher_id=teacher_id)


def _sync_students_to_teacher(conn, teacher_id, class_id, section):
    """Backfill students.teacher_id and teacher_students for a class-section teacher assignment."""
    cleaned_section = _clean_section_value(section)
    if not teacher_id or class_id is None or not cleaned_section:
        return 0

    conn.execute(
        '''
        UPDATE students
        SET teacher_id = ?
        WHERE class_id = ?
          AND UPPER(TRIM(COALESCE(section, ''))) = ?
        ''',
        (teacher_id, class_id, cleaned_section)
    )

    matched_students = conn.execute(
        '''
        SELECT student_id
        FROM students
        WHERE class_id = ?
          AND UPPER(TRIM(COALESCE(section, ''))) = ?
        ''',
        (class_id, cleaned_section)
    ).fetchall()

    for row in matched_students:
        sid = row['student_id']
        conn.execute('DELETE FROM teacher_students WHERE student_id = ?', (sid,))
        conn.execute(
            '''
            INSERT OR IGNORE INTO teacher_students (teacher_id, student_id, assigned_at)
            VALUES (?, ?, ?)
            ''',
            (teacher_id, sid, datetime.now().isoformat())
        )

    print(
        f'[DEBUG Sync Teacher] ✓ teacher_id={teacher_id} class_id={class_id} section={cleaned_section} '
        f'matched_students={len(matched_students)}'
    )
    return len(matched_students)


def _class_group_label(standard, section):
    class_label = _clean_class_value(standard)
    section_label = _clean_class_value(section)
    if class_label.isdigit():
        class_label = f'{class_label}th'
    if class_label and section_label:
        return f'{class_label} {section_label} Students'
    if class_label:
        return f'{class_label} Students'
    return 'Assigned Students'


def _get_teacher_visible_students(conn, teacher, section_override=''):
    teacher_standard = _clean_class_value(teacher['assigned_standard']) if 'assigned_standard' in teacher.keys() else ''
    teacher_section = _clean_section_value(teacher['assigned_section']) if 'assigned_section' in teacher.keys() else ''
    selected_section = _clean_section_value(section_override)

    teacher_meta = conn.execute(
        'SELECT class_id, section FROM teachers WHERE teacher_id = ? LIMIT 1',
        (teacher['id'],)
    ).fetchone()

    effective_section = (
        _clean_section_value(teacher_meta['section']) if teacher_meta and teacher_meta['section'] else (teacher_section or selected_section)
    )

    students = []
    if teacher_meta and teacher_meta['class_id'] is not None:
        query = '''
            SELECT u.id, u.username, u.standard, u.section
            FROM students s
            JOIN users u ON u.id = s.student_id
            WHERE s.class_id = ?
        '''
        params = [teacher_meta['class_id']]
        if effective_section:
            query += " AND UPPER(TRIM(COALESCE(s.section, ''))) = ?"
            params.append(effective_section)
        query += ' ORDER BY u.username ASC'
        students = conn.execute(query, tuple(params)).fetchall()

    if not students:
        if not teacher_standard:
            return []
        query = '''
            SELECT id, username, standard, section
            FROM users
            WHERE role IN ('student', 'college_student')
              AND TRIM(COALESCE(standard, '')) = ?
        '''
        params = [teacher_standard]
        if effective_section:
            query += " AND UPPER(TRIM(COALESCE(section, ''))) = ?"
            params.append(effective_section)
        query += ' ORDER BY username ASC'
        students = conn.execute(query, tuple(params)).fetchall()

    assigned_student_ids = set(get_assigned_student_ids(teacher['id']))
    if assigned_student_ids:
        students = [student for student in students if student['id'] in assigned_student_ids]

    return students


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    flash('Uploaded file is too large. Maximum allowed size is 5 MB.', 'danger')
    return redirect(request.referrer or url_for('signup'))


def _is_allowed_teacher_certificate(filename):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_TEACHER_CERT_EXTENSIONS


def _validate_certificate_file(file_path):
    if not os.path.exists(file_path):
        return False, 'Certificate file not found.'

    file_size = os.path.getsize(file_path)
    if file_size <= 0:
        return False, 'Certificate file is empty.'
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        return False, 'Certificate file exceeds size limit.'

    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in ('.jpg', '.jpeg', '.png'):
            if Image is None:
                return False, 'Image validation requires Pillow package.'
            with Image.open(file_path) as image_obj:
                image_obj.verify()
        elif ext == '.pdf':
            with open(file_path, 'rb') as pdf_file:
                header = pdf_file.read(5)
                if header != b'%PDF-':
                    return False, 'Invalid PDF format.'
            if PdfReader is not None:
                _ = PdfReader(file_path)
        else:
            return False, 'Unsupported certificate format.'
    except Exception as err:
        return False, f'Certificate validation failed: {err}'

    return True, 'Certificate file is valid.'


def _extract_text_from_certificate(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text_chunks = []

    # OCR for images directly via Tesseract.
    if ext in ('.jpg', '.jpeg', '.png'):
        if Image is None or pytesseract is None:
            return ''
        try:
            with Image.open(file_path) as image_obj:
                text_chunks.append(pytesseract.image_to_string(image_obj) or '')
        except Exception:
            pass

    # OCR for PDFs when pdf2image + pytesseract are available.
    elif ext == '.pdf':
        if convert_from_path is not None and pytesseract is not None:
            try:
                pages = convert_from_path(file_path, dpi=200, first_page=1, last_page=3)
                for page in pages:
                    text_chunks.append(pytesseract.image_to_string(page) or '')
            except Exception:
                pass

        # Fallback text extraction for searchable PDFs.
        if not any(chunk.strip() for chunk in text_chunks) and PdfReader is not None:
            try:
                reader = PdfReader(file_path)
                for page in reader.pages[:3]:
                    text_chunks.append(page.extract_text() or '')
            except Exception:
                pass

    return '\n'.join(text_chunks).strip()


def auto_verify_teacher_certificate(file_path):
    is_valid, file_message = _validate_certificate_file(file_path)
    if not is_valid:
        return {
            'is_verified': False,
            'status': 'failed',
            'confidence': 0,
            'matched_keywords': [],
            'message': file_message,
        }

    extracted_text = _extract_text_from_certificate(file_path)
    normalized = extracted_text.lower()
    matched = [kw for kw in TEACHER_DEGREE_KEYWORDS if kw in normalized]
    confidence = round((len(matched) / len(TEACHER_DEGREE_KEYWORDS)) * 100, 2) if TEACHER_DEGREE_KEYWORDS else 0

    if matched:
        return {
            'is_verified': True,
            'status': 'verified',
            'confidence': confidence,
            'matched_keywords': matched,
            'message': 'Certificate verified automatically.',
        }

    return {
        'is_verified': False,
        'status': 'failed',
        'confidence': confidence,
        'matched_keywords': [],
        'message': 'Invalid certificate. Please upload a valid degree.',
    }


def resolve_student_type(profile):
    """Return a stable student_type ('school' or 'college') using profile + grade inference."""
    if not profile:
        return 'college'

    raw_type = (profile['student_type'] or '').strip().lower() if 'student_type' in profile.keys() and profile['student_type'] else ''
    if raw_type in ('school', 'college'):
        return raw_type

    grade_value = (profile['grade'] or '').strip() if 'grade' in profile.keys() and profile['grade'] else ''
    if grade_value and grade_value not in COLLEGE_STREAMS:
        first_token = grade_value.split()[0]
        if first_token.isdigit():
            return 'school'
    return 'college'


@app.after_request
def add_no_cache_headers(response):
    """Avoid stale auth/profile/focus pages after account switching."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.context_processor
def inject_current_profile():
    """Make current_profile available in every template (for conditional nav)."""
    user = current_user()
    if user:
        conn = get_db_connection()
        prof = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
        conn.close()
        return {
            'current_profile': prof,
            'teacher_verification_enabled': TEACHER_VERIFICATION_ENABLED,
        }
    return {
        'current_profile': None,
        'teacher_verification_enabled': TEACHER_VERIFICATION_ENABLED,
    }


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
        role = (request.form.get('role', 'student') or 'student').strip().lower()
        standard = _clean_class_value(request.form.get('standard'))
        section = _clean_section_value(request.form.get('section'))
        assigned_standard = _clean_class_value(request.form.get('assigned_standard'))
        assigned_section = _clean_section_value(request.form.get('assigned_section'))
        teacher_proof = request.files.get('teacher_proof')
        if role not in ('student', 'college_student', 'teacher'):
            role = 'student'
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)
        if role == 'teacher' and (not assigned_standard or not assigned_section):
            flash('Teachers must select Grade / Class and Section.', 'danger')
            return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)
        if TEACHER_VERIFICATION_ENABLED and role == 'teacher' and (not teacher_proof or not teacher_proof.filename):
            flash('Teacher proof document is required for teacher signup.', 'danger')
            return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)
        if TEACHER_VERIFICATION_ENABLED and role == 'teacher' and teacher_proof and not _is_allowed_teacher_certificate(teacher_proof.filename):
            flash('Only PDF/JPG/PNG certificates are allowed for teacher verification.', 'danger')
            return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)
        conn = get_db_connection()
        try:
            default_verified = 0 if (role == 'teacher' and TEACHER_VERIFICATION_ENABLED) else 1
            default_status = 'pending' if (role == 'teacher' and TEACHER_VERIFICATION_ENABLED) else 'verified'
            cur = conn.execute(
                '''
                INSERT INTO users (
                    username, password, email, role, is_verified, verification_status,
                    standard, section, assigned_standard, assigned_section
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    username, password, email, role, default_verified, default_status,
                    standard if role in ('student', 'college_student') else '',
                    section if role in ('student', 'college_student') else '',
                    assigned_standard if role == 'teacher' else '',
                    assigned_section if role == 'teacher' else ''
                )
            )
            new_user_id = cur.lastrowid

            if TEACHER_VERIFICATION_ENABLED and role == 'teacher' and teacher_proof and teacher_proof.filename:
                user_id = new_user_id
                safe_name = _material_storage_name(user_id, teacher_proof.filename)
                proof_path = os.path.join(TEACHER_PROOF_UPLOAD_DIR, safe_name)
                teacher_proof.save(proof_path)

                verification = auto_verify_teacher_certificate(proof_path)
                verification_status = verification['status']
                is_verified = 1 if verification['is_verified'] else 0
                matched_keywords = ', '.join(verification.get('matched_keywords', []))
                notes = (
                    f"{verification.get('message', '')} | "
                    f"confidence={verification.get('confidence', 0)} | "
                    f"matched=[{matched_keywords}]"
                )

                conn.execute(
                    '''
                    INSERT INTO teacher_verification (user_id, proof_file, status, submitted_at)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (user_id, safe_name, verification_status, datetime.now().isoformat())
                )
                conn.execute(
                    '''
                    UPDATE users
                    SET is_verified = ?, verification_status = ?
                    WHERE id = ?
                    ''',
                    (is_verified, verification_status, user_id)
                )
                conn.execute(
                    '''
                    UPDATE teacher_verification
                    SET notes = ?
                    WHERE user_id = ? AND proof_file = ?
                    ''',
                    (notes, user_id, safe_name)
                )

            if role in ('student', 'college_student'):
                _sync_teacher_students_for_student(conn, new_user_id)
                # Debug: verify teacher mapping was created
                student_row = conn.execute(
                    'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
                    (new_user_id,)
                ).fetchone()
                print(
                    f'[DEBUG Signup] ✓ student_id={new_user_id} username={username} standard={standard} section={section} '
                    f'teacher_id={student_row["teacher_id"] if student_row else "NO_RECORD"} '
                    f'class_id={student_row["class_id"] if student_row else "NO_RECORD"}'
                )
            elif role == 'teacher':
                _sync_teacher_students_for_teacher(conn, new_user_id)
                print(f'[DEBUG Signup] ✓ teacher_id={new_user_id} username={username} assigned_standard={assigned_standard} assigned_section={assigned_section}')

            conn.commit()
            if role == 'teacher':
                if not TEACHER_VERIFICATION_ENABLED:
                    flash('Teacher account created successfully. You can login now.', 'success')
                else:
                    teacher_user = conn.execute(
                        'SELECT is_verified, verification_status FROM users WHERE id = ?',
                        (cur.lastrowid,)
                    ).fetchone()
                    if teacher_user and int(teacher_user['is_verified'] or 0) == 1:
                        flash('Teacher account created and verified automatically. You can login now.', 'success')
                    else:
                        flash('Invalid certificate. Please upload a valid degree.', 'danger')
                return redirect(url_for('login'))
            flash('Signup successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
    return render_template('signup.html', teacher_verification_enabled=TEACHER_VERIFICATION_ENABLED, all_grades=SCHOOL_GRADES)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        if user:
            role = current_user_role(user)
            if TEACHER_VERIFICATION_ENABLED and role == 'teacher' and not is_teacher_approved(user['id']):
                conn.close()
                status = (user['verification_status'] or '').strip().lower() if 'verification_status' in user.keys() else ''
                if status == 'failed':
                    flash('Invalid certificate. Please upload a valid degree.', 'danger')
                else:
                    flash('Teacher verification is pending. Please wait for automatic validation.', 'warning')
                return redirect(url_for('login'))

            conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
            profile = conn.execute('SELECT student_type, grade FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
            
            # MANDATORY FIX Step 6: For students, forcefully resolve and cache teacher mapping during login
            if role in ('student', 'college_student'):
                _sync_teacher_students_for_student(conn, user['id'])
                student_row = conn.execute(
                    'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
                    (user['id'],)
                ).fetchone()
                teacher_id = student_row['teacher_id'] if student_row else None
                class_id = student_row['class_id'] if student_row else None
                print(f'[DEBUG Login] student_id={user["id"]} username={user["username"]} teacher_id={teacher_id} class_id={class_id}')
            
            conn.close()

            # Ensure no stale auth/session data survives from a previous account.
            session.clear()
            session['user_id'] = user['id']
            session['role'] = role
            if role == 'college_student':
                session['student_type'] = 'college'
            elif role == 'teacher':
                session['student_type'] = 'college'
            else:
                session['student_type'] = resolve_student_type(profile)
            session['auth_nonce'] = str(int(time.time() * 1000))

            if role == 'teacher':
                flash('Login successful.', 'success')
                return redirect(url_for('teacher_dashboard'))

            # Log activity AFTER teacher mapping is secured
            log_activity(user['id'], 'login', f'{user["username"]} logged in.')

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
    current = current_user()
    if current and current_user_role(current) in ('student', 'college_student'):
        log_activity(current['id'], 'logout', f'{current["username"]} logged out.')
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login', logged_out='1'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    role = current_user_role(user)
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()

    if role == 'teacher':
        teacher_meta = conn.execute(
            '''
            SELECT t.class_id, t.section, t.subject
            FROM teachers t
            WHERE t.teacher_id = ?
            ''',
            (user['id'],)
        ).fetchone()

        if request.method == 'POST':
            assigned_standard = (request.form.get('assigned_standard') or '').strip()
            assigned_section = _clean_section_value(request.form.get('assigned_section'))
            teacher_subject = (request.form.get('teacher_subject') or '').strip()

            if not assigned_standard or not assigned_section:
                flash('Class and section are required for teacher profile.', 'danger')
            else:
                class_id = _ensure_class_record(conn, assigned_standard, assigned_section, class_teacher_id=user['id'])
                conn.execute(
                    'UPDATE users SET assigned_standard = ?, assigned_section = ? WHERE id = ?',
                    (assigned_standard, assigned_section, user['id'])
                )
                conn.execute(
                    '''
                    INSERT INTO teachers (teacher_id, name, class_id, section, subject)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(teacher_id) DO UPDATE SET
                        name = excluded.name,
                        class_id = excluded.class_id,
                        section = excluded.section,
                        subject = excluded.subject
                    ''',
                    (user['id'], user['username'], class_id, assigned_section, teacher_subject)
                )
                _sync_teacher_students_for_teacher(conn, user['id'])
                conn.commit()
                conn.close()
                flash('Teacher profile saved.', 'success')
                return redirect(url_for('teacher_dashboard'))

        teacher_standard = _clean_class_value(user['assigned_standard']) if 'assigned_standard' in user.keys() else ''
        teacher_section = _clean_section_value(user['assigned_section']) if 'assigned_section' in user.keys() else ''
        teacher_subject = (teacher_meta['subject'] if teacher_meta else '') or ''
        conn.close()
        return render_template(
            'profile.html',
            user=user,
            profile=profile,
            is_teacher=True,
            teacher_standard=teacher_standard,
            teacher_section=teacher_section,
            teacher_subject=teacher_subject,
            all_grades=SCHOOL_GRADES,
            section_choices=['A', 'B', 'C', 'D', 'E', 'F']
        )

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
        parent_phone = request.form.get('parent_phone', '').strip()
        subjects = ','.join(request.form.getlist('subjects'))
        daily_goal = int(request.form.get('daily_goal') or 60)
        if daily_goal < MIN_STUDY_MINUTES:
            daily_goal = MIN_STUDY_MINUTES
            flash(f'Daily study goal updated to minimum {MIN_STUDY_MINUTES} minutes.', 'info')

        # Keep board and parent email strictly school-only.
        if student_type != 'school':
            board = ''
            parent_email = ''
            parent_phone = ''

        conn.execute('UPDATE users SET email = ? WHERE id = ?', (email, user['id']))
        conn.execute(
            'UPDATE users SET standard = ?, section = ? WHERE id = ?',
            (grade, _clean_section_value(section), user['id'])
        )
        if profile:
            conn.execute(
                '''UPDATE student_profile
                   SET full_name=?, school=?, department=?, grade=?, section=?, board=?,
                              parent_email=?, parent_phone=?, subjects=?, daily_goal=?, student_type=?
                   WHERE user_id = ?''',
                     (full_name, school, department, grade, section, board, parent_email, parent_phone, subjects, daily_goal, student_type, user['id']))
        else:
            conn.execute(
                '''INSERT INTO student_profile
                         (user_id, full_name, school, department, grade, section, board, parent_email, parent_phone, subjects, daily_goal, student_type)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (user['id'], full_name, school, department, grade, section, board, parent_email, parent_phone, subjects, daily_goal, student_type))
        _sync_teacher_students_for_student(conn, user['id'])
        conn.commit()
        conn.close()
        flash('Profile saved.', 'success')
        return redirect(url_for('dashboard'))
    conn.close()
    stype = profile['student_type'] if profile else 'college'
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None, stype)
    return render_template('profile.html', user=user, profile=profile,
                           is_teacher=False,
                           subjects=grade_subjects, all_grades=SCHOOL_GRADES,
                           school_subjects_by_grade=SCHOOL_SUBJECTS_BY_GRADE,
                           school_subjects_default=SCHOOL_SUBJECTS_DEFAULT,
                           college_subjects=SUBJECTS,
                           college_streams=COLLEGE_STREAMS,
                           college_subjects_by_stream=COLLEGE_SUBJECTS_BY_STREAM)


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')
    
    # POST request - reset password
    username = request.form.get('username', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    # Validation - username
    if not username:
        flash('⚠️ Please enter your username.', 'danger')
        return render_template('forgot_password.html')
    
    # Validation - new password
    if not new_password:
        flash('⚠️ Please enter a new password.', 'danger')
        return render_template('forgot_password.html')
    
    if len(new_password) < 8:
        flash('⚠️ New password must be at least 8 characters long.', 'danger')
        return render_template('forgot_password.html')
    
    # Validation - confirmation
    if not confirm_password:
        flash('⚠️ Please confirm your new password.', 'danger')
        return render_template('forgot_password.html')
    
    if new_password != confirm_password:
        flash('⚠️ Passwords do not match. Please try again.', 'danger')
        return render_template('forgot_password.html')
    
    # Check if user exists
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        
        if not user:
            flash('❌ Username not found. Please check and try again.', 'danger')
            return render_template('forgot_password.html')
        
        # Update password
        conn.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, username))
        conn.commit()
        flash('✅ Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        flash(f'❌ Error resetting password: {str(e)}', 'danger')
        return render_template('forgot_password.html')
    finally:
        conn.close()


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
    if current_user_role(user) == 'teacher':
        return redirect(url_for('teacher_dashboard'))

    apply_homework_deadline_penalties(user['id'])
    apply_streak_decay_if_missed(user['id'])
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()

    if not profile or not (profile['student_type'] or '').strip():
        conn.close()
        flash('Please complete your profile first and choose School or College student.', 'warning')
        return redirect(url_for('profile'))

    study_logs = conn.execute('SELECT * FROM study_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user['id'],)).fetchall()
    today_str = date.today().isoformat()
    upcoming_hw = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status != 'completed' AND due_date >= ? ORDER BY due_date ASC LIMIT 5",
        (user['id'], today_str)
    ).fetchall()
    overdue_hw = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status != 'completed' AND due_date < ? ORDER BY due_date ASC",
        (user['id'], today_str)
    ).fetchall()
    next_exam = conn.execute(
        'SELECT * FROM exams WHERE user_id = ? AND exam_date >= ? ORDER BY exam_date ASC LIMIT 1',
        (user['id'], today_str)
    ).fetchone()

    available_school_exams = []
    assigned_materials = []
    student_info = conn.execute('SELECT class_id, section FROM students WHERE student_id = ?', (user['id'],)).fetchone()
    if student_info:
        class_id = str(student_info['class_id']).strip() if student_info['class_id'] else ''
        section = str(student_info['section']).strip() if student_info['section'] else ''
        
        # Fetch exams following material logic with robust TRIM matching
        available_school_exams = conn.execute(
            '''
            SELECT se.*, u.username as teacher_name,
                   (SELECT score FROM school_exam_attempts sea WHERE sea.exam_id = se.id AND sea.student_id = ?) as my_score
            FROM school_exams se
            JOIN users u ON u.id = se.created_by
            WHERE TRIM(se.class_id) = TRIM(?)
              AND TRIM(se.section) = TRIM(?)
              AND se.is_published = 1
            ORDER BY se.created_at DESC LIMIT 5
            ''',
            (user['id'], class_id, section)
        ).fetchall()

        # Debug logs for troubleshooting
        print(f"DEBUG STUDENT DASHBOARD: id={user['id']} class_id={class_id} section={section}")
        print(f"DEBUG MATCHED EXAMS: {len(available_school_exams)}")

        # Fetch materials assigned to this class
        # (Assuming study_materials is linked to teachers via teacher_id, and we filter by the teacher's class)
        assigned_materials = conn.execute(
            '''
            SELECT sm.*, u.username as teacher_name
            FROM study_materials sm
            JOIN users u ON u.id = sm.teacher_id
            WHERE u.assigned_standard = (SELECT standard FROM classes WHERE id = ?)
              AND UPPER(u.assigned_section) = ?
            ORDER BY sm.created_at DESC LIMIT 5
            ''',
            (class_id, section)
        ).fetchall()

    conn.close()

    today_logs = get_today_logs(user['id'])
    total_today = sum([row['minutes'] for row in today_logs])
    total_all = sum([row['minutes'] for row in study_logs])
    streak = user['streak'] or 0

    student_type = resolve_student_type(profile)
    is_school = student_type == 'school'

    grade = profile['grade'] if profile else None
    grade_subjects = get_subjects_for_grade(grade, student_type)
    subject_topics_for_grade = {s: get_topics_for_subject(s) for s in grade_subjects}

    return render_template('dashboard.html', user=user, profile=profile,
                           today_logs=today_logs, total_today=total_today,
                           total_all=total_all, streak=streak,
                           subjects=grade_subjects, subject_topics=subject_topics_for_grade,
                           upcoming_hw=upcoming_hw, overdue_hw=overdue_hw,
                           next_exam=next_exam, is_school=is_school,
                           student_type=student_type,
                           available_school_exams=available_school_exams,
                           assigned_materials=assigned_materials)


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

        log_activity(
            user['id'],
            'subject_selection',
            f'Selected subject {mandatory}' + (f' with extra subjects: {", ".join(extra)}' if extra else ''),
            subject=mandatory
        )
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)
    return render_template('plan_subjects.html', subjects=grade_subjects, profile=profile)


def call_ai_provider(prompt_text):
    # Support a primary key plus optional backup keys to reduce interruptions.
    api_keys = []
    primary_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if primary_key:
        api_keys.append(primary_key)

    extra_keys = os.environ.get('OPENROUTER_API_KEYS', '').strip()
    if extra_keys:
        api_keys.extend([k.strip() for k in extra_keys.split(',') if k.strip()])

    # Remove placeholder/invalid values and duplicates while preserving order.
    filtered_keys = []
    seen = set()
    for key in api_keys:
        if key == 'your_openrouter_api_key_here' or key in seen:
            continue
        filtered_keys.append(key)
        seen.add(key)

    if not filtered_keys:
        return 'OpenRouter API key not set or invalid in .env file.'

    max_retries = 3
    retry_delay = 2
    openrouter_url = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1/chat/completions').strip()
    openrouter_model = os.environ.get('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001').strip()

    for key_index, api_key in enumerate(filtered_keys):
        for attempt in range(max_retries):
            try:
                payload = {
                    'model': openrouter_model,
                    'messages': [
                        {'role': 'user', 'content': prompt_text}
                    ],
                    'temperature': 0.7,
                }
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(
                    openrouter_url,
                    data=data,
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': os.environ.get('OPENROUTER_SITE_URL', 'http://localhost:5000'),
                        'X-Title': os.environ.get('OPENROUTER_APP_NAME', 'AI Study Planner'),
                    },
                    method='POST'
                )

                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode('utf-8')
                    parsed = json.loads(raw)
                    choices = parsed.get('choices') or []
                    if not choices:
                        return 'AI provider returned an empty response.'
                    message = choices[0].get('message') or {}
                    content = message.get('content', '')
                    if isinstance(content, list):
                        content = ' '.join(
                            item.get('text', '') for item in content if isinstance(item, dict)
                        ).strip()
                    return str(content).strip() if content else 'AI provider returned an empty response.'
            except Exception as err:
                error_str = str(err)
                error_lower = error_str.lower()
                print(f"[OpenRouter Debug] Full error: {error_str}")
                print(f"[OpenRouter Debug] Error type: {type(err).__name__}")

                if isinstance(err, urllib.error.HTTPError):
                    try:
                        body = err.read().decode('utf-8', errors='ignore')
                    except Exception:
                        body = ''
                    error_lower = f"{error_lower} {body.lower()}"

                # Quota / rate-limit errors: try next key if available, otherwise return guidance.
                if '429' in error_str or 'resource_exhausted' in error_lower or 'quota' in error_lower or 'rate limit' in error_lower:
                    has_more_keys = key_index < len(filtered_keys) - 1
                    if has_more_keys:
                        print(f"[OpenRouter] Quota hit for key #{key_index + 1}, trying next key.")
                        break
                    return (
                        'OpenRouter quota reached or rate-limited (429). '
                        'Please check your OpenRouter credits/limits and retry. '
                        'You can also set backup keys in OPENROUTER_API_KEYS (comma-separated) in .env.'
                    )

                # Check for invalid API key.
                if 'invalid' in error_lower or 'unauthenticated' in error_lower or '401' in error_str or '403' in error_str:
                    has_more_keys = key_index < len(filtered_keys) - 1
                    if has_more_keys:
                        print(f"[OpenRouter] Invalid key #{key_index + 1}, trying next key.")
                        break
                    return 'Invalid or expired API key. Please verify your OPENROUTER_API_KEY in .env file.'

                # Retry transient connection errors for the same key.
                if 'disconnected' in error_lower or 'connection' in error_lower or 'timeout' in error_lower:
                    if attempt < max_retries - 1:
                        print(f"[OpenRouter] Connection error, retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    has_more_keys = key_index < len(filtered_keys) - 1
                    if has_more_keys:
                        print(f"[OpenRouter] Connection issue with key #{key_index + 1}, trying next key.")
                        break
                    return (
                        f'OpenRouter API connection failed after {max_retries} attempts. '
                        'The AI service may be temporarily unavailable. Please try again in a few moments.'
                    )

                # Other errors are returned immediately.
                return f"Gemini request failed: {err}"
    
    return "Gemini request failed: Unknown error"


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
        generated = call_ai_provider(prompt)
    return render_template('topic_generator.html', subjects=grade_subjects, generated=generated, selected_subject=selected_subject)


@app.route('/ai_notes', methods=['POST'])
@login_required
def ai_notes():
    topic = request.form.get('topic')
    if not topic:
        flash('Select a topic first.', 'danger')
        return redirect(url_for('topic_generator'))
    
    # Structured prompt for well-organized notes with clean formatting - NO asterisks
    prompt = f"""Create comprehensive and well-organized study notes for '{topic}' following this exact structure. IMPORTANT: Do NOT use any asterisks (*), dashes (-), or bullet points. Use ### headings for emphasis. Format content as plain text with proper paragraphs.

1. DEFINITION

Provide a clear and concise definition of the topic in 2-3 sentences.

2. OVERVIEW

### Brief Overview and Context

Brief overview and context of the topic in paragraph form. Include 3-4 key points naturally woven into the explanation without using any special characters.

### Why It's Important to Study This Topic

Explain 3-4 reasons why this topic is important in paragraph form, naturally integrated without bullet points or special formatting.

3. KEY CONCEPTS

List the main concepts related to {topic}:

Concept 1: Brief explanation of this concept

Concept 2: Brief explanation of this concept

Concept 3: Brief explanation of this concept

Concept 4: Brief explanation of this concept

4. DETAILED EXPLANATION

### Main Concepts

Provide in-depth explanation with logical flow. Break down complex ideas into simpler parts:

1. First aspect of explanation
2. Second aspect of explanation
3. Third aspect of explanation
4. Fourth aspect of explanation

5. EXAMPLES

### Practical Real-World Examples

Example 1: Description and explanation in detail

Example 2: Description and explanation in detail

Example 3: Description and explanation in detail

6. KEY POINTS TO REMEMBER

Main Point 1: Explanation

Main Point 2: Explanation

Main Point 3: Explanation

Main Point 4: Explanation

Main Point 5: Explanation

### Tips for Remembering

Tip 1: Helpful mnemonic or memory aid

Tip 2: Helpful mnemonic or memory aid

7. COMMON MISTAKES

### Common Mistake 1

Explanation of why it's wrong and what's correct

### Common Mistake 2

Explanation of why it's wrong and what's correct

### Common Mistake 3

Explanation of why it's wrong and what's correct

8. PRACTICE QUESTIONS

### Question 1

Answer: Detailed explanation

### Question 2

Answer: Detailed explanation

### Question 3

Answer: Detailed explanation

### Question 4

Answer: Detailed explanation

### Question 5

Answer: Detailed explanation

9. TIPS FOR MASTERY

### Study Strategies

Strategy 1: Detailed explanation of approach

Strategy 2: Detailed explanation of approach

Strategy 3: Detailed explanation of approach

### Next Steps for Deeper Learning

Resource 1: Description and how to use it

Resource 2: Description and how to use it

Resource 3: Description and how to use it

IMPORTANT: Do NOT use any asterisks (*), dashes (-), or any special bullet point characters. Use only ### headings for emphasis and plain paragraphs for content."""
    
    notes = call_ai_provider(prompt)
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
            grade_note = f'Please explain clearly for a Grade {grade} school student.' if grade else 'Provide a clear and comprehensive explanation.'
            
            # Moderate-length answer prompt
            prompt = f"""
{grade_note}

Question: {q}

Provide a concise answer in 3-5 sentences. Include the key explanation and one example if relevant.

Do NOT use asterisks (*) or dashes (-).
"""
            
            answer = call_ai_provider(prompt)
            if not answer:
                answer = 'No answer from AI.'
    return render_template('ai_chat.html', question=q, answer=answer)


@app.route('/focus_mode', methods=['GET'])
@login_required
def focus_mode():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT student_type, grade FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()

    student_type = resolve_student_type(profile)
    grade = profile['grade'] if profile and profile['grade'] else None
    grade_subjects = get_subjects_for_grade(grade, student_type)
    topics_map = {subject: get_topics_for_subject(subject) for subject in grade_subjects}

    # Keep session role synced with DB-backed profile role.
    session['student_type'] = student_type

    return render_template(
        'focus_mode.html',
        user_type=student_type,
        focus_subjects=grade_subjects,
        focus_topics=topics_map
    )


@app.route('/api/focus-subjects', methods=['GET'])
@login_required
def focus_subjects_api():
    user = current_user()
    conn = get_db_connection()
    profile = conn.execute('SELECT student_type, grade FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.close()

    student_type = resolve_student_type(profile)
    grade = profile['grade'] if profile and profile['grade'] else None
    subjects = get_subjects_for_grade(grade, student_type)
    topics_by_subject = {subject: get_topics_for_subject(subject) for subject in subjects}

    session['student_type'] = student_type

    return jsonify({
        'user_type': student_type,
        'grade': grade or '',
        'subjects': subjects,
        'topics_by_subject': topics_by_subject,
        'fetched_at': datetime.now().isoformat()
    })


# ── Homework tracker ──────────────────────────────────────────────────────────

@app.route('/homework', methods=['GET', 'POST'])
@login_required
def homework():
    user = current_user()
    apply_homework_deadline_penalties(user['id'])
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    grade_subjects = get_subjects_for_grade(profile['grade'] if profile else None)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subject = request.form.get('subject', '').strip()
        due_date = request.form.get('due_date', '').strip()
        priority = normalize_priority(request.form.get('priority', 'medium'))

        if not subject:
            flash('Subject is required.', 'danger')
            conn.close()
            return redirect(url_for('homework'))

        if not title:
            previous = conn.execute(
                'SELECT title FROM homework WHERE user_id = ? AND subject = ? ORDER BY id DESC LIMIT 1',
                (user['id'], subject)
            ).fetchone()
            last_title = previous['title'] if previous else None
            title = generate_homework_topic_title(subject, last_title=last_title)
        if not request.form.get('priority'):
            priority = get_subject_priority(subject)
        if not due_date:
            due_date = get_auto_due_date(priority)

        if not title or not due_date:
            flash('Title, subject and due date are required.', 'danger')
        else:
            conn.execute(
                '''
                INSERT INTO homework
                (user_id, title, subject, due_date, priority, status, started_at, completed_at, xp_reward, deadline_status, penalty_applied, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (user['id'], title, subject, due_date, priority, 'not_started', None, None, 0, 'active', 0, datetime.now().isoformat())
            )
            conn.commit()
            log_activity(user['id'], 'create_homework', f'Created homework "{title}" for {subject}, due {due_date}.', subject=subject)
            flash('Homework added.', 'success')
        conn.close()
        return redirect(url_for('homework'))

    today_str = date.today().isoformat()
    pending = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status != 'completed' ORDER BY due_date ASC",
        (user['id'],)
    ).fetchall()
    done = conn.execute(
        "SELECT * FROM homework WHERE user_id = ? AND status = 'completed' ORDER BY completed_at DESC, due_date DESC LIMIT 20",
        (user['id'],)
    ).fetchall()
    conn.close()

    subject_title_map = {s: get_homework_title_suggestion(s) for s in grade_subjects}
    subject_topic_map = {s: get_homework_topics_for_subject(s) for s in grade_subjects}
    subject_priority_map = {s: get_subject_priority(s) for s in grade_subjects}

    return render_template('homework.html', pending=pending, done=done,
                           subjects=grade_subjects, today=today_str,
                           xp_points=user['xp_points'],
                           subject_title_map=subject_title_map,
                           subject_topic_map=subject_topic_map,
                           subject_priority_map=subject_priority_map)


@app.route('/homework/start/<int:hw_id>')
@login_required
def homework_start(hw_id):
    """Backward-compatible route for link-based start action."""
    flash('Use the Start button to begin this task.', 'info')
    return redirect(url_for('homework'))


@app.route('/start_task/<int:hw_id>', methods=['POST'])
@login_required
def start_task(hw_id):
    user = current_user()
    conn = get_db_connection()
    hw = conn.execute('SELECT * FROM homework WHERE id = ? AND user_id = ?', (hw_id, user['id'])).fetchone()

    if not hw:
        conn.close()
        return jsonify({'ok': False, 'message': 'Homework not found.'}), 404

    if hw['status'] == 'completed':
        conn.close()
        return jsonify({'ok': False, 'message': 'Homework is already completed.'}), 400

    if hw['status'] == 'in_progress':
        conn.close()
        return jsonify({'ok': True, 'message': 'Homework already in progress.'}), 200

    conn.execute(
        "UPDATE homework SET status = 'in_progress', started_at = ?, deadline_status = CASE WHEN due_date < ? THEN 'overdue' ELSE 'active' END WHERE id = ? AND user_id = ?",
        (datetime.now().isoformat(), date.today().isoformat(), hw_id, user['id'])
    )
    conn.commit()

    log_activity(user['id'], 'start_homework', f'Started homework "{hw["title"]}" ({hw["subject"]}).', subject=hw['subject'])
    conn.close()

    return jsonify({'ok': True, 'message': 'Homework moved to In Progress.'})


@app.route('/homework/complete/<int:hw_id>')
@login_required
def homework_complete(hw_id):
    """Backward-compatible route for link-based complete action."""
    flash('Use the Complete button to finish this task.', 'info')
    return redirect(url_for('homework'))


@app.route('/complete_task/<int:hw_id>', methods=['POST'])
@login_required
def complete_task(hw_id):
    user = current_user()
    conn = get_db_connection()
    hw = conn.execute('SELECT * FROM homework WHERE id = ? AND user_id = ?', (hw_id, user['id'])).fetchone()
    user_row = conn.execute('SELECT streak, last_completed_date FROM users WHERE id = ?', (user['id'],)).fetchone()

    if not hw:
        conn.close()
        return jsonify({'ok': False, 'message': 'Homework not found.'}), 404

    if hw['status'] == 'completed':
        conn.close()
        return jsonify({'ok': False, 'message': 'Homework is already completed.'}), 400

    if hw['status'] != 'in_progress':
        conn.close()
        return jsonify({'ok': False, 'message': 'Start the homework first before marking it completed.'}), 400

    today_iso = date.today().isoformat()
    on_time = (hw['due_date'] or '') >= today_iso
    xp_reward = 10 if on_time else 5
    deadline_status = 'completed_on_time' if on_time else 'completed_late'

    # Daily streak update (once per day):
    # - if last_completed_date == yesterday: streak += 1
    # - if last_completed_date == today: no change
    # - if older or first-time: streak = 1
    today_date = date.today()
    yesterday_date = today_date - timedelta(days=1)
    last_completed_raw = (user_row['last_completed_date'] or '').strip() if user_row else ''
    current_streak = (user_row['streak'] or 0) if user_row else 0

    print(f"[Streak Debug] user_id={user['id']} today={today_date.isoformat()} last_completed_date={last_completed_raw} current_streak={current_streak}")

    next_streak = current_streak
    if not last_completed_raw:
        next_streak = 1
    else:
        try:
            last_completed_date = datetime.strptime(last_completed_raw, '%Y-%m-%d').date()
            if last_completed_date == today_date:
                next_streak = current_streak
            elif last_completed_date == yesterday_date:
                next_streak = current_streak + 1
            else:
                next_streak = 1
        except ValueError:
            next_streak = 1

    print(f"[Streak Debug] user_id={user['id']} next_streak={next_streak}")

    conn.execute(
        '''
        UPDATE homework
        SET status = 'completed', completed_at = ?, xp_reward = ?, deadline_status = ?
        WHERE id = ? AND user_id = ?
        ''',
        (datetime.now().isoformat(), xp_reward, deadline_status, hw_id, user['id'])
    )
    conn.execute(
        'UPDATE users SET xp_points = xp_points + ?, streak = ?, last_completed_date = ? WHERE id = ?',
        (xp_reward, next_streak, today_date.isoformat(), user['id'])
    )

    conn.commit()

    started_at_raw = (hw['started_at'] or '').strip() if hw['started_at'] else ''
    spent_minutes = None
    if started_at_raw:
        try:
            started_dt = datetime.fromisoformat(started_at_raw)
            spent_minutes = max(0, int((datetime.now() - started_dt).total_seconds() // 60))
        except ValueError:
            spent_minutes = None

    detail = f'Completed homework "{hw["title"]}" ({hw["subject"]}). +{xp_reward} XP.'
    if spent_minutes is not None:
        detail += f' Time spent ~{spent_minutes} min.'
    log_activity(user['id'], 'complete_homework', detail, subject=hw['subject'])

    conn.close()

    return jsonify({
        'ok': True,
        'message': f'Homework completed. +{xp_reward} XP awarded.',
        'xp_reward': xp_reward,
        'deadline_status': deadline_status
    })


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

    # Include test subjects that are available in the question bank,
    # while preserving profile-driven subjects shown elsewhere in the app.
    test_subjects = list(dict.fromkeys(grade_subjects + list(EXAM_QUESTION_BANK.keys())))

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

    recent_attempts = conn.execute(
        '''
        SELECT *
        FROM exam_attempts
        WHERE user_id = ?
        ORDER BY submitted_at DESC
        LIMIT 12
        ''',
        (user['id'],)
    ).fetchall()
    conn.close()
    return render_template('exams.html', upcoming=upcoming, past=past,
                           subjects=test_subjects, today=today_str,
                           recent_attempts=recent_attempts)


@app.route('/exams/delete/<int:exam_id>')
@login_required
def exam_delete(exam_id):
    user = current_user()
    conn = get_db_connection()
    conn.execute('DELETE FROM exams WHERE id = ? AND user_id = ?', (exam_id, user['id']))
    conn.commit(); conn.close()
    flash('Exam deleted.', 'info')
    return redirect(url_for('exams'))


@app.route('/get_questions/<subject>')
@login_required
def get_questions(subject):
    mapped_subject = resolve_exam_subject(subject)
    if not mapped_subject:
        return jsonify({
            'ok': False,
            'message': f'No question bank configured for subject "{subject}" yet.'
        }), 404

    bank = EXAM_QUESTION_BANK.get(mapped_subject, [])
    if len(bank) < 5:
        return jsonify({
            'ok': False,
            'message': f'Question bank for "{mapped_subject}" is too small.'
        }), 400

    used_questions = session.get('used_exam_questions', {})
    used_ids = set(used_questions.get(mapped_subject, []))
    unused_bank = [q for q in bank if q['id'] not in used_ids]

    # Reset used history when all questions for this subject are exhausted.
    if not unused_bank:
        used_ids = set()
        unused_bank = list(bank)

    requested_count = request.args.get('count', default=8, type=int)
    question_count = max(5, min(10, requested_count if requested_count else 8))
    question_count = min(question_count, len(bank))

    # If remaining unused pool is too small for this test size, reset and start a new cycle.
    if len(unused_bank) < question_count:
        used_ids = set()
        unused_bank = list(bank)

    selected_questions = random.sample(unused_bank, question_count)
    exam_id = f"exam-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    answer_key = {}
    public_questions = []
    selected_ids = []

    for q in selected_questions:
        option_pairs = [
            {'text': option_text, 'original_idx': idx}
            for idx, option_text in enumerate(q['options'])
        ]
        random.shuffle(option_pairs)

        shuffled_options = [pair['text'] for pair in option_pairs]
        remapped_correct_answer = next(
            i for i, pair in enumerate(option_pairs)
            if pair['original_idx'] == q['answer']
        )

        answer_key[q['id']] = remapped_correct_answer
        selected_ids.append(q['id'])
        public_questions.append({
            'id': q['id'],
            'question': q['question'],
            'options': shuffled_options,
        })

    used_ids.update(selected_ids)
    used_questions[mapped_subject] = list(used_ids)
    session['used_exam_questions'] = used_questions

    active_exams = session.get('active_exams', {})
    active_exams[exam_id] = {
        'subject': mapped_subject,
        'started_at': datetime.now().isoformat(),
        'answer_key': answer_key,
    }

    # Keep session payload small by retaining only recent active tests.
    if len(active_exams) > 5:
        active_exam_ids = list(active_exams.keys())
        for old_exam_id in active_exam_ids[:-5]:
            active_exams.pop(old_exam_id, None)

    session['active_exams'] = active_exams

    user = current_user()
    log_activity(user['id'], 'start_exam', f'Started exam for subject {mapped_subject} with {question_count} questions.', subject=mapped_subject)

    return jsonify({
        'ok': True,
        'exam_id': exam_id,
        'subject': mapped_subject,
        'duration_seconds': 600,
        'questions': public_questions,
    })


@app.route('/submit_exam', methods=['POST'])
@login_required
@role_required(['student', 'college_student'])
def submit_exam():
    payload = request.get_json(silent=True) or {}
    exam_id = str(payload.get('exam_id', '')).strip()
    submitted_answers = payload.get('answers', {})

    if not exam_id:
        return jsonify({'ok': False, 'message': 'Missing exam_id.'}), 400

    if not isinstance(submitted_answers, dict):
        return jsonify({'ok': False, 'message': 'Answers must be an object.'}), 400

    active_exams = session.get('active_exams', {})
    active_exam = active_exams.get(exam_id)
    if not active_exam:
        return jsonify({
            'ok': False,
            'message': 'Exam session expired. Please generate a new test.'
        }), 400

    answer_key = active_exam.get('answer_key', {})
    total_questions = len(answer_key)
    score = 0
    answer_details = []

    for question_id, correct_answer in answer_key.items():
        submitted_value = submitted_answers.get(question_id)
        try:
            selected_answer = int(submitted_value) if submitted_value is not None else None
        except (TypeError, ValueError):
            selected_answer = None

        is_correct = selected_answer == correct_answer
        if is_correct:
            score += 1

        answer_details.append({
            'question_id': question_id,
            'selected': selected_answer,
            'correct': correct_answer,
            'is_correct': is_correct,
        })

    started_at_raw = active_exam.get('started_at')
    time_taken_seconds = None
    if started_at_raw:
        try:
            started_at = datetime.fromisoformat(started_at_raw)
            elapsed = int((datetime.now() - started_at).total_seconds())
            time_taken_seconds = max(0, elapsed)
        except ValueError:
            time_taken_seconds = None

    user = current_user()
    submitted_at = datetime.now().isoformat()

    conn = get_db_connection()
    class_id, teacher_id = _record_exam_attempt(
        conn=conn,
        student_id=user['id'],
        exam_id=exam_id,
        subject=active_exam.get('subject', ''),
        score=score,
        total_questions=total_questions,
        time_taken_seconds=time_taken_seconds,
        details_json=json.dumps(answer_details),
        submitted_at=submitted_at,
    )
    
    # MANDATORY FIX Step 1: Verify exam_attempts record actually has teacher_id
    if teacher_id is None:
        print(f'[CRITICAL] Exam submission FAILED: teacher_id is still NULL after insert for student_id={user["id"]}')
        # Fetch back what was inserted to verify
        check_row = conn.execute(
            'SELECT student_id, teacher_id, subject FROM exam_attempts WHERE student_id = ? AND exam_id = ? ORDER BY submitted_at DESC LIMIT 1',
            (user['id'], exam_id)
        ).fetchone()
        if check_row:
            print(f'[DEBUG Exam] Last exam_attempts: student_id={check_row["student_id"]} teacher_id={check_row["teacher_id"]} subject={check_row["subject"]}')
    
    conn.commit()
    conn.close()

    active_exams.pop(exam_id, None)
    session['active_exams'] = active_exams

    log_activity(
        user['id'],
        'submit_exam',
        f'Submitted exam for {active_exam.get("subject", "")}. Score {score}/{total_questions}.',
        subject=active_exam.get('subject', '')
    )

    return jsonify({
        'ok': True,
        'subject': active_exam.get('subject', ''),
        'score': score,
        'total_questions': total_questions,
        'percentage': round((score / total_questions) * 100) if total_questions else 0,
        'time_taken_seconds': time_taken_seconds,
        'answer_details': answer_details,
    })


@app.route('/api/activity/log', methods=['POST'])
@login_required
@role_required(['student', 'college_student'])
def api_log_activity():
    user = current_user()
    payload = request.get_json(silent=True) or {}

    action_type = (payload.get('action_type') or '').strip()
    description = (payload.get('description') or '').strip()
    subject = (payload.get('subject') or '').strip()

    if not action_type:
        return jsonify({'ok': False, 'message': 'action_type is required.'}), 400

    log_activity(user['id'], action_type, description, subject=subject)
    return jsonify({'ok': True, 'message': 'Activity logged.'})


def _is_allowed_material_file(filename):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_MATERIAL_EXTENSIONS


def _material_storage_name(user_id, original_filename):
    safe_name = secure_filename(original_filename or '')
    timestamp = int(time.time())
    return f'u{user_id}_{timestamp}_{safe_name}'


def _ensure_weekly_test(subject, teacher_id=None):
    week_key = get_current_week_key()
    conn = get_db_connection()
    test = conn.execute(
        'SELECT * FROM weekly_tests WHERE week_key = ? AND subject = ?',
        (week_key, subject)
    ).fetchone()

    if test:
        test_id = test['id']
    else:
        conn.execute(
            '''
            INSERT INTO weekly_tests (week_key, subject, teacher_id, total_marks, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (week_key, subject, teacher_id, WEEKLY_TEST_MAX_MARKS, datetime.now().isoformat())
        )
        conn.commit()
        test_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']

        question_pool = EXAM_QUESTION_BANK.get(subject, [])
        required_questions = 10
        if len(question_pool) < required_questions:
            conn.close()
            return None

        selected = random.sample(question_pool, required_questions)
        for q in selected:
            conn.execute(
                'INSERT OR IGNORE INTO weekly_test_questions (test_id, question_id, marks) VALUES (?, ?, ?)',
                (test_id, q['id'], 5)
            )
        conn.commit()

    test = conn.execute('SELECT * FROM weekly_tests WHERE id = ?', (test_id,)).fetchone()
    conn.close()
    return test


def _send_sms_message(phone_number, text_message):
    provider = (os.environ.get('SMS_PROVIDER', 'console') or 'console').strip().lower()
    if provider == 'console':
        print(f'[SMS:console] to={phone_number} message={text_message}')
        return True, 'Console SMS provider logged the message.'

    if provider == 'twilio':
        sid = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
        token = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
        from_number = os.environ.get('TWILIO_FROM_NUMBER', '').strip()
        if not (sid and token and from_number and phone_number):
            return False, 'Twilio credentials or phone numbers are missing.'

        try:
            import base64
            import urllib.parse

            payload = urllib.parse.urlencode({
                'From': from_number,
                'To': phone_number,
                'Body': text_message,
            }).encode('utf-8')
            twilio_url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
            auth_value = base64.b64encode(f'{sid}:{token}'.encode('utf-8')).decode('ascii')
            req = urllib.request.Request(
                twilio_url,
                data=payload,
                headers={
                    'Authorization': f'Basic {auth_value}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=20):
                pass
            return True, 'SMS sent via Twilio.'
        except Exception as err:
            return False, f'Twilio send failed: {err}'

    return False, f'Unsupported SMS provider: {provider}'


@app.route('/teacher/register_verification', methods=['GET', 'POST'])
@login_required
@role_required(['teacher'])
def teacher_register_verification():
    if not TEACHER_VERIFICATION_ENABLED:
        flash('Teacher verification is currently disabled.', 'info')
        return redirect(url_for('teacher_dashboard'))

    user = current_user()
    if request.method == 'POST':
        proof = request.files.get('proof_file')
        if not proof or not proof.filename:
            flash('Please upload ID card or certificate proof.', 'danger')
            return redirect(url_for('teacher_register_verification'))
        if not _is_allowed_teacher_certificate(proof.filename):
            flash('Only PDF/JPG/PNG certificates are allowed.', 'danger')
            return redirect(url_for('teacher_register_verification'))

        safe_name = _material_storage_name(user['id'], proof.filename)
        save_path = os.path.join(TEACHER_PROOF_UPLOAD_DIR, safe_name)
        proof.save(save_path)

        verification = auto_verify_teacher_certificate(save_path)
        verification_status = verification['status']
        is_verified = 1 if verification['is_verified'] else 0
        matched_keywords = ', '.join(verification.get('matched_keywords', []))
        notes = (
            f"{verification.get('message', '')} | "
            f"confidence={verification.get('confidence', 0)} | "
            f"matched=[{matched_keywords}]"
        )

        conn = get_db_connection()
        conn.execute(
            '''
            INSERT INTO teacher_verification (user_id, proof_file, status, submitted_at)
            VALUES (?, ?, ?, ?)
            ''',
            (user['id'], safe_name, verification_status, datetime.now().isoformat())
        )
        conn.execute(
            'UPDATE users SET is_verified = ?, verification_status = ? WHERE id = ?',
            (is_verified, verification_status, user['id'])
        )
        conn.execute(
            'UPDATE teacher_verification SET notes = ? WHERE user_id = ? AND proof_file = ?',
            (notes, user['id'], safe_name)
        )
        conn.commit()
        conn.close()

        if is_verified:
            flash('Certificate verified automatically. Teacher account is now active.', 'success')
        else:
            flash('Invalid certificate. Please upload a valid degree.', 'danger')
        return redirect(url_for('teacher_register_verification'))

    status = get_teacher_verification_status(user['id'])
    return render_template('teacher_verification.html', verification_status=status)


@app.route('/admin/teacher-approvals', methods=['GET', 'POST'])
@login_required
def admin_teacher_approvals():
    admin = current_user()
    if not is_admin_user(admin):
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if request.method == 'POST':
        action = (request.form.get('action') or '').strip().lower()
        if action == 'assign_class':
            teacher_id = int(request.form.get('teacher_id') or 0)
            assigned_standard = (request.form.get('assigned_standard') or '').strip()
            assigned_section = (request.form.get('assigned_section') or '').strip().upper()
            if not teacher_id:
                flash('Teacher selection is required for class assignment.', 'danger')
            elif not assigned_standard or not assigned_section:
                flash('Assigned standard and section are required.', 'danger')
            else:
                conn.execute(
                    '''
                    UPDATE users
                    SET assigned_standard = ?, assigned_section = ?
                    WHERE id = ? AND role = 'teacher'
                    ''',
                    (assigned_standard, assigned_section, teacher_id)
                )
                _sync_teacher_students_for_teacher(conn, teacher_id)
                conn.commit()
                flash(f'Assigned class {assigned_standard}-{assigned_section} to teacher.', 'success')
        else:
            verification_id = int(request.form.get('verification_id') or 0)
            new_status = (request.form.get('status') or '').strip().lower()
            notes = (request.form.get('notes') or '').strip()
            if new_status not in ('approved', 'rejected'):
                flash('Invalid approval status.', 'danger')
            else:
                conn.execute(
                    '''
                    UPDATE teacher_verification
                    SET status = ?, reviewed_at = ?, reviewed_by = ?, notes = ?
                    WHERE id = ?
                    ''',
                    (new_status, datetime.now().isoformat(), admin['id'], notes, verification_id)
                )
                conn.commit()
                flash(f'Teacher verification marked as {new_status}.', 'success')

    rows = conn.execute(
        '''
        SELECT tv.*, u.username, u.email, u.assigned_standard, u.assigned_section
        FROM teacher_verification tv
        JOIN users u ON u.id = tv.user_id
        ORDER BY tv.submitted_at DESC
        ''').fetchall()
    teachers = conn.execute(
        '''
        SELECT id, username, email, assigned_standard, assigned_section
        FROM users
        WHERE role = 'teacher'
        ORDER BY username ASC
        '''
    ).fetchall()
    conn.close()
    return render_template('admin_teacher_approvals.html', requests=rows, teachers=teachers)


# ── School Exam System ────────────────────────────────────────────────────────

@app.route('/teacher/create_exam', methods=['GET', 'POST'])
@login_required
@role_required(['teacher'])
def teacher_create_exam():
    teacher = current_user()
    if request.method == 'POST':
        title = request.form.get('title')
        subject = request.form.get('subject')
        standard = request.form.get('standard')
        section = request.form.get('section')
        duration = int(request.form.get('duration') or 60)
        
        # Lists from form
        q_parts = request.form.getlist('question_part[]')
        q_texts = request.form.getlist('question_text[]')
        opt_as = request.form.getlist('option_a[]')
        opt_bs = request.form.getlist('option_b[]')
        opt_cs = request.form.getlist('option_c[]')
        opt_ds = request.form.getlist('option_d[]')
        corrects = request.form.getlist('correct_answer[]')
        marks_list = request.form.getlist('question_marks[]')
        
        # Specialized for PART4
        p4_as = request.form.getlist('part4_option_a[]')
        p4_bs = request.form.getlist('part4_option_b[]')

        total_marks = sum(int(m) for m in marks_list)
        if total_marks != 50:
            flash(f'Total marks must be exactly 50. Currently: {total_marks}', 'danger')
            return redirect(url_for('teacher_create_exam'))

        conn = get_db_connection()
        class_id = _ensure_class_record(conn, standard, section, class_teacher_id=teacher['id'])
        
        cur = conn.execute(
            '''
            INSERT INTO school_exams (title, class_id, section, subject, total_marks, duration, created_by, is_published, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (title, class_id, section.upper(), subject, 50, duration, teacher['id'], 0, datetime.now().isoformat())
        )
        exam_id = cur.lastrowid

        p1_idx = 0
        p2_idx = 0
        p3_idx = 0
        p4_idx = 0

        for part in q_parts:
            if part == 'PART1':
                conn.execute(
                    '''
                    INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (exam_id, 'PART1', q_texts[p1_idx + p2_idx + p3_idx], opt_as[p1_idx], opt_bs[p1_idx], opt_cs[p1_idx], opt_ds[p1_idx], corrects[p1_idx], 1)
                )
                p1_idx += 1
            elif part == 'PART2':
                conn.execute(
                    '''
                    INSERT INTO school_questions (exam_id, part, question_text, marks)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (exam_id, 'PART2', q_texts[p1_idx + p2_idx + p3_idx], int(marks_list[p1_idx + p2_idx + p3_idx + p4_idx]))
                )
                p2_idx += 1
            elif part == 'PART3':
                conn.execute(
                    '''
                    INSERT INTO school_questions (exam_id, part, question_text, marks)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (exam_id, 'PART3', q_texts[p1_idx + p2_idx + p3_idx], 3)
                )
                p3_idx += 1
            elif part == 'PART4':
                conn.execute(
                    '''
                    INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, marks)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (exam_id, 'PART4', 'Long Answer Either-Or', p4_as[p4_idx], p4_bs[p4_idx], 5)
                )
                p4_idx += 1
        
        conn.commit()
        conn.close()
        flash('Exam created successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))

    return render_template('teacher_create_exam.html')

@app.route('/teacher/edit_exam/<int:exam_id>')
@login_required
@role_required(['teacher'])
def teacher_edit_exam(exam_id):
    teacher = current_user()
    conn = get_db_connection()
    exam = conn.execute('SELECT se.*, c.standard FROM school_exams se JOIN classes c ON c.id = se.class_id WHERE se.id = ?', (exam_id,)).fetchone()
    
    if not exam:
        conn.close()
        flash('Exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    if exam['created_by'] != teacher['id']:
        conn.close()
        flash('You are not authorized to edit this exam.', 'danger')
        return redirect(url_for('teacher_dashboard'))
        
    questions = conn.execute('SELECT * FROM school_questions WHERE exam_id = ? ORDER BY part, id', (exam_id,)).fetchall()
    conn.close()
    
    return render_template('teacher_edit_exam.html', exam=exam, questions=questions)

@app.route('/teacher/update_exam/<int:exam_id>', methods=['POST'])
@login_required
@role_required(['teacher'])
def teacher_update_exam(exam_id):
    teacher = current_user()
    conn = get_db_connection()
    exam = conn.execute('SELECT * FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    
    if not exam or exam['created_by'] != teacher['id']:
        conn.close()
        flash('Unauthorized or exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    title = request.form.get('title')
    subject = request.form.get('subject')
    standard = request.form.get('standard')
    section = request.form.get('section')
    duration = int(request.form.get('duration') or 60)
    
    # Lists from form
    q_parts = request.form.getlist('question_part[]')
    q_texts = request.form.getlist('question_text[]')
    opt_as = request.form.getlist('option_a[]')
    opt_bs = request.form.getlist('option_b[]')
    opt_cs = request.form.getlist('option_c[]')
    opt_ds = request.form.getlist('option_d[]')
    corrects = request.form.getlist('correct_answer[]')
    marks_list = request.form.getlist('question_marks[]')
    
    # Specialized for PART4
    p4_as = request.form.getlist('part4_option_a[]')
    p4_bs = request.form.getlist('part4_option_b[]')

    total_marks = sum(int(m) for m in marks_list)
    if total_marks != 50:
        conn.close()
        flash(f'Total marks must be exactly 50. Currently: {total_marks}', 'danger')
        return redirect(url_for('teacher_edit_exam', exam_id=exam_id))

    class_id = _ensure_class_record(conn, standard, section, class_teacher_id=teacher['id'])
    
    # Update Exam
    conn.execute(
        '''
        UPDATE school_exams 
        SET title=?, class_id=?, section=?, subject=?, duration=?
        WHERE id=?
        ''',
        (title, class_id, section.upper(), subject, duration, exam_id)
    )

    # Replace questions
    conn.execute('DELETE FROM school_questions WHERE exam_id = ?', (exam_id,))

    p1_idx = 0
    p2_idx = 0
    p3_idx = 0
    p4_idx = 0

    for part in q_parts:
        if part == 'PART1':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (exam_id, 'PART1', q_texts[p1_idx + p2_idx + p3_idx], opt_as[p1_idx], opt_bs[p1_idx], opt_cs[p1_idx], opt_ds[p1_idx], corrects[p1_idx], 1)
            )
            p1_idx += 1
        elif part == 'PART2':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, marks)
                VALUES (?, ?, ?, ?)
                ''',
                (exam_id, 'PART2', q_texts[p1_idx + p2_idx + p3_idx], int(marks_list[p1_idx + p2_idx + p3_idx + p4_idx]))
            )
            p2_idx += 1
        elif part == 'PART3':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, marks)
                VALUES (?, ?, ?, ?)
                ''',
                (exam_id, 'PART3', q_texts[p1_idx + p2_idx + p3_idx], 3)
            )
            p3_idx += 1
        elif part == 'PART4':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, marks)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (exam_id, 'PART4', 'Long Answer Either-Or', p4_as[p4_idx], p4_bs[p4_idx], 5)
            )
            p4_idx += 1
    
    conn.commit()
    conn.close()
    flash('Exam updated successfully!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/delete_exam/<int:exam_id>')
@login_required
@role_required(['teacher'])
def teacher_delete_exam(exam_id):
    teacher = current_user()
    conn = get_db_connection()
    exam = conn.execute('SELECT created_by FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    
    if not exam:
        conn.close()
        flash('Exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    if exam['created_by'] != teacher['id']:
        conn.close()
        flash('You are not authorized to delete this exam.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    # Delete related questions first to avoid orphan records
    conn.execute('DELETE FROM school_questions WHERE exam_id = ?', (exam_id,))
    # Delete the exam itself
    conn.execute('DELETE FROM school_exams WHERE id = ?', (exam_id,))
    
    conn.commit()
    conn.close()
    flash('Exam and all its questions deleted successfully.', 'info')
    return redirect(url_for('teacher_dashboard'))

@app.route('/upload_exam/<int:exam_id>')
@login_required
@role_required(['teacher'])
def upload_exam(exam_id):
    conn = get_db_connection()
    conn.execute('''
        UPDATE school_exams
        SET is_published = 1
        WHERE id = ?
    ''', (exam_id,))
    conn.commit()
    conn.close()
    flash('Exam uploaded/published successfully.', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/reupload_exam/<int:exam_id>')
@login_required
@role_required(['teacher'])
def teacher_reupload_exam(exam_id):
    teacher = current_user()
    conn = get_db_connection()
    exam = conn.execute('SELECT se.*, c.standard FROM school_exams se JOIN classes c ON c.id = se.class_id WHERE se.id = ?', (exam_id,)).fetchone()
    
    if not exam:
        conn.close()
        flash('Exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    if exam['created_by'] != teacher['id']:
        conn.close()
        flash('You are not authorized to re-upload this exam.', 'danger')
        return redirect(url_for('teacher_dashboard'))
        
    questions = conn.execute('SELECT * FROM school_questions WHERE exam_id = ? ORDER BY part, id', (exam_id,)).fetchall()
    conn.close()
    
    # We'll use the same template as edit, but indicate it's a re-upload
    return render_template('teacher_reupload_exam.html', exam=exam, questions=questions)

@app.route('/teacher/update_reupload_exam/<int:exam_id>', methods=['POST'])
@login_required
@role_required(['teacher'])
def teacher_update_reupload_exam(exam_id):
    teacher = current_user()
    conn = get_db_connection()
    exam = conn.execute('SELECT * FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    
    if not exam or exam['created_by'] != teacher['id']:
        conn.close()
        flash('Unauthorized or exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    title = request.form.get('title')
    subject = request.form.get('subject')
    standard = request.form.get('standard')
    section = request.form.get('section')
    duration = int(request.form.get('duration') or 60)
    
    # Lists from form
    q_parts = request.form.getlist('question_part[]')
    q_texts = request.form.getlist('question_text[]')
    opt_as = request.form.getlist('option_a[]')
    opt_bs = request.form.getlist('option_b[]')
    opt_cs = request.form.getlist('option_c[]')
    opt_ds = request.form.getlist('option_d[]')
    corrects = request.form.getlist('correct_answer[]')
    marks_list = request.form.getlist('question_marks[]')
    
    # Specialized for PART4
    p4_as = request.form.getlist('part4_option_a[]')
    p4_bs = request.form.getlist('part4_option_b[]')

    total_marks = sum(int(m) for m in marks_list)
    if total_marks != 50:
        conn.close()
        flash(f'Total marks must be exactly 50 to re-publish. Currently: {total_marks}', 'danger')
        return redirect(url_for('teacher_reupload_exam', exam_id=exam_id))

    class_id = _ensure_class_record(conn, standard, section, class_teacher_id=teacher['id'])
    
    # Update Exam AND set is_updated=1
    conn.execute(
        '''
        UPDATE school_exams 
        SET title=?, class_id=?, section=?, subject=?, duration=?, is_updated=1, created_at=?
        WHERE id=?
        ''',
        (title, class_id, section.upper(), subject, duration, datetime.now().isoformat(), exam_id)
    )

    # Replace questions
    conn.execute('DELETE FROM school_questions WHERE exam_id = ?', (exam_id,))

    p1_idx = 0
    p2_idx = 0
    p3_idx = 0
    p4_idx = 0

    for part in q_parts:
        if part == 'PART1':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, option_c, option_d, correct_answer, marks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (exam_id, 'PART1', q_texts[p1_idx + p2_idx + p3_idx], opt_as[p1_idx], opt_bs[p1_idx], opt_cs[p1_idx], opt_ds[p1_idx], corrects[p1_idx], 1)
            )
            p1_idx += 1
        elif part == 'PART2':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, marks)
                VALUES (?, ?, ?, ?)
                ''',
                (exam_id, 'PART2', q_texts[p1_idx + p2_idx + p3_idx], int(marks_list[p1_idx + p2_idx + p3_idx + p4_idx]))
            )
            p2_idx += 1
        elif part == 'PART3':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, marks)
                VALUES (?, ?, ?, ?)
                ''',
                (exam_id, 'PART3', q_texts[p1_idx + p2_idx + p3_idx], 3)
            )
            p3_idx += 1
        elif part == 'PART4':
            conn.execute(
                '''
                INSERT INTO school_questions (exam_id, part, question_text, option_a, option_b, marks)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (exam_id, 'PART4', 'Long Answer Either-Or', p4_as[p4_idx], p4_bs[p4_idx], 5)
            )
            p4_idx += 1
    
    conn.commit()
    conn.close()
    flash('Exam re-published and updated successfully!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/student/available_exams')
@login_required
@role_required(['student', 'college_student'])
def student_available_exams():
    user = current_user()
    conn = get_db_connection()
    
    # Get student's class and section from 'students' table
    student_info = conn.execute(
        'SELECT class_id, section FROM students WHERE student_id = ?', 
        (user['id'],)
    ).fetchone()
    
    if not student_info or not student_info['class_id']:
        conn.close()
        flash('Please complete your profile (Class & Section) to view exams.', 'warning')
        return redirect(url_for('profile'))

    class_id = str(student_info['class_id']).strip()
    student_section = str(student_info['section'] or '').strip()

    print("STUDENT:", class_id, student_section)

    # Get exams for this specific class_id and section.
    exams = conn.execute(
        '''
        SELECT se.*, u.username as teacher_name
        FROM school_exams se
        JOIN users u ON u.id = se.created_by
        WHERE TRIM(se.class_id) = TRIM(?) 
          AND TRIM(se.section) = TRIM(?) 
          AND se.is_published = 1
        ORDER BY se.created_at DESC
        ''',
        (class_id, student_section)
    ).fetchall()

    print("EXAMS:", exams)

    # Get student's attempts
    attempts = conn.execute(
        'SELECT exam_id, score FROM school_exam_attempts WHERE student_id = ?',
        (user['id'],)
    ).fetchall()
    
    attempt_map = {a['exam_id']: a['score'] for a in attempts}
    attempted_ids = list(attempt_map.keys())

    # Format exams with student score if attempted
    formatted_exams = []
    for e in exams:
        d = dict(e)
        d['student_score'] = attempt_map.get(e['id'])
        formatted_exams.append(d)

    student_standard = conn.execute('SELECT standard FROM classes WHERE id = ?', (class_id,)).fetchone()['standard']

    conn.close()
    return render_template('student_available_exams.html', 
                           exams=formatted_exams, 
                           attempted_ids=attempted_ids,
                           student_standard=student_standard,
                           student_section=student_section)

@app.route('/student/take_exam/<int:exam_id>')
@login_required
@role_required(['student', 'college_student'])
def student_take_exam(exam_id):
    user = current_user()
    conn = get_db_connection()
    
    # Check if already attempted
    already = conn.execute('SELECT id FROM school_exam_attempts WHERE student_id = ? AND exam_id = ?', (user['id'], exam_id)).fetchone()
    if already:
        conn.close()
        flash('You have already attempted this exam.', 'warning')
        return redirect(url_for('student_available_exams'))

    exam = conn.execute('SELECT * FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    if not exam:
        conn.close()
        flash('Exam not found.', 'danger')
        return redirect(url_for('student_available_exams'))
    
    questions = conn.execute('SELECT * FROM school_questions WHERE exam_id = ? ORDER BY part, id', (exam_id,)).fetchall()
    conn.close()
    
    log_activity(user['id'], 'start_exam', f'Started school exam: {exam["title"]}', subject=exam['subject'])
    
    return render_template('student_take_exam.html', exam=exam, questions=questions, student_name=user['username'], user_id=user['id'])

@app.route('/student/submit_school_exam', methods=['POST'])
@login_required
@role_required(['student', 'college_student'])
def student_submit_school_exam():
    user = current_user()
    exam_id = request.form.get('exam_id')
    
    conn = get_db_connection()
    questions = conn.execute('SELECT * FROM school_questions WHERE exam_id = ?', (exam_id,)).fetchall()
    
    total_score = 0
    student_answers = []
    
    for q in questions:
        if q['part'] == 'PART1':
            selected = request.form.get(f'q_{q["id"]}')
            if selected == q['correct_answer']:
                total_score += q['marks']
            student_answers.append((q['id'], selected))
        elif q['part'] == 'PART4':
            choice = request.form.get(f'q_{q["id"]}_choice')
            answer_text = request.form.get(f'q_{q["id"]}_text')
            full_val = f"Choice: {choice} | Answer: {answer_text}" if choice else ""
            student_answers.append((q['id'], full_val))
        else: # PART2, PART3
            answer_text = request.form.get(f'q_{q["id"]}')
            student_answers.append((q['id'], answer_text))
    
    # Save attempt
    cur = conn.execute(
        '''
        INSERT INTO school_exam_attempts (student_id, exam_id, score, submitted_at)
        VALUES (?, ?, ?, ?)
        ''',
        (user['id'], exam_id, total_score, datetime.now().isoformat())
    )
    attempt_id = cur.lastrowid
    
    # Save individual answers
    for q_id, ans in student_answers:
        conn.execute(
            '''
            INSERT INTO school_student_answers (attempt_id, question_id, selected_answer)
            VALUES (?, ?, ?)
            ''',
            (attempt_id, q_id, ans or '')
        )
    
    # Award XP (25 XP for attending structured school exam)
    conn.execute('UPDATE users SET xp_points = xp_points + 25 WHERE id = ?', (user['id'],))
    
    conn.commit()
    
    exam = conn.execute('SELECT title, subject FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    log_activity(user['id'], 'submit_exam', f'Submitted structured school exam: {exam["title"]} (Initial MCQ Score: {total_score})', subject=exam['subject'])
    
    conn.close()
    flash(f'Exam submitted! Your MCQ score is {total_score}. Descriptive answers are pending teacher review. +25 XP awarded.', 'success')
    return redirect(url_for('student_available_exams'))


@app.route('/teacher/view_exam_results/<int:exam_id>')
@login_required
@role_required(['teacher'])
def view_exam_results(exam_id):
    conn = get_db_connection()
    exam = conn.execute('SELECT * FROM school_exams WHERE id = ?', (exam_id,)).fetchone()
    if not exam:
        conn.close()
        flash('Exam not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    results = conn.execute(
        '''
        SELECT sea.*, u.username as student_name
        FROM school_exam_attempts sea
        JOIN users u ON u.id = sea.student_id
        WHERE sea.exam_id = ?
        ORDER BY sea.submitted_at DESC
        ''',
        (exam_id,)
    ).fetchall()
    
    conn.close()
    return render_template('teacher_exam_results.html', exam=exam, results=results)


@app.route('/teacher/dashboard')
@login_required
@role_required(['teacher'])
def teacher_dashboard():
    teacher = current_user()
    if not is_teacher_approved(teacher['id']):
        flash('Your teacher account is pending verification approval.', 'warning')
        return redirect(url_for('teacher_register_verification'))

    conn = get_db_connection()
    materials = conn.execute(
        '''
        SELECT * FROM study_materials
        WHERE teacher_id = ?
        ORDER BY created_at DESC
        ''',
        (teacher['id'],)
    ).fetchall()

    school_exams = conn.execute(
        '''
        SELECT se.*, c.standard, c.section,
               (SELECT COUNT(*) FROM school_exam_attempts sea WHERE sea.exam_id = se.id) as attempt_count
        FROM school_exams se
        JOIN classes c ON c.id = se.class_id
        WHERE se.created_by = ?
        ORDER BY se.created_at DESC
        ''',
        (teacher['id'],)
    ).fetchall()

    selected_section = (request.args.get('section') or '').strip().upper()
    subject_filter = (request.args.get('subject') or '').strip()
    teacher_standard = _clean_class_value(teacher['assigned_standard']) if 'assigned_standard' in teacher.keys() else ''
    teacher_section = _clean_section_value(teacher['assigned_section']) if 'assigned_section' in teacher.keys() else ''
    active_section = teacher_section or selected_section

    students = _get_teacher_visible_students(conn, teacher, section_override=selected_section)
    visible_student_ids = [student['id'] for student in students]

    # Backfill: update any activities/exam_attempts that have NULL teacher_id for our students
    if visible_student_ids:
        placeholders = ','.join('?' * len(visible_student_ids))
        conn.execute(
            f'''
            UPDATE activities
            SET teacher_id = ?
            WHERE student_id IN ({placeholders})
              AND (teacher_id IS NULL)
            ''',
            [teacher['id']] + visible_student_ids
        )
        conn.execute(
            f'''
            UPDATE activities
            SET class_id = (SELECT st.class_id FROM students st WHERE st.student_id = activities.student_id)
            WHERE student_id IN ({placeholders})
              AND class_id IS NULL
            ''',
            visible_student_ids
        )
        conn.execute(
            f'''
            UPDATE exam_attempts
            SET teacher_id = ?
            WHERE student_id IN ({placeholders})
              AND (teacher_id IS NULL)
            ''',
            [teacher['id']] + visible_student_ids
        )
        conn.execute(
            f'''
            UPDATE exam_attempts
            SET class_id = (SELECT st.class_id FROM students st WHERE st.student_id = exam_attempts.student_id)
            WHERE student_id IN ({placeholders})
              AND class_id IS NULL
            ''',
            visible_student_ids
        )
        conn.commit()

    activities = []
    exam_attempt_rows = []
    available_subjects = []
    
    # Use visible_student_ids for robust lookup — this does NOT depend on teacher_students JOIN
    # which may not exist at the exact time activities were logged
    if visible_student_ids:
        placeholders = ','.join('?' * len(visible_student_ids))
        activity_query = f'''
            SELECT a.id, a.student_id, a.action AS action_type, a.class_id, a.teacher_id,
                   a.subject, a.timestamp, a.details AS description,
                   u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM activities a
            JOIN users u ON u.id = a.student_id
            LEFT JOIN classes c ON c.id = a.class_id
            WHERE a.student_id IN ({placeholders})
        '''
        query_params = list(visible_student_ids)
    else:
        # Fallback: use teacher_students JOIN when we have no visible_student_ids
        activity_query = '''
            SELECT a.id, a.student_id, a.action AS action_type, a.class_id, a.teacher_id,
                   a.subject, a.timestamp, a.details AS description,
                   u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM activities a
            JOIN users u ON u.id = a.student_id
            JOIN teacher_students ts ON ts.student_id = a.student_id AND ts.teacher_id = ?
            LEFT JOIN classes c ON c.id = a.class_id
            WHERE 1=1
        '''
        query_params = [teacher['id']]

    
    if subject_filter:
        activity_query += " AND LOWER(TRIM(COALESCE(a.subject, ''))) = LOWER(TRIM(?))"
        query_params.append(subject_filter)
    if active_section:
        activity_query += " AND UPPER(TRIM(COALESCE(c.section, u.section, ''))) = ?"
        query_params.append(_clean_section_value(active_section))
    activity_query += ' ORDER BY a.timestamp DESC LIMIT 150'
    activities = conn.execute(activity_query, tuple(query_params)).fetchall()

    if visible_student_ids:
        placeholders_subj = ','.join('?' * len(visible_student_ids))
        subject_rows = conn.execute(
            f'''
            SELECT DISTINCT TRIM(COALESCE(a.subject, '')) AS subject
            FROM activities a
            WHERE a.student_id IN ({placeholders_subj})
              AND TRIM(COALESCE(a.subject, '')) != ''
            ORDER BY subject ASC
            ''',
            visible_student_ids
        ).fetchall()
    else:
        subject_rows = conn.execute(
            '''
            SELECT DISTINCT TRIM(COALESCE(a.subject, '')) AS subject
            FROM activities a
            JOIN teacher_students ts ON ts.student_id = a.student_id AND ts.teacher_id = ?
            WHERE TRIM(COALESCE(a.subject, '')) != ''
            ORDER BY subject ASC
            ''',
            (teacher['id'],)
        ).fetchall()
    available_subjects = [row['subject'] for row in subject_rows if row['subject']]

    # Exam attempts query — use visible_student_ids for robust lookup
    if visible_student_ids:
        placeholders_ea = ','.join('?' * len(visible_student_ids))
        exam_attempt_rows = conn.execute(
            f'''
            SELECT ea.*, u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM exam_attempts ea
            JOIN users u ON u.id = ea.student_id
            LEFT JOIN classes c ON c.id = ea.class_id
            WHERE ea.student_id IN ({placeholders_ea})
            ORDER BY COALESCE(ea.timestamp, ea.submitted_at) DESC
            LIMIT 120
            ''',
            visible_student_ids
        ).fetchall()
    else:
        exam_attempt_rows = conn.execute(
            '''
            SELECT ea.*, u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM exam_attempts ea
            JOIN users u ON u.id = ea.student_id
            JOIN teacher_students ts ON ts.student_id = ea.student_id AND ts.teacher_id = ?
            LEFT JOIN classes c ON c.id = ea.class_id
            ORDER BY COALESCE(ea.timestamp, ea.submitted_at) DESC
            LIMIT 120
            ''',
            (teacher['id'],)
        ).fetchall()

    if visible_student_ids:
        placeholders_alerts = ','.join('?' * len(visible_student_ids))
        alerts_query = f'''
            SELECT v.*, u.username AS student_name
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.student_id IN ({placeholders_alerts})
        '''
        alerts_params = list(visible_student_ids)
        if active_section:
            alerts_query += " AND UPPER(TRIM(COALESCE(v.section, ''))) = ?"
            alerts_params.append(_clean_section_value(active_section))
        alerts_query += ' ORDER BY v.timestamp DESC LIMIT 150'
        alerts = conn.execute(alerts_query, tuple(alerts_params)).fetchall()
    elif active_section:
        alerts = conn.execute(
            '''
            SELECT v.*, u.username AS student_name
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.teacher_id = ?
              AND UPPER(TRIM(COALESCE(v.section, ''))) = ?
            ORDER BY v.timestamp DESC
            LIMIT 150
            ''',
            (teacher['id'], _clean_section_value(active_section))
        ).fetchall()
    else:
        alerts = conn.execute(
            '''
            SELECT v.*, u.username AS student_name
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.teacher_id = ?
            ORDER BY v.timestamp DESC
            LIMIT 150
            ''',
            (teacher['id'],)
        ).fetchall()

    unread_notification_count = conn.execute(
        'SELECT COUNT(*) AS cnt FROM notifications WHERE teacher_id = ? AND is_read = 0',
        (teacher['id'],)
    ).fetchone()['cnt']

    if visible_student_ids:
        placeholders_risk = ','.join('?' * len(visible_student_ids))
        risk_query = f'''
            SELECT u.username AS student_name,
                   MAX(v.suspicion_score) AS max_score,
                   COUNT(v.id) AS total_violations
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.student_id IN ({placeholders_risk})
              AND v.is_high_risk = 1
        '''
        risk_params = list(visible_student_ids)
        if active_section:
            risk_query += " AND UPPER(TRIM(COALESCE(v.section, ''))) = ?"
            risk_params.append(_clean_section_value(active_section))
        risk_query += '''
            GROUP BY v.student_id, u.username
            ORDER BY max_score DESC, total_violations DESC
            LIMIT 20
        '''
        high_risk_students = conn.execute(risk_query, tuple(risk_params)).fetchall()
    elif active_section:
        high_risk_students = conn.execute(
            '''
            SELECT u.username AS student_name,
                   MAX(v.suspicion_score) AS max_score,
                   COUNT(v.id) AS total_violations
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.teacher_id = ?
              AND UPPER(TRIM(COALESCE(v.section, ''))) = ?
              AND v.is_high_risk = 1
            GROUP BY v.student_id, u.username
            ORDER BY max_score DESC, total_violations DESC
            LIMIT 20
            ''',
            (teacher['id'], _clean_section_value(active_section))
        ).fetchall()
    else:
        high_risk_students = conn.execute(
            '''
            SELECT u.username AS student_name,
                   MAX(v.suspicion_score) AS max_score,
                   COUNT(v.id) AS total_violations
            FROM violations v
            JOIN users u ON u.id = v.student_id
            WHERE v.teacher_id = ?
              AND v.is_high_risk = 1
            GROUP BY v.student_id, u.username
            ORDER BY max_score DESC, total_violations DESC
            LIMIT 20
            ''',
            (teacher['id'],)
        ).fetchall()
    
    conn.close()

    print(f'[Dashboard Load] teacher_id={teacher["id"]} activities={len(activities)} exam_attempts={len(exam_attempt_rows)} students={len(students)}')

    student_group_label = _class_group_label(teacher_standard, active_section)
    available_sections = []
    if teacher_standard and not teacher_section:
        sections_conn = get_db_connection()
        section_rows = sections_conn.execute(
            '''
            SELECT DISTINCT TRIM(COALESCE(section, '')) AS section
            FROM users
            WHERE role IN ('student', 'college_student')
              AND TRIM(COALESCE(standard, '')) = ?
              AND TRIM(COALESCE(section, '')) != ''
            ORDER BY section ASC
            ''',
            (teacher_standard,)
        ).fetchall()
        sections_conn.close()
        available_sections = [row['section'] for row in section_rows if row['section']]

    return render_template(
        'teacher_dashboard.html',
        materials=materials,
        alerts=alerts,
        activities=activities,
        students=students,
        student_group_label=student_group_label,
        teacher_standard=teacher_standard,
        teacher_section=teacher_section,
        active_section=active_section,
        available_sections=available_sections,
        available_subjects=available_subjects,
        selected_subject=subject_filter,
        exam_attempt_rows=exam_attempt_rows,
        unread_notification_count=unread_notification_count,
        high_risk_students=high_risk_students,
        school_exams=school_exams,
    )


@app.route('/teacher/activity_logs')
@login_required
@role_required(['teacher'])
def teacher_activity_logs():
    teacher = current_user()
    if not is_teacher_approved(teacher['id']):
        return jsonify({'ok': False, 'message': 'Teacher account not approved.'}), 403

    section_filter = _clean_section_value(request.args.get('section') or '')
    conn = get_db_connection()

    student_id_filter = request.args.get('student_id', type=int)
    activity_type_filter = (request.args.get('action_type') or '').strip()
    subject_filter = (request.args.get('subject') or '').strip()
    date_filter = (request.args.get('date') or '').strip()

    # Get visible students for this teacher — robust lookup
    students = _get_teacher_visible_students(conn, teacher, section_override=section_filter)
    visible_student_ids = [s['id'] for s in students]

    if visible_student_ids:
        placeholders = ','.join('?' * len(visible_student_ids))
        query = f'''
            SELECT a.id, a.student_id, a.action AS action_type, a.class_id, a.teacher_id,
                   a.subject, a.timestamp, a.details AS description,
                   u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM activities a
            JOIN users u ON u.id = a.student_id
            LEFT JOIN classes c ON c.id = a.class_id
            WHERE a.student_id IN ({placeholders})
        '''
        params = list(visible_student_ids)
    else:
        query = '''
            SELECT a.id, a.student_id, a.action AS action_type, a.class_id, a.teacher_id,
                   a.subject, a.timestamp, a.details AS description,
                   u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM activities a
            JOIN users u ON u.id = a.student_id
            JOIN teacher_students ts ON ts.student_id = a.student_id AND ts.teacher_id = ?
            LEFT JOIN classes c ON c.id = a.class_id
            WHERE 1=1
        '''
        params = [teacher['id']]

    if activity_type_filter:
        query += ' AND a.action = ?'
        params.append(activity_type_filter)
    if subject_filter:
        query += " AND LOWER(TRIM(COALESCE(a.subject, ''))) = LOWER(TRIM(?))"
        params.append(subject_filter)
    if date_filter:
        query += ' AND DATE(a.timestamp) = ?'
        params.append(date_filter)
    if section_filter:
        query += " AND UPPER(TRIM(COALESCE(c.section, ''))) = ?"
        params.append(section_filter)
    if student_id_filter:
        query += ' AND a.student_id = ?'
        params.append(student_id_filter)

    query += ' ORDER BY a.timestamp DESC LIMIT 300'
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    activities = [dict(row) for row in rows]
    print(
        f'[Teacher Activities] teacher_id={teacher["id"]} rows={len(activities)} '
        f'filters={{"student_id": {student_id_filter}, "action_type": "{activity_type_filter}", '
        f'"subject": "{subject_filter}", "date": "{date_filter}", "section": "{section_filter}"}}'
    )
    return jsonify({'ok': True, 'activities': activities})


@app.route('/teacher/exam_attempts')
@login_required
@role_required(['teacher'])
def teacher_exam_attempts():
    teacher = current_user()
    if not is_teacher_approved(teacher['id']):
        return jsonify({'ok': False, 'message': 'Teacher account not approved.'}), 403

    student_id_filter = request.args.get('student_id', type=int)
    class_id_filter = request.args.get('class_id', type=int)
    section_filter = _clean_section_value(request.args.get('section') or '')
    exam_id_filter = (request.args.get('exam_id') or '').strip()
    subject_filter = (request.args.get('subject') or '').strip()
    date_filter = (request.args.get('date') or '').strip()

    conn = get_db_connection()
    
    # Get visible students for this teacher — robust lookup
    students = _get_teacher_visible_students(conn, teacher, section_override=section_filter)
    visible_student_ids = [s['id'] for s in students]

    if visible_student_ids:
        placeholders = ','.join('?' * len(visible_student_ids))
        query = f'''
            SELECT ea.*, u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM exam_attempts ea
            JOIN users u ON u.id = ea.student_id
            LEFT JOIN classes c ON c.id = ea.class_id
            WHERE ea.student_id IN ({placeholders})
        '''
        params = list(visible_student_ids)
    else:
        query = '''
            SELECT ea.*, u.username AS student_name, c.standard AS class_standard, c.section AS class_section
            FROM exam_attempts ea
            JOIN users u ON u.id = ea.student_id
            JOIN teacher_students ts ON ts.student_id = ea.student_id AND ts.teacher_id = ?
            LEFT JOIN classes c ON c.id = ea.class_id
            WHERE 1=1
        '''
        params = [teacher['id']]

    if student_id_filter:
        query += ' AND ea.student_id = ?'
        params.append(student_id_filter)
    if class_id_filter:
        query += ' AND ea.class_id = ?'
        params.append(class_id_filter)
    if section_filter:
        query += " AND UPPER(TRIM(COALESCE(c.section, ''))) = ?"
        params.append(section_filter)
    if exam_id_filter:
        query += ' AND ea.exam_id = ?'
        params.append(exam_id_filter)
    if subject_filter:
        query += " AND LOWER(TRIM(COALESCE(ea.subject, ''))) = LOWER(TRIM(?))"
        params.append(subject_filter)
    if date_filter:
        query += ' AND DATE(COALESCE(ea.timestamp, ea.submitted_at)) = ?'
        params.append(date_filter)

    query += ' ORDER BY COALESCE(ea.timestamp, ea.submitted_at) DESC LIMIT 300'
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    return jsonify({'ok': True, 'exam_attempts': [dict(row) for row in rows]})


@app.route('/teacher_activities')
@login_required
@role_required(['teacher'])
def teacher_activities():
    # Compatibility endpoint for dashboards expecting this URL.
    return redirect(url_for('teacher_dashboard'))


@app.route('/upload_material', methods=['POST'])
@login_required
@role_required(['teacher'])
def upload_material():
    teacher = current_user()
    if not is_teacher_approved(teacher['id']):
        return jsonify({'ok': False, 'message': 'Teacher account not approved.'}), 403

    title = (request.form.get('title') or '').strip()
    subject = (request.form.get('subject') or '').strip()
    topic = (request.form.get('topic') or '').strip()
    material_type = (request.form.get('material_type') or 'file').strip().lower()
    video_link = (request.form.get('video_link') or '').strip()
    material_file = request.files.get('material_file')

    if not (title and subject and topic):
        return jsonify({'ok': False, 'message': 'Title, subject, and topic are required.'}), 400

    stored_filename = None
    if material_type == 'video':
        if not video_link:
            return jsonify({'ok': False, 'message': 'Video link is required for video material.'}), 400
    else:
        if not material_file or not material_file.filename:
            return jsonify({'ok': False, 'message': 'Material file is required.'}), 400
        if not _is_allowed_material_file(material_file.filename):
            return jsonify({'ok': False, 'message': 'Unsupported file type.'}), 400
        stored_filename = _material_storage_name(teacher['id'], material_file.filename)
        material_file.save(os.path.join(STUDY_MATERIAL_UPLOAD_DIR, stored_filename))
        material_type = 'file'

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT INTO study_materials
        (teacher_id, title, subject, topic, material_type, file_path, video_link, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (teacher['id'], title, subject, topic, material_type, stored_filename, video_link, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({'ok': True, 'message': 'Material uploaded successfully.'})


@app.route('/get_materials')
@login_required
def get_materials():
    subject = (request.args.get('subject') or '').strip()
    topic = (request.args.get('topic') or '').strip()

    conn = get_db_connection()
    query = '''
        SELECT sm.*, u.username AS teacher_name
        FROM study_materials sm
        JOIN users u ON u.id = sm.teacher_id
        WHERE 1=1
    '''
    params = []
    if subject:
        query += ' AND sm.subject = ?'
        params.append(subject)
    if topic:
        query += ' AND sm.topic = ?'
        params.append(topic)
    query += ' ORDER BY sm.created_at DESC'
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    data = []
    for row in rows:
        item = dict(row)
        if item.get('file_path'):
            item['download_url'] = url_for('download_material', material_id=item['id'])
        data.append(item)

    return jsonify({'ok': True, 'materials': data})


@app.route('/download_material/<int:material_id>')
@login_required
def download_material(material_id):
    conn = get_db_connection()
    material = conn.execute('SELECT * FROM study_materials WHERE id = ?', (material_id,)).fetchone()
    conn.close()
    if not material or not material['file_path']:
        flash('Material file not found.', 'danger')
        return redirect(url_for('dashboard'))
    return send_from_directory(STUDY_MATERIAL_UPLOAD_DIR, material['file_path'], as_attachment=True)


@app.route('/start_test', methods=['GET'])
@login_required
@role_required(['student', 'college_student'])
def start_test():
    user = current_user()
    subject = (request.args.get('subject') or '').strip()
    mapped_subject = resolve_exam_subject(subject)
    if not mapped_subject:
        return jsonify({'ok': False, 'message': 'Invalid subject for weekly test.'}), 400

    test = _ensure_weekly_test(mapped_subject)
    if not test:
        return jsonify({'ok': False, 'message': 'Unable to create weekly test for this subject.'}), 400

    conn = get_db_connection()
    questions_rows = conn.execute(
        'SELECT * FROM weekly_test_questions WHERE test_id = ? ORDER BY id ASC',
        (test['id'],)
    ).fetchall()
    conn.close()

    bank_map = {q['id']: q for q in EXAM_QUESTION_BANK.get(mapped_subject, [])}
    selected_questions = [bank_map[row['question_id']] for row in questions_rows if row['question_id'] in bank_map]

    exam_session_id = f'weekly-{user["id"]}-{int(time.time() * 1000)}'
    answer_key = {}
    public_questions = []

    for q in selected_questions:
        option_pairs = [{'text': txt, 'original_idx': idx} for idx, txt in enumerate(q['options'])]
        random.shuffle(option_pairs)
        shuffled_options = [pair['text'] for pair in option_pairs]
        remapped_correct = next(i for i, pair in enumerate(option_pairs) if pair['original_idx'] == q['answer'])
        answer_key[q['id']] = remapped_correct
        public_questions.append({'id': q['id'], 'question': q['question'], 'options': shuffled_options, 'marks': 5})

    weekly_active_tests = session.get('weekly_active_tests', {})
    weekly_active_tests[exam_session_id] = {
        'test_id': test['id'],
        'subject': mapped_subject,
        'answer_key': answer_key,
        'started_at': datetime.now().isoformat(),
    }
    session['weekly_active_tests'] = weekly_active_tests

    log_activity(
        user['id'],
        'start_weekly_test',
        f'Started weekly test in {mapped_subject} ({WEEKLY_TEST_MAX_MARKS} marks).',
        subject=mapped_subject
    )

    return jsonify({
        'ok': True,
        'exam_session_id': exam_session_id,
        'test_id': test['id'],
        'subject': mapped_subject,
        'total_marks': WEEKLY_TEST_MAX_MARKS,
        'duration_seconds': 1800,
        'questions': public_questions,
    })


@app.route('/submit_test', methods=['POST'])
@login_required
@role_required(['student', 'college_student'])
def submit_test():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    exam_session_id = (payload.get('exam_session_id') or '').strip()
    answers = payload.get('answers', {})

    if not exam_session_id:
        return jsonify({'ok': False, 'message': 'Missing exam_session_id.'}), 400
    if not isinstance(answers, dict):
        return jsonify({'ok': False, 'message': 'Answers must be an object.'}), 400

    weekly_active_tests = session.get('weekly_active_tests', {})
    active = weekly_active_tests.get(exam_session_id)
    if not active:
        return jsonify({'ok': False, 'message': 'Test session expired. Start again.'}), 400

    answer_key = active.get('answer_key', {})
    total_questions = len(answer_key)
    correct = 0
    details = []

    for qid, correct_idx in answer_key.items():
        submitted = answers.get(qid)
        try:
            selected = int(submitted) if submitted is not None else None
        except (TypeError, ValueError):
            selected = None
        is_correct = selected == correct_idx
        if is_correct:
            correct += 1
        details.append({'question_id': qid, 'selected': selected, 'correct': correct_idx, 'is_correct': is_correct})

    obtained_marks = correct * 5
    total_marks = total_questions * 5

    submitted_at = datetime.now().isoformat()

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT OR REPLACE INTO weekly_test_results
        (id, user_id, test_id, exam_session_id, subject, obtained_marks, total_marks, answer_json, submitted_at)
        VALUES (
            (SELECT id FROM weekly_test_results WHERE user_id = ? AND test_id = ?),
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        ''',
        (
            user['id'], active['test_id'],
            user['id'], active['test_id'], exam_session_id, active.get('subject', ''),
            obtained_marks, total_marks, json.dumps(details), submitted_at
        )
    )

    _record_exam_attempt(
        conn=conn,
        student_id=user['id'],
        exam_id=exam_session_id,
        subject=active.get('subject', ''),
        score=obtained_marks,
        total_questions=total_questions,
        time_taken_seconds=None,
        details_json=json.dumps(details),
        submitted_at=submitted_at,
    )

    profile = conn.execute('SELECT parent_phone FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    conn.commit()
    conn.close()

    weekly_active_tests.pop(exam_session_id, None)
    session['weekly_active_tests'] = weekly_active_tests

    log_activity(
        user['id'],
        'submit_weekly_test',
        f'Completed weekly test in {active.get("subject", "")}. Score {obtained_marks}/{total_marks}.',
        subject=active.get('subject', '')
    )

    sms_status = {'sent': False, 'message': 'Parent phone not available.'}
    parent_phone = (profile['parent_phone'] or '').strip() if profile and 'parent_phone' in profile.keys() else ''
    if parent_phone:
        sms_text = f'Your child scored {obtained_marks}/{total_marks} in this week\'s {active.get("subject", "")} test.'
        sent, info = _send_sms_message(parent_phone, sms_text)
        sms_status = {'sent': sent, 'message': info}

    return jsonify({
        'ok': True,
        'subject': active.get('subject', ''),
        'obtained_marks': obtained_marks,
        'total_marks': total_marks,
        'percentage': round((obtained_marks / total_marks) * 100) if total_marks else 0,
        'details': details,
        'sms_status': sms_status,
    })


def _log_violation_event(conn, student_id, violation_type, details='', exam_session_id='', class_id=None, section=''):
    violation_type = (violation_type or '').strip() or 'unknown'
    details = (details or '').strip()
    section = _clean_section_value(section)

    student_row = conn.execute(
        'SELECT class_id, section FROM students WHERE student_id = ? LIMIT 1',
        (student_id,)
    ).fetchone()
    resolved_class_id = class_id if class_id is not None else (student_row['class_id'] if student_row else None)
    resolved_section = section or (_clean_section_value(student_row['section']) if student_row else '')

    teacher_id = None
    if resolved_class_id is not None and resolved_section:
        teacher_row = conn.execute(
            '''
            SELECT teacher_id
            FROM teachers
            WHERE class_id = ?
              AND UPPER(TRIM(COALESCE(section, ''))) = ?
            ORDER BY teacher_id ASC
            LIMIT 1
            ''',
            (resolved_class_id, resolved_section)
        ).fetchone()
        teacher_id = teacher_row['teacher_id'] if teacher_row else None

    test_id = None
    if exam_session_id:
        weekly_active_tests = session.get('weekly_active_tests', {})
        active = weekly_active_tests.get(exam_session_id)
        if active:
            test_id = active.get('test_id')
            if teacher_id is None:
                test = conn.execute('SELECT teacher_id FROM weekly_tests WHERE id = ?', (test_id,)).fetchone()
                teacher_id = test['teacher_id'] if test else None

    score_delta = int(VIOLATION_SCORE_MAP.get(violation_type, 1))
    existing_score = conn.execute(
        '''
        SELECT COALESCE(MAX(suspicion_score), 0) AS score
        FROM violations
        WHERE student_id = ?
          AND COALESCE(exam_session_id, '') = COALESCE(?, '')
        ''',
        (student_id, exam_session_id)
    ).fetchone()
    suspicion_score = int((existing_score['score'] if existing_score else 0) or 0) + score_delta
    is_high_risk = 1 if suspicion_score >= VIOLATION_SUSPICION_THRESHOLD else 0

    now_iso = datetime.now().isoformat()
    cur = conn.execute(
        '''
        INSERT INTO violations (
            student_id, teacher_id, class_id, section, test_id, exam_session_id,
            violation_type, score_delta, suspicion_score, is_high_risk, timestamp, details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            student_id, teacher_id, resolved_class_id, resolved_section, test_id, exam_session_id,
            violation_type, score_delta, suspicion_score, is_high_risk, now_iso, details
        )
    )
    violation_id = cur.lastrowid

    # Legacy compatibility table.
    conn.execute(
        '''
        INSERT INTO test_violations (user_id, teacher_id, test_id, event_type, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (student_id, teacher_id, test_id, violation_type, details, now_iso)
    )

    if teacher_id:
        student_row_name = conn.execute('SELECT username FROM users WHERE id = ? LIMIT 1', (student_id,)).fetchone()
        student_name = student_row_name['username'] if student_row_name else f'Student {student_id}'
        notif_message = f'⚠️ {student_name} {violation_type.replace("_", " ")} (score: {suspicion_score})'
        conn.execute(
            '''
            INSERT INTO notifications (teacher_id, violation_id, message, is_read, timestamp)
            VALUES (?, ?, ?, 0, ?)
            ''',
            (teacher_id, violation_id, notif_message, now_iso)
        )

    return {
        'teacher_id': teacher_id,
        'class_id': resolved_class_id,
        'section': resolved_section,
        'score_delta': score_delta,
        'suspicion_score': suspicion_score,
        'is_high_risk': bool(is_high_risk),
    }


def _safe_debug_print(message):
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            import sys
            sys.stdout.buffer.write((str(message) + '\n').encode('utf-8', errors='ignore'))
            sys.stdout.flush()
        except Exception:
            print(str(message).encode('ascii', errors='ignore').decode('ascii') or 'DEBUG')


@app.route('/log_violation', methods=['POST'])
def log_violation():
    data = request.json

    print("API CALLED")
    print(data)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO violations (student_id, violation_type, details, timestamp)
        VALUES (?, ?, ?, ?)
    """, (
        data['student_id'],
        data['violation_type'],
        data['details'],
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.route('/detect_violation', methods=['POST'])
@login_required
@role_required(['student', 'college_student'])
def detect_violation():
    # Backward-compatible alias for existing clients.
    return log_violation()


@app.route('/send_sms', methods=['POST'])
@login_required
def send_sms():
    payload = request.get_json(silent=True) or {}
    phone = (payload.get('phone') or '').strip()
    message = (payload.get('message') or '').strip()
    if not (phone and message):
        return jsonify({'ok': False, 'message': 'phone and message are required.'}), 400
    sent, info = _send_sms_message(phone, message)
    return jsonify({'ok': sent, 'message': info})


@app.route('/weekly_test')
@login_required
@role_required(['student', 'college_student'])
def weekly_test_page():
    conn = get_db_connection()
    user = current_user()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (user['id'],)).fetchone()
    student_ctx = conn.execute(
        'SELECT class_id, section FROM students WHERE student_id = ? LIMIT 1',
        (user['id'],)
    ).fetchone()
    conn.close()
    subjects = get_subjects_for_grade(profile['grade'] if profile else None, profile['student_type'] if profile else None)
    test_subjects = list(dict.fromkeys(subjects + list(EXAM_QUESTION_BANK.keys())))
    return render_template(
        'weekly_test.html',
        subjects=test_subjects,
        student_id=user['id'],
        student_class_id=(student_ctx['class_id'] if student_ctx else None),
        student_section=(_clean_section_value(student_ctx['section']) if student_ctx else ''),
    )


@app.route('/test_page')
@login_required
@role_required(['student', 'college_student'])
def test_page():
    # Compatibility endpoint for clients that navigate to /test_page after start.
    return redirect(url_for('weekly_test_page'))


@app.route('/materials')
@login_required
@role_required(['student', 'college_student'])
def materials_page():
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM student_profile WHERE user_id = ?', (current_user()['id'],)).fetchone()
    conn.close()
    subjects = get_subjects_for_grade(profile['grade'] if profile else None, profile['student_type'] if profile else None)
    material_subjects = list(dict.fromkeys(subjects + list(EXAM_QUESTION_BANK.keys())))
    return render_template('materials.html', subjects=material_subjects)


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
        print(f"[Email] Connecting to {smtp_server}:{smtp_port}")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        print(f"[Email] Logging in as {smtp_user}")
        server.login(smtp_user, smtp_password)
        print(f"[Email] Sending email to {recipient}")
        server.send_message(msg)
        server.quit()
        print(f"[Email] ✓ Successfully sent to {recipient}")
        return True
    except Exception as e:
        print(f"[Email] ✗ Error sending email to {recipient}: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_all_automatic_reminders():
    auto_enabled = os.environ.get('AUTO_REMINDERS_ENABLED', 'true').strip().lower() == 'true'
    if not auto_enabled:
        return

    print(f"[{datetime.now().isoformat()}] Running automatic background reminders...")
    conn = None
    try:
        conn = get_db_connection()
        # Get all users with valid email addresses (send to EVERYONE every hour)
        users = conn.execute('''
            SELECT u.id, u.username, u.email, u.last_login_at,
                   p.subjects, p.daily_goal, p.parent_email, p.student_type,
                   p.full_name, p.grade, p.board, p.department, p.school
            FROM users u
            JOIN student_profile p ON u.id = p.user_id
            WHERE u.email IS NOT NULL AND u.email != ''
        ''').fetchall()
        
        if not users:
            print("[Reminders] No users found with email addresses")
            return
        
        print(f"[Reminders] Found {len(users)} users to send reminders to")
        sent_count = 0
        failed_count = 0
        
        for u in users:
            email = u['email']
            
            # Get user's reminder settings (if any)
            reminder = conn.execute('SELECT * FROM reminders WHERE user_id = ? ORDER BY id DESC LIMIT 1',
                                    (u['id'],)).fetchone()
            
            # Send to all users regardless of reminder enabled status
            # (enabled status just controls whether user set up reminders)
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
                # Update last_sent timestamp for tracking
                if reminder:
                    conn.execute('UPDATE reminders SET last_sent = ? WHERE id = ?',
                                 (datetime.now().isoformat(), reminder['id']))
                else:
                    # Create reminder record if it doesn't exist
                    conn.execute('INSERT INTO reminders (user_id, is_enabled, last_sent) VALUES (?, 1, ?)',
                                 (u['id'], datetime.now().isoformat()))
                conn.commit()
                print(f"[Reminders] ✓ Sent to {email}")
                sent_count += 1
                
                # Also send to parent if set
                parent_email = u['parent_email'] if 'parent_email' in u.keys() else None
                if parent_email and parent_email != email:
                    parent_success = send_email_reminder(
                        payload['user_id'], parent_email, payload['mandatory_subject'],
                        payload['topic'], payload['minutes'], payload['extra_subjects'],
                        payload['student_type'], payload['full_name'],
                        payload['grade_or_stream'], payload['board'],
                        payload['department'], payload['school_or_college']
                    )
                    if parent_success:
                        print(f"[Reminders] ✓ Sent to parent {parent_email}")
                        sent_count += 1
            else:
                print(f"[Reminders] ✗ Failed to send to {email}")
                failed_count += 1
        
        print(f"[Reminders] Summary: {sent_count} sent, {failed_count} failed")
    except Exception as e:
        print(f"[Reminders] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()


def start_scheduler():
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("Scheduler: Skipping in debug reload process")
        return None

    auto_enabled = os.environ.get('AUTO_REMINDERS_ENABLED', 'true').strip().lower() == 'true'
    if not auto_enabled:
        print("Scheduler: AUTO_REMINDERS_ENABLED is disabled")
        return None

    try:
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
        print(f"Scheduler: Started successfully with {reminder_interval_hours} hour interval")
        print(f"Scheduler: SMTP_USER = {os.environ.get('SMTP_USER')}")
        print(f"Scheduler: AUTO_REMINDERS_ENABLED = {auto_enabled}")
        return scheduler
    except Exception as e:
        print(f"Scheduler: Error starting scheduler - {e}")
        import traceback
        traceback.print_exc()
        return None

scheduler = start_scheduler()

@app.route('/test_reminders', methods=['GET'])
def test_reminders():
    """Test endpoint to manually trigger reminders"""
    from flask import jsonify
    print("\n[TEST] Manual reminder trigger started...")
    send_all_automatic_reminders()
    return jsonify({'status': 'Reminder job executed. Check console logs for details.'})

@app.route('/student_exams')
@login_required
def student_exams_view():
    user = current_user()
    if not user:
        return redirect('/login')
    student_id = user['id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student class & section
    cursor.execute("""
        SELECT class_id, section FROM students
        WHERE student_id=?
    """, (student_id,))
    
    student = cursor.fetchone()

    if not student:
        return "Student not found"

    class_id = str(student[0]).strip() if student[0] else ''
    section = str(student[1]).strip() if student[1] else ''

    print("STUDENT:", class_id, section)

    # 🔥 FETCH EXAMS
    cursor.execute("""
        SELECT * FROM school_exams
        WHERE TRIM(class_id)=TRIM(?)
        AND TRIM(section)=TRIM(?)
        AND is_published=1
    """, (class_id, section))

    exams = cursor.fetchall()
    conn.close()

    print("EXAMS:", exams)

    return render_template("exams.html", exams=exams)


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            init_db()
        ensure_schema_updates()
    app.run(debug=True)
