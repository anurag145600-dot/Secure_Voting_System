import random
import sqlite3
from datetime import datetime

from flask import Flask, session, redirect, render_template, request
from werkzeug.security import generate_password_hash, check_password_hash
from phe import paillier

# ------------------ APP SETUP ------------------
app = Flask(__name__)
app.secret_key = "mysecret123"

# ------------------ DATABASE ------------------
def get_db():
    return sqlite3.connect("database.db")

def create_tables():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        voter_id TEXT PRIMARY KEY,
        name TEXT,
        address TEXT,
        phone TEXT,
        password TEXT,
        gender TEXT,
        eligible INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_id TEXT,
        vote INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        voter_id TEXT,
        time TEXT
    )
    """)

    db.commit()
    db.close()

create_tables()

# ------------------ ADMIN ------------------
ADMIN_USER = "admin"
ADMIN_PASS = "1234"

voting_open = True   # GLOBAL VARIABLE TO TRACK VOTING STATUS

ELIGIBLE_VOTERS = ["voter1", "voter2", "voter3"]

# ------------------ ENCRYPTION ------------------
public_key, private_key = paillier.generate_paillier_keypair()

# ------------------ HOME (START HERE) ------------------
@app.route('/')
def home():
    return redirect('/register')   # FIRST PAGE = REGISTER

# ------------------ REGISTER ------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        voter_id = request.form['voter_id']

        db = get_db()
        cursor = db.cursor()

        hashed_password = generate_password_hash(request.form['password'])

        try:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                voter_id,
                request.form['name'],
                request.form['address'],
                request.form['phone'],
                hashed_password,
                request.form['gender'],
                1
            ))
        except:
            db.close()
            return "User already exists!"

        db.commit()
        db.close()

        return redirect('/login')

    return render_template('register.html')

# ------------------ LOGIN ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()

        voter_id = request.form['voter_id']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE voter_id=?", (voter_id,))
        user = cursor.fetchone()

        if user and check_password_hash(user[4], password):

            cursor.execute("INSERT INTO logs VALUES (NULL, ?, ?, ?)",
                           ("LOGIN", voter_id, str(datetime.now())))

            db.commit()
            db.close()

            session['user'] = voter_id

            otp = str(random.randint(1000, 9999))
            session['otp'] = otp

            print("OTP:", otp)

            return redirect('/otp')

        db.close()
        return "Invalid credentials"

    return render_template('login.html')

# ------------------ OTP ------------------
@app.route('/otp', methods=['GET', 'POST'])
def otp():
    if request.method == 'POST':
        if request.form['otp'] == session.get('otp'):
            session['verified'] = True
            return redirect('/vote_page')   # GO TO VOTING PAGE
        else:
            return "Wrong OTP"

    return render_template('otp.html')

# ------------------ VOTE PAGE ------------------
@app.route('/vote_page')
def vote_page():
    if not session.get('verified'):
        return redirect('/login')

    return render_template('vote.html')

# ------------------ VOTE ------------------
@app.route('/vote', methods=['POST'])
def vote():
    if not session.get('verified'):
        return redirect('/login')
    if not voting_open:
        return render_template('success.html', message="Voting is closed!")

    db = get_db()
    cursor = db.cursor()

    voter_id = session['user']
    choice = int(request.form['candidate'])

    cursor.execute("SELECT * FROM votes WHERE voter_id=?", (voter_id,))
    if cursor.fetchone():
        db.close()
        return "You have already voted!"

    cursor.execute("INSERT INTO votes (voter_id, vote) VALUES (?, ?)",
                   (voter_id, choice))

    cursor.execute("INSERT INTO logs VALUES (NULL, ?, ?, ?)",
                   ("VOTE_CAST", voter_id, str(datetime.now())))

    db.commit()
    db.close()

    return render_template('success.html')

# ------------------ ADMIN LOGIN ------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['admin'] = True
            return redirect('/dashboard')
        else:
            return "Invalid Admin Login"

    return render_template('admin_login.html')

# ------------------ DASHBOARD ------------------
@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return "Access Denied"
    return render_template('admin_dashboard.html')

#close voting
# ------------------ CLOSE VOTING ------------------
voting_open = True   # 👈 add this ONLY ONCE at top of file (see below)

@app.route('/close_voting')
def close_voting():
    if not session.get('admin'):
        return "Access Denied"

    global voting_open
    voting_open = False

    return "Voting has been closed!"

#view voters
@app.route('/voters')
def voters():
    if not session.get('admin'):
        return "Access Denied"

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT voter_id, name, address, phone FROM users")
    data = cursor.fetchall()

    db.close()

    return render_template('voters.html', data=data)

# ------------------ RESULT ------------------
@app.route('/result')
def result():
    if not session.get('admin'):
        return "Access Denied"

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM votes WHERE vote=1")
    A = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM votes WHERE vote=0")
    B = cursor.fetchone()[0]

    cursor.execute("""
    SELECT gender, COUNT(*) 
    FROM votes 
    JOIN users ON votes.voter_id = users.voter_id 
    GROUP BY gender
    """)

    gender_data = dict(cursor.fetchall())

    db.close()

    return render_template(
        'result.html',
        A=A,
        B=B,
        male=gender_data.get('male', 0),
        female=gender_data.get('female', 0)
    )

# ------------------ RUN ------------------
if __name__ == '__main__':
    app.run(debug=True)