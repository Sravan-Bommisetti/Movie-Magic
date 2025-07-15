from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.security import generate_password_hash
import qrcode
from flask import send_file
import uuid
import hashlib
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import white, HexColor
from reportlab.lib.utils import ImageReader
import smtplib
from email.message import EmailMessage
import qrcode
import os

app = Flask(__name__)
app.secret_key = '77038c4a4d4f5e9dabf7d8b15873e78c'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movie_magic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------- Models ----------------------
class User(db.Model):
    email = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(200))

class Booking(db.Model):
    booking_id = db.Column(db.String(100), primary_key=True)
    user_email = db.Column(db.String(100))
    movie = db.Column(db.String(100))
    theater = db.Column(db.String(100))
    price = db.Column(db.String(10))
    time = db.Column(db.String(20))
    seats = db.Column(db.String(100))

# ---------------------- Movie Data----------------------

MOVIES = [
    {
        'title': 'DEVARA',
        'poster_filename': 'devara.jpg',
        'teaser_url': 'https://www.youtube.com/embed/rc61YHl1PFY',
        'theaters': [
            {
                'name': 'M1 CINEMA, NELLORE',
                'price': 250,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            {
                'name': 'SIRI COMPLEX, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM'],
                    'TOMORROW': ['2:00 PM','6:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM']
                }
            },
            {
                'name': 'MANASA, KAVALI',
                'price': 220,
                'timings_by_day': {
                    'TODAY': ['7:00 AM', '12:00 PM', '4:00 PM', '10:10 PM'],
                    'TOMORROW': ['7:00 AM', '12:00 PM', '6:30 PM'],
                    'DAY OF TOMORROW': ['11:00 AM', '6:50 PM']
                }
            },
            {
                'name': 'M GB, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            
        ]
    },
    {
        'title': 'RAJA SAAB',
        'poster_filename': 'rajasaab.jpg',
        'teaser_url': 'https://www.youtube.com/embed/NZbmcl0QUaU',
        'theaters': [
            {
                'name': 'M1 CINEMA, NELLORE',
                'price': 250,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            {
                'name': 'SIRI COMPLEX, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM'],
                    'TOMORROW': ['2:00 PM','6:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM']
                }
            },
             {
                'name': 'M G B, NELLORE',
                'price': 300,
                'timings_by_day': {
                    'TODAY': ['6:00 AM','8:00 AM', '12:00 PM', '6:00 PM'],
                    'TOMORROW': ['7:00 AM','6:00 PM','10:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM','10:00 PM']
                }
            },
           
            {
                'name': 'M G B, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            {
                'name': 'P.V.R, Hyderabad',
                'price': 220,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM'],
                    'TOMORROW': ['2:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM']
                }
            }
        ]
    },
    {
        'title': 'HIT 3',
        'poster_filename': 'hit3.jpg',
        'teaser_url': 'https://www.youtube.com/embed/XhW3i2f54BQ',
        'theaters': [
            {
                'name': 'M1 CINEMA, NELLORE',
                'price': 250,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            {
                'name': 'SIRI COMPLEX, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM'],
                    'TOMORROW': ['2:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM']
                }
            },
            {
                'name': 'MANASA, KAVALI',
                'price': 220,
                'timings_by_day': {
                    'TODAY': ['7:00 AM', '12:00 PM', '4:00 PM', '10:10 PM'],
                    'TOMORROW': ['7:00 AM', '12:00 PM', '6:30 PM'],
                    'DAY OF TOMORROW': ['11:00 AM', '6:50 PM']
                }
            },
            {
                'name': 'M GB, NELLORE',
                'price': 200,
                'timings_by_day': {
                    'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            },
            {
                'name': 'P.V.R, Hyderabad',
                'price': 220,
                'timings_by_day': {
                   'TODAY': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM'],
                    'TOMORROW': ['2:00 PM', '3:00 PM', '6:10 PM'],
                    'DAY OF TOMORROW': ['8:00 AM', '12:00 PM', '3:00 PM', '6:10 PM']
                }
            }
        ]
    }
]



# ----------------------  Email Setup ---------------------
EMAIL_ADDRESS = 'your_email@gmail.com'
EMAIL_PASSWORD = 'your_gmail_app_password'

# ---------------------- Utilities ----------------------
def get_current_user():
    return User.query.get(session['email']) if 'email' in session else None

def get_user_bookings(email):
    return Booking.query.filter_by(user_email=email).all()

def email_ticket_pdf(to_email, pdf_buffer, booking):
    try:
        msg = EmailMessage()
        msg['Subject'] = '🎟️ Your Movie Ticket'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg.set_content(f"""
🎬 Movie: {booking.movie}
🎭 Theater: {booking.theater}
🕒 Time: {booking.time}
💺 Seats: {booking.seats}
🆔 Booking ID: {booking.booking_id}
""")
        msg.add_attachment(pdf_buffer.read(), maintype='application', subtype='pdf', filename='ticket.pdf')
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)

