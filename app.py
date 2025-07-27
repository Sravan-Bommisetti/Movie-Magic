from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
import qrcode
import os
import threading
import webbrowser
import time
import uuid
from io import BytesIO
import smtplib
from email.message import EmailMessage
import traceback # Added for more detailed error logging

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_for_security' # IMPORTANT: Change this to a strong, unique key!

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'movie_magic.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(50), unique=True, nullable=False)
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), nullable=False)
    movie = db.Column(db.String(100), nullable=False)
    theater = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    seats = db.Column(db.String(200), nullable=False) # Increased length to support more seats
    price = db.Column(db.String(10), nullable=False)

# --- Movie Data ---
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

# IMPORTANT: Replace with your actual Gmail and App Password
# For security, consider using environment variables for these
EMAIL_ADDRESS = 'your_email@gmail.com' # Replace with your Gmail address
EMAIL_PASSWORD = 'your_gmail_app_password' # Replace with your Gmail App Password

# --- Helper Functions ---
def get_current_user():
    if 'email' in session:
        return User.query.filter_by(email=session['email']).first()
    return None

def get_user_bookings(email):
    return Booking.query.filter_by(user_email=email).all()

def email_ticket_pdf(to_email, pdf_buffer, booking):
    try:
        msg = EmailMessage()
        msg['Subject'] = '🎟️ Your Movie Magic Ticket!'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg.set_content(f"""
Hello there,

Your movie ticket details:

🎬 Movie: {booking.movie}
🎭 Theater: {booking.theater}
🕒 Time: {booking.time}
💺 Seats: {booking.seats}
💸 Total Price: ₹{booking.price}
🆔 Booking ID: {booking.booking_id}

Please find your ticket attached. Enjoy the show!

Best regards,
Movie Magic Team
""")
        
        pdf_buffer.seek(0)
        msg.add_attachment(pdf_buffer.read(), maintype='application', subtype='pdf', filename=f'ticket_{booking.booking_id}.pdf')
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"Ticket email sent successfully to {to_email} for booking {booking.booking_id}")
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")
        traceback.print_exc() # Log full traceback for more detailed debugging

