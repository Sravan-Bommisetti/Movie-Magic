from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import boto3, qrcode, os, threading, webbrowser
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json # Import json for SNS message
import time # Import time for adding timestamp to bookings

app = Flask(__name__)
app.secret_key = 'your_secret_key' # IMPORTANT: Change this to a strong, random key in production

# AWS Setup
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

USER_TABLE = 'MovieMagicUsers'
BOOKING_TABLE = 'MovieMagicBookings'
# IMPORTANT: Replace with your actual SNS Topic ARN
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:YourMovieMagicSNSTopic'

table_users = dynamodb.Table(USER_TABLE)
table_bookings = dynamodb.Table(BOOKING_TABLE)


# Helper funcs
def get_current_user():
    if 'email' in session:
        # Use table_users (DynamoDB) to get user
        resp = table_users.get_item(Key={'email': session['email']})
        return resp.get('Item')
    return None

def get_user_bookings(email):
    # Use table_bookings (DynamoDB) to query bookings for a user
    response = table_bookings.query(
        IndexName='UserEmailIndex', # Assuming you have a GSI on user_email for querying
        KeyConditionExpression=boto3.dynamodb.conditions.Key('user_email').eq(email)
    )
    return response.get('Items', [])

def email_ticket_via_sns(to_email, pdf_buffer, booking):
    pdf_buffer.seek(0)
    payload = {
        "to": to_email,
        "booking_id": booking['booking_id'],
        "movie": booking['movie'],
        "theater": booking['theater'],
        "time": booking['time'],
        "seats": booking['seats'],
        "pdf_hex": pdf_buffer.getvalue().hex()
    }
    try:
        # Publish the message to SNS
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(payload), # Convert payload to JSON string
            Subject='🎟️ Your Movie Magic Ticket!'
        )
        print(f"SNS email triggered for {to_email} and booking {booking['booking_id']}")
    except Exception as e:
        print(f"Error publishing to SNS: {e}")

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
        password = generate_password_hash(request.form['password'])

        # Check if user already exists in DynamoDB
        resp = table_users.get_item(Key={'email': email})
        existing_user = resp.get('Item')

        if existing_user:
            flash("Email already registered. Please reset your password.")
            return redirect(url_for('reset_password', email=email))
        else:
            # Store new user in DynamoDB
            table_users.put_item(
                Item={
                    'email': email,
                    'name': name,
                    'password': password
                }
            )
            flash("Registration successful! You can now login.")
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email') or ''
    if request.method == 'POST':
        email = request.form['email']
        new_password = generate_password_hash(request.form['password'])

        # Get user from DynamoDB
        resp = table_users.get_item(Key={'email': email})
        user = resp.get('Item')

        if user:
            # Update user's password in DynamoDB
            table_users.update_item(
                Key={'email': email},
                UpdateExpression='SET #pw = :new_password',
                ExpressionAttributeNames={'#pw': 'password'},
                ExpressionAttributeValues={':new_password': new_password}
            )
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

        # Get user from DynamoDB
        resp = table_users.get_item(Key={'email': email})
        user = resp.get('Item')

        if user and check_password_hash(user['password'], password):
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
            # Filter theaters within each movie based on location
            matched_theaters = [t for t in movie['theaters'] if location in t['name'].lower()]
            if matched_theaters:
                movie_copy = movie.copy()
                movie_copy['theaters'] = matched_theaters # Keep the original 'theaters' key for consistency
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

    # Filter theaters based on location if provided
    filtered_theaters = [
        t for t in movie['theaters']
        if location in t['name'].lower()
    ] if location else movie['theaters'] # If no location, show all theaters

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

    # Query DynamoDB for occupied seats
    # This query needs to be efficient. Consider a GSI if querying by movie, theater, time is frequent.
    # For now, we'll scan (inefficient for large tables) or filter after a broader query.
    # A better approach would be to have a composite key for bookings like movie#theater#time
    # Or a GSI on these attributes.
    occupied_seats = []
    response = table_bookings.query(
        IndexName='MovieTheaterTimeIndex', # Assuming you have a GSI on movie, theater, time
        KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(title) &
                               boto3.dynamodb.conditions.Key('theater').eq(theater_name) &
                               boto3.dynamodb.conditions.Key('time').eq(time)
    )
    for b in response.get('Items', []):
        occupied_seats.extend(b['seats'].split(','))


    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time,
        selected_price=theater['price'],
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
    # Get booking from DynamoDB
    resp = table_bookings.get_item(Key={'booking_id': booking_id})
    booking = resp.get('Item')

    if not booking:
        return "Ticket not found.", 404
    return render_template('view_ticket.html', booking=booking)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = get_current_user() # This now correctly fetches from DynamoDB

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        update_expression = 'SET '
        expression_attribute_values = {}
        expression_attribute_names = {}

        if new_name:
            update_expression += '#n = :new_name, '
            expression_attribute_names['#n'] = 'name'
            expression_attribute_values[':new_name'] = new_name
            user['name'] = new_name # Update in memory for immediate display

        if new_password:
            hashed_password = generate_password_hash(new_password)
            update_expression += '#pw = :new_password, '
            expression_attribute_names['#pw'] = 'password'
            expression_attribute_values[':new_password'] = hashed_password
            user['password'] = hashed_password # Update in memory

        # Remove trailing comma and space
        update_expression = update_expression.rstrip(', ')

        if update_expression != 'SET': # Only update if there are changes
            table_users.update_item(
                Key={'email': user['email']},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            flash("Profile updated successfully.")
        else:
            flash("No changes were made to the profile.")

        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'email' not in session:
        return redirect(url_for('login'))

    movie = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    total_price = request.form['total_price']
    seats_str = request.form['seats'] # Get the comma-separated string
    seats = seats_str.split(',') if seats_str else [] # Convert to list

    booking_id = str(uuid.uuid4())
    user_email = session['email']
    timestamp = str(int(time.time())) # Add a timestamp for better uniqueness and sorting if needed

    # Prepare booking item for DynamoDB
    booking_item = {
        'booking_id': booking_id,
        'user_email': user_email, # This will be the GSI partition key
        'movie': movie,
        'theater': theater,
        'price': total_price,
        'time': time,
        'seats': ",".join(seats), # Store as comma-separated string
        'timestamp': timestamp # Add timestamp to the booking
    }

    try:
        table_bookings.put_item(Item=booking_item)
        flash("Payment processed and booking created successfully!")
    except Exception as e:
        flash(f"Error saving booking: {e}")
        return redirect(url_for('confirm_ticket')) # Or an appropriate error page

    # Now, generate PDF and email (or trigger SNS for email)
    pdf_buffer = generate_ticket_pdf(booking_item)
    # Use the SNS email function
    threading.Thread(target=email_ticket_via_sns, args=(user_email, pdf_buffer, booking_item)).start()


    return render_template(
        'ticket_confirmation.html',
        booking=booking_item
    )


@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    # This route seems to be a duplicate or in conflict with process_payment.
    # It's better to consolidate booking finalization into one place (e.g., process_payment)
    # For now, I'm just adapting it to use DynamoDB, but consider removing one.

    if 'email' not in session:
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    seat_price = int(request.form['seat_price'])
    seats_str = request.form['seats']
    seats = seats_str.split(',') if seats_str else []

    if not seats:
        flash("No seats selected.")
        # Need to pass movie, theater, time back to select_seats
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time))

    # Check if any of the seats were already booked using DynamoDB query
    # This needs a GSI on movie, theater, time to be efficient.
    occupied_seats = []
    response = table_bookings.query(
        IndexName='MovieTheaterTimeIndex', # Assuming you have a GSI on movie, theater, time
        KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(movie_title) &
                               boto3.dynamodb.conditions.Key('theater').eq(theater) &
                               boto3.dynamodb.conditions.Key('time').eq(time)
    )
    for b in response.get('Items', []):
        occupied_seats.extend(b['seats'].split(','))

    for seat in seats:
        if seat in occupied_seats:
            flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
            return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time))

    # All good: Save booking to DynamoDB
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)
    user_email = session['email']
    timestamp = str(int(time.time()))

    booking_item = {
        'booking_id': booking_id,
        'user_email': user_email,
        'movie': movie_title,
        'theater': theater,
        'time': time,
        'price': total_price,
        'seats': ",".join(seats),
        'timestamp': timestamp
    }

    try:
        table_bookings.put_item(Item=booking_item)
        flash("Booking confirmed!")
    except Exception as e:
        flash(f"Error finalizing booking: {e}")
        return redirect(url_for('confirm_ticket')) # Or an appropriate error page

    # Generate PDF
    buffer = generate_ticket_pdf(booking_item)

    # Email PDF via SNS (asynchronous)
    threading.Thread(target=email_ticket_via_sns, args=(user_email, buffer, booking_item)).start()

    # Show confirmation
    return render_template(
        'ticket_confirmation.html',
        booking=booking_item
    )