# ---------------------- Routes ----------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = generate_password_hash(request.form['password'])  # ✅ Secure hashing

        existing_user = User.query.get(email)
        if existing_user:
            flash("Email already registered. Please reset your password.")
            return redirect(url_for('reset_password', email=email))
        else:
            new_user = User(email=email, name=name, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! You can now login.")
            return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email') or ''
    if request.method == 'POST':
        email = request.form['email']
        new_password = generate_password_hash(request.form['password'])  # ✅ Use correct hash
        user = User.query.get(email)
        if user:
            user.password = new_password
            db.session.commit()
            flash("Password reset successful. Please login.")
            return redirect(url_for('login'))
        else:
            flash("Email not found. Please register first.")
            return redirect(url_for('register'))
    return render_template('reset_password.html', email=email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.get(email)

        if user and check_password_hash(user.password, password):
            session['email'] = email
            return redirect(url_for('home1'))
        flash("Invalid credentials.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/home1')
def home1():
    if 'email' not in session:
        return redirect(url_for('login'))

    location = request.args.get('location', '').lower()
    filtered_movies = []

    if location:
        for movie in MOVIES:
            matched_theaters = [t for t in movie['theater'] if location in t.lower()]
            if matched_theaters:
                movie_copy = movie.copy()
                movie_copy['theater'] = matched_theaters
                filtered_movies.append(movie_copy)
    else:
        filtered_movies = MOVIES

    return render_template('home1.html', movies=filtered_movies, location=location)

@app.route('/booking_form')
def booking_form():
    if 'email' not in session:
        return redirect(url_for('login'))

    title = request.args.get('title')
    location = request.args.get('location', '').lower()

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    # ✅ FIX: Updated to match new structure
    filtered_theaters = [
        t for t in movie['theaters']
        if location in t['name'].lower()
    ]

    return render_template('booking_form.html',
                           movie=movie,
                           theaters=filtered_theaters,
                           selected_location=location)

@app.route('/select_seats')
def select_seats():
    if 'email' not in session:
        return redirect(url_for('login'))

    title = request.args.get('title')
    theater_name = request.args.get('theater')
    time = request.args.get('time')

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    theater = next((t for t in movie['theaters'] if t['name'] == theater_name), None)
    if not theater:
        flash("Theater not found.")
        return redirect(url_for('home1'))

    occupied_bookings = Booking.query.filter_by(
        movie=title, theater=theater_name, time=time
    ).all()

    occupied_seats = []
    for b in occupied_bookings:
        occupied_seats += b.seats.split(',')

    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time,
        selected_price=theater['price'],   # <-- IMPORTANT!
        occupied_seats=occupied_seats
    )

@app.route('/confirm_ticket', methods=['POST'])
def confirm_ticket():
    movie_title = request.form['movie']
    selected_time = request.form['time']
    theater = request.form['theater']
    seat_price = int(request.form['price'])
    seats_str = request.form['seats']

    selected_seats = seats_str.split(",") if seats_str else []
    seat_count = len(selected_seats)
    total_price = seat_count * seat_price

    # Find movie poster
    movie = next((m for m in MOVIES if m['title'] == movie_title), None)
    poster = movie['poster_filename'] if movie else "default_poster.jpg"

    return render_template(
        'confirm_payment.html',
        movie=movie_title,
        theater=theater,
        time=selected_time,
        seats=selected_seats,
        seat_count=seat_count,
        total_price=total_price,
        poster=poster,
        seat_price=seat_price
    )


@app.route('/view_ticket/<booking_id>')
def view_ticket(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        return "Ticket not found.", 404
    return render_template('view_ticket.html', booking=booking)
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))  # ✅ Must return redirect

    user = get_current_user()

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        if new_name:
            user.name = new_name
        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()
        flash("Profile updated successfully.")
        return redirect(url_for('profile'))  # ✅ After POST, redirect back

    return render_template('profile.html', user=user)  # ✅ Final return for GET

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'email' not in session:
        return redirect(url_for('login'))

    movie = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    total_price = request.form['total_price']
    seats = request.form.getlist('seats')

    booking_id = str(uuid.uuid4())

    new_booking = Booking(
        booking_id=booking_id,
        user_email=session['email'],
        movie=movie,
        theater=theater,
        price=str(total_price),
        time=time,
        seats=",".join(seats)
    )
    db.session.add(new_booking)
    db.session.commit()

    return render_template(
        'ticket_confirmation.html',
        booking=new_booking  # ✅ This passes the full booking object
    )


@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    if 'email' not in session:
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    seat_price = int(request.form['seat_price'])
    seats = request.form.getlist('seats')

    if not seats:
        flash("No seats selected.")
        return redirect(url_for('home1'))

    # Check if any of the seats were already booked
    existing_bookings = Booking.query.filter_by(
        movie=movie_title, theater=theater, time=time
    ).all()
    occupied_seats = []
    for b in existing_bookings:
        occupied_seats += b.seats.split(',')

    for seat in seats:
        if seat in occupied_seats:
            flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
            return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time))

    # All good: Save booking
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)

    booking = Booking(
        booking_id=booking_id,
        user_email=session['email'],
        movie=movie_title,
        theater=theater,
        time=time,
        price=total_price,
        seats=",".join(seats)
    )
    db.session.add(booking)
    db.session.commit()

    # Generate PDF
    buffer = generate_ticket_pdf(booking)

    # Email PDF
    email_ticket_pdf(session['email'], buffer, booking)

    # Show confirmation
    return render_template(
        'ticket_confirmation.html',
        booking=booking
    )