def generate_ticket_pdf(booking):
    movie = next((m for m in MOVIES if m['title'] == booking.movie), None)
    
    # Ensure poster_path is correctly constructed and checked
    poster_path = None
    if movie and movie.get('poster_filename'):
        poster_path = os.path.join(basedir, "static", movie['poster_filename']) # Use basedir for absolute path

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # Background Color (Dark Blue)
    p.setFillColor(HexColor("#0d253f"))
    p.rect(0, 0, A4[0], A4[1], fill=1)

    # Header Bar (Light Blue)
    p.setFillColor(HexColor("#01b4e4"))
    p.rect(0, 770, A4[0], 50, fill=1)

    # Header Text
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(A4[0] / 2, 785, "🎟 Movie Magic - Your Ticket")

    # Movie Poster
    if poster_path and os.path.exists(poster_path):
        try:
            p.drawImage(poster_path, 50, 570, width=120, height=170)
            print(f"Successfully loaded and drew image: {poster_path}")
        except Exception as e:
            print(f"Error loading or drawing image {poster_path}: {e}")
            traceback.print_exc() # Log traceback for image errors
    else:
        print(f"Poster not found or path invalid for {booking.movie}: {poster_path}")

    # Booking Details
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

    # Separator Line
    p.setStrokeColor(HexColor("#01b4e4"))
    p.setLineWidth(1)
    p.line(50, 550, A4[0]-50, 550)

    # QR code for viewing ticket online
    qr_url = url_for('view_ticket', booking_id=booking.booking_id, _external=True)
    qr_img = qrcode.make(qr_url)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    p.drawImage(ImageReader(qr_buffer), 50, 370, width=150, height=150)

    p.setFont("Helvetica-Oblique", 12)
    p.drawString(220, 470, "Scan this QR code to view your ticket online.")

    # Footer
    p.setFont("Helvetica", 10)
    p.setFillColor(HexColor("#bbbbbb"))
    p.drawCentredString(A4[0]/2, 50, "Thank you for booking with Movie Magic.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- Routes ---
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
        email = request.form['email'].strip()
        name = request.form['name'].strip()
        password = generate_password_hash(request.form['password'])

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("That email is already registered. Please login or reset your password.")
            return redirect(url_for('login', email=email))
        else:
            new_user = User(email=email, name=name, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! You can now login.")
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email', '').strip()
    if request.method == 'POST':
        email = request.form['email'].strip()
        new_password = generate_password_hash(request.form['password'])
        user = User.query.filter_by(email=email).first()
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
        email = request.form['email'].strip()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['email'] = email
            flash(f"Welcome back, {user.name or user.email}!")
            return redirect(url_for('home1'))
        flash("Invalid email or password. Please try again.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('index'))

@app.route('/home1')
def home1():
    if 'email' not in session:
        flash("Please log in to view movies.")
        return redirect(url_for('login'))

    location_query = request.args.get('location', '').strip().lower()
    filtered_movies = []

    if location_query:
        for movie in MOVIES:
            if any(location_query in t['name'].lower() for t in movie['theaters']):
                filtered_movies.append(movie)
        if not filtered_movies:
            flash(f"No movies found for '{location_query}'. Showing all movies instead.")
            filtered_movies = MOVIES
    else:
        filtered_movies = MOVIES

    return render_template('home1.html', movies=filtered_movies, location=location_query)

@app.route('/booking_form')
def booking_form():
    if 'email' not in session:
        flash("Please log in to book tickets.")
        return redirect(url_for('login'))

    title = request.args.get('title')
    location = request.args.get('location', '').strip().lower()

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    filtered_theaters = [
        t for t in movie['theaters']
        if location in t['name'].lower() or not location
    ]

    return render_template(
        'booking_form.html',
        movie=movie,
        theaters=filtered_theaters,
        selected_location=location)

@app.route('/select_seats')
def select_seats():
    if 'email' not in session:
        flash("Please log in to select seats.")
        return redirect(url_for('login'))

    title = request.args.get('title')
    theater_name = request.args.get('theater')
    time_slot = request.args.get('time')

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    theater = next((t for t in movie['theaters'] if t['name'] == theater_name), None)
    if not theater:
        flash("Theater not found for this movie.")
        return redirect(url_for('home1'))

    # Retrieve all existing bookings for this movie, theater, and time
    occupied_bookings = Booking.query.filter_by(
        movie=title, theater=theater_name, time=time_slot
    ).all()

    occupied_seats = []
    for b in occupied_bookings:
        if b.seats:
            occupied_seats.extend(b.seats.split(',')) # Split the comma-separated string

    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time_slot,
        selected_price=theater['price'],
        occupied_seats=occupied_seats # Pass the list of occupied seats to the template
    )

@app.route('/confirm_ticket', methods=['POST'])
def confirm_ticket():
    if 'email' not in session:
        flash("Please log in to confirm your ticket.")
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    selected_time = request.form['time']
    theater = request.form['theater']
    seat_price = int(request.form['price'])
    
    # FIX: Changed 'seats_selected' to 'seats' to match the 'name' attribute in select_seats.html
    seats_str = request.form.get('seats', '') 

    selected_seats = [seat.strip() for seat in seats_str.split(',') if seat.strip()]
    
    if not selected_seats:
        flash("No seats selected. Please select at least one seat.")
        # Redirect back to select_seats with relevant info to repopulate the form
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=selected_time))

    seat_count = len(selected_seats)
    total_price = seat_count * seat_price

    movie_data = next((m for m in MOVIES if m['title'] == movie_title), None)
    poster = movie_data['poster_filename'] if movie_data else "default_poster.jpg"

    return render_template(
        'confirm_payment.html',
        movie=movie_title,
        theater=theater,
        time=selected_time,
        seats=selected_seats, # Pass as list to the template for display
        seat_count=seat_count,
        total_price=total_price,
        poster=poster,
        seat_price=seat_price
    )
# ... (rest of your app.py code) ...