def generate_ticket_pdf(booking):
    movie = next((m for m in MOVIES if m['title'] == booking['movie']), None) # Use dictionary access for booking
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
        f"Booking ID: {booking['booking_id']}",
        f"Movie: {booking['movie']}",
        f"Theater: {booking['theater']}",
        f"Time: {booking['time']}",
        f"Seats: {booking['seats']}",
        f"Total Price: ₹{booking['price']}"
    ]
    for line in details:
        p.drawString(200, y, line)
        y -= 30

    p.setStrokeColor(HexColor("#01b4e4"))
    p.line(50, 550, A4[0]-50, 550)

    qr_url = url_for('view_ticket', booking_id=booking['booking_id'], _external=True)
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
    # Get booking from DynamoDB
    resp = table_bookings.get_item(Key={'booking_id': booking_id})
    booking = resp.get('Item')

    if not booking:
        flash("Booking not found.")
        return redirect(url_for('dashboard'))

    # Lookup movie in the MOVIES list
    movie = next((m for m in MOVIES if m['title'] == booking['movie']), None) # Use dictionary access
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
        f"Booking ID: {booking['booking_id']}",
        f"Movie: {booking['movie']}",
        f"Theater: {booking['theater']}",
        f"Time: {booking['time']}",
        f"Seats: {booking['seats']}",
        f"Price: ₹{booking['price']}"
    ]

    for line in details:
        p.drawString(200, y, line)
        y -= 30

    # === Divider line ===
    p.setStrokeColor(HexColor("#01b4e4"))
    p.setLineWidth(1)
    p.line(50, 550, A4[0]-50, 550)

    # === QR Code ===
    qr_url = url_for('view_ticket', booking_id=booking['booking_id'], _external=True) # Use url_for for external URL
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
        download_name=f'movie_magic_ticket_{booking_id}.pdf', # More descriptive filename
        mimetype='application/pdf'
    )


@app.route('/ticket_qr/<booking_id>')
def ticket_qr(booking_id):
    # This route is likely not needed if QR codes are embedded in the PDF
    # or if view_ticket serves the purpose.
    booking_url = url_for('view_ticket', booking_id=booking_id, _external=True)
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
    bookings = get_user_bookings(user['email']) # Pass email from the user dictionary
    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

# send_sns_email is now integrated into email_ticket_via_sns and no longer a standalone helper
# def send_sns_email(email, subject, message):
#     sns.publish(TopicArn='your-sns-topic-arn', Message=message, Subject=subject)


def open_browser():
    # Only open browser if not in debug mode for production deployment
    if not app.debug:
        webbrowser.open_new("http://localhost:5000/")

if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