def generate_ticket_pdf(booking):
    movie = next((m for m in MOVIES if m['title'] == booking.movie), None)
    poster_path = os.path.join("static", movie['poster_filename']) if movie and movie.get('poster_filename') else None

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    p.setFillColor(HexColor("#0d253f"))
    p.rect(0, 0, A4[0], A4[1], fill=1)

    p.setFillColor(HexColor("#01b4e4"))
    p.rect(0, 770, A4[0], 50, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(A4[0]/2, 785, "🎟 Movie Magic - Your Ticket")

    if poster_path and os.path.exists(poster_path):
        p.drawImage(poster_path, 50, 570, width=120, height=170)

    y = 700
    p.setFont("Helvetica", 14)
    details = [
        f"Booking ID: {booking.booking_id}",
        f"Movie: {booking.movie}",
        f"Theater: {booking.theater}",
        f"Time: {booking.time}",
        f"Seats: {booking.seats}",
        f"Total Price: ₹{booking.price}"
    ]
    for line in details:
        p.drawString(200, y, line)
        y -= 30

    p.setStrokeColor(HexColor("#01b4e4"))
    p.line(50, 550, A4[0]-50, 550)

    qr_url = url_for('view_ticket', booking_id=booking.booking_id, _external=True)
    qr_img = qrcode.make(qr_url)
    qr_buf = BytesIO()
    qr_img.save(qr_buf)
    qr_buf.seek(0)
    p.drawImage(ImageReader(qr_buf), 50, 370, width=150, height=150)

    p.setFont("Helvetica-Oblique", 12)
    p.drawString(220, 470, "Scan to view ticket online.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking not found.")
        return redirect(url_for('dashboard'))

    # Lookup movie in the MOVIES list
    movie = next((m for m in MOVIES if m['title'] == booking.movie), None)
    poster_path = os.path.join("static", movie['poster_filename']) if movie and movie.get('poster_filename') else None

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # === Background color ===
    p.setFillColor(HexColor("#0d253f"))
    p.rect(0, 0, A4[0], A4[1], fill=1)

    # === Heading bar ===
    p.setFillColor(HexColor("#01b4e4"))
    p.rect(0, 770, A4[0], 50, fill=1)

    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(A4[0] / 2, 785, "🎟 Movie Magic - Your Ticket")

    # === Poster ===
    if poster_path and os.path.exists(poster_path):
        try:
            p.drawImage(poster_path, 50, 570, width=120, height=170)
        except Exception as e:
            print("Error loading image:", e)

    # === Details ===
    p.setFont("Helvetica", 14)
    p.setFillColor(white)
    y = 700

    details = [
        f"Booking ID: {booking.booking_id}",
        f"Movie: {booking.movie}",
        f"Theater: {booking.theater}",
        f"Time: {booking.time}",
        f"Seats: {booking.seats}",
        f"Price: ₹{booking.price}"
    ]

    for line in details:
        p.drawString(200, y, line)
        y -= 30

    # === Divider line ===
    p.setStrokeColor(HexColor("#01b4e4"))
    p.setLineWidth(1)
    p.line(50, 550, A4[0]-50, 550)

    # === QR Code ===
    qr_url = f"http://localhost:5000/view_ticket/{booking.booking_id}"
    qr_img = qrcode.make(qr_url)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)

    p.drawImage(ImageReader(qr_buffer), 50, 370, width=150, height=150)

    # === Note ===
    p.setFont("Helvetica-Oblique", 12)
    p.drawString(220, 470, "Scan this QR code to view your ticket online.")

    # === Footer ===
    p.setFont("Helvetica", 10)
    p.setFillColor(HexColor("#bbbbbb"))
    p.drawCentredString(A4[0]/2, 50, "Thank you for booking with Movie Magic.")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name='ticket.pdf',
        mimetype='application/pdf'
    )





@app.route('/ticket_qr/<booking_id>')
def ticket_qr(booking_id):
    booking_url = f"http://localhost:5000/ticket/{booking_id}"  # or full URL to your ticket
    qr = qrcode.make(booking_url)
    qr_path = f"static/qr_{booking_id}.png"
    qr.save(qr_path)
    return send_file(qr_path, mimetype='image/png')

@app.route('/payment_qr')
def payment_qr():
    amount = request.args.get("amount", "0")
    upi_string = f"upi://pay?pa=merchant@upi&pn=MovieMagic&am={amount}&cu=INR"

    qr_img = qrcode.make(upi_string)
    qr_buf = BytesIO()
    qr_img.save(qr_buf)
    qr_buf.seek(0)

    return send_file(qr_buf, mimetype='image/png')





@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = get_current_user()
    bookings = get_user_bookings(user.email)
    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

# ---------------------- Main ----------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