@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    print("\n--- finalize_booking START ---") # Added print
    if 'email' not in session:
        flash("Please log in to complete your booking.")
        print("DEBUG: Redirecting to login (user not in session)") # Added print
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time_slot = request.form['time']
    seat_price = int(request.form['seat_price'])
    seats_raw = request.form.get('seats', '')
    selected_seats = [s.strip() for s in seats_raw.split(',') if s.strip()]
    print(f"DEBUG: Received seats_raw: '{seats_raw}', processed selected_seats: {selected_seats}") # Added print

    if not selected_seats:
        flash("No seats selected. Please go back and select seats.")
        print("DEBUG: Redirecting (no seats selected)") # Added print
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot))

    # Re-check for occupied seats just before finalization to prevent double-booking
    existing_bookings = Booking.query.filter_by(
        movie=movie_title, theater=theater, time=time_slot
    ).all()
    
    occupied_seats_at_finalization = []
    for b in existing_bookings:
        if b.seats:
            occupied_seats_at_finalization.extend(b.seats.split(','))
    print(f"DEBUG: Occupied seats from DB: {occupied_seats_at_finalization}") # Added print

    for seat in selected_seats:
        if seat in occupied_seats_at_finalization:
            flash(f"Oops! Seat {seat} was just booked by someone else. Please select different seats.")
            print(f"DEBUG: Redirecting (seat {seat} was just booked by someone else)") # Added print
            return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot))

    # If we reach here, seats are available, proceed with booking
    booking_id = str(uuid.uuid4())
    total_price = str(len(selected_seats) * seat_price)

    new_booking = Booking(
        booking_id=booking_id,
        user_email=session['email'],
        movie=movie_title,
        theater=theater,
        time=time_slot,
        price=total_price,
        seats=",".join(selected_seats) # Store as comma-separated string
    )
    print(f"DEBUG: New booking object created: {new_booking.booking_id}") # Added print
    try:
        db.session.add(new_booking)
        db.session.commit()
        print("DEBUG: Booking successfully added to database.") # Added print
    except Exception as e:
        db.session.rollback() # Important: rollback on error
        print(f"ERROR: Database commit failed: {e}") # Added print
        traceback.print_exc() # Print full traceback
        flash("An unexpected error occurred during booking. Please try again.")
        return redirect(url_for('home1'))


    # Generate and send PDF in a separate thread
    print("DEBUG: Starting PDF generation and email thread...") # Added print
    try:
        pdf_buffer = generate_ticket_pdf(new_booking)
        threading.Thread(target=email_ticket_pdf, args=(session['email'], pdf_buffer, new_booking)).start()
        print("DEBUG: PDF generation and email thread started.") # Added print
    except Exception as e:
        print(f"ERROR: Problem with PDF generation or email thread start: {e}")
        traceback.print_exc()
        flash("Booking confirmed, but there was an issue generating/sending your ticket PDF. Please check your dashboard.")
        # Do NOT return here, still want to show confirmation page if booking saved

    flash("Your booking is confirmed! A ticket has been sent to your email.")
    print("DEBUG: Attempting to render ticket_confirmation.html") # Added print
    return render_template(
        'ticket_confirmation.html',
        booking=new_booking
    )
@app.route('/view_ticket/<booking_id>')
def view_ticket(booking_id):
    if 'email' not in session:
        flash("Please log in to view tickets.")
        return redirect(url_for('login'))

    booking = Booking.query.filter_by(booking_id=booking_id, user_email=session['email']).first()
    if not booking:
        flash("Ticket not found or you don't have permission to view it.")
        return redirect(url_for('dashboard'))

    return render_template('view_ticket.html', booking=booking)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        flash("Please log in to view your profile.")
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User not found. Please log in again.")
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()
        new_password = request.form.get('password', '').strip()

        if new_name:
            user.name = new_name
        if new_password:
            user.password = generate_password_hash(new_password)
            flash("Password updated successfully.")
        
        db.session.commit()
        flash("Profile updated successfully.")
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        flash("Please log in to view your dashboard.")
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User not found. Please log in again.")
        session.clear()
        return redirect(url_for('login'))

    bookings = get_user_bookings(user.email)
    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    if 'email' not in session:
        flash("Please log in to download tickets.")
        return redirect(url_for('login'))

    booking = Booking.query.filter_by(booking_id=booking_id, user_email=session['email']).first()
    if not booking:
        flash("Booking not found or you don't have permission to download it.")
        return redirect(url_for('dashboard'))

    buffer = generate_ticket_pdf(booking)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'movie_ticket_{booking.booking_id}.pdf',
        mimetype='application/pdf'
    )

@app.route('/payment_qr')
def payment_qr():
    amount = request.args.get("amount", "0")
    # Basic UPI string - for a real app, integrate with a payment gateway
    upi_string = f"upi://pay?pa=merchant@upi&pn=MovieMagic&am={amount}&cu=INR" 

    qr_img = qrcode.make(upi_string)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    return send_file(qr_buf, mimetype='image/png')

# --- App Initialization ---
def open_browser():
    time.sleep(1) # Give the server a moment to start
    webbrowser.open_new("http://127.0.0.1:5000/")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Ensure static folder exists for posters
    if not os.path.exists(os.path.join(basedir, 'static')):
        os.makedirs(os.path.join(basedir, 'static'))
        print(f"Created static directory at: {os.path.join(basedir, 'static')}")

    threading.Thread(target=open_browser).start()
    
    app.run(debug=True) # Run in debug mode for development
