from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import boto3, qrcode, os, threading, webbrowser
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key' # In a real application, use a strong, randomly generated key

# AWS Setup
# Ensure your AWS credentials are configured (e.g., via environment variables, ~/.aws/credentials, or IAM roles)
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

USER_TABLE = 'MovieMagicUsers' # Make sure this table exists in DynamoDB with 'email' as primary key
BOOKING_TABLE = 'MovieMagicBookings' # Make sure this table exists with 'booking_id' as primary key
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:YourMovieMagicTopic'  # <<< REPLACE with your actual SNS topic ARN

table_users = dynamodb.Table(USER_TABLE)
table_bookings = dynamodb.Table(BOOKING_TABLE)


# Helper funcs
def get_current_user():
    if 'email' in session:
        # Use table_users to get item by primary key 'email'
        resp = table_users.get_item(Key={'email': session['email']})
        return resp.get('Item')
    return None

def email_ticket_via_sns(to_email, pdf_buffer, booking):
    pdf_buffer.seek(0)
    # The payload needs to be a string when publishing to SNS
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
        sns.publish(TopicArn=SNS_TOPIC_ARN, Message=str(payload), Subject="Your Movie Magic Ticket")
        print(f"SNS email sent to {to_email} for booking {booking['booking_id']}")
    except Exception as e:
        print(f"Error sending SNS email: {e}")

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
                    'TOMORROW': ['2:00 PM', '6:00 PM'],
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
                    'TOMORROW': ['2:00 PM', '6:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM']
                }
            },
            {
                'name': 'M G B, NELLORE',
                'price': 300,
                'timings_by_day': {
                    'TODAY': ['6:00 AM', '8:00 AM', '12:00 PM', '6:00 PM'],
                    'TOMORROW': ['7:00 AM', '6:00 PM', '10:00 PM'],
                    'DAY OF TOMORROW': ['1:00 PM', '6:00 PM', '10:00 PM']
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
        response = table_users.get_item(Key={'email': email})
        existing_user = response.get('Item')

        if existing_user:
            flash("Email already registered. Please reset your password.")
            return redirect(url_for('reset_password', email=email))
        else:
            # Add new user to DynamoDB
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

        # Check if user exists in DynamoDB
        response = table_users.get_item(Key={'email': email})
        user = response.get('Item')

        if user:
            # Update password in DynamoDB
            table_users.update_item(
                Key={'email': email},
                UpdateExpression='SET #P = :val',
                ExpressionAttributeNames={'#P': 'password'},
                ExpressionAttributeValues={':val': new_password}
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
        response = table_users.get_item(Key={'email': email})
        user = response.get('Item')

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
            # Correctly filter theaters within each movie
            matched_theaters = [t for t in movie['theaters'] if location in t['name'].lower()]
            if matched_theaters:
                movie_copy = movie.copy()
                movie_copy['theaters'] = matched_theaters # Assign filtered theaters
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

    # Filter theaters based on the provided location
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

    # Query DynamoDB for occupied seats for this movie, theater, and time
    response = table_bookings.query(
        IndexName='MovieTheaterTimeIndex', # You might need to create this index in DynamoDB
        KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(title) & boto3.dynamodb.conditions.Key('theater').eq(theater_name),
        FilterExpression=boto3.dynamodb.conditions.Attr('time').eq(time)
    )
    # If the above query is too complex or slow, consider structuring your booking_id
    # to include movie-theater-time as part of the primary key or using a GSI with all three attributes.
    # For simplicity, if you only query by booking_id, you'd fetch all bookings and filter in Python.

    occupied_bookings = response.get('Items', [])
    occupied_seats = []
    for b in occupied_bookings:
        # Ensure 'seats' attribute exists and is a string before splitting
        if 'seats' in b and isinstance(b['seats'], str):
            occupied_seats.extend(b['seats'].split(','))
    
    # Remove duplicates from occupied_seats
    occupied_seats = list(set(occupied_seats))

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
    response = table_bookings.get_item(Key={'booking_id': booking_id})
    booking = response.get('Item')
    if not booking:
        return "Ticket not found.", 404
    return render_template('view_ticket.html', booking=booking)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = get_current_user() # This now returns a dict from DynamoDB
    if not user:
        flash("User not found.")
        return redirect(url_for('login')) # Should not happen if session['email'] is valid

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        update_expression = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        if new_name and new_name != user.get('name'): # Only update if changed
            update_expression.append('#N = :newName')
            expression_attribute_names['#N'] = 'name'
            expression_attribute_values[':newName'] = new_name
        
        if new_password: # Always update if password field is filled
            update_expression.append('#P = :newPassword')
            expression_attribute_names['#P'] = 'password'
            expression_attribute_values[':newPassword'] = generate_password_hash(new_password)

        if update_expression: # Only update if there are changes
            try:
                table_users.update_item(
                    Key={'email': user['email']},
                    UpdateExpression='SET ' + ', '.join(update_expression),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                flash("Profile updated successfully.")
            except Exception as e:
                flash(f"Error updating profile: {e}")
            return redirect(url_for('profile')) # Redirect after POST
        else:
            flash("No changes to update.")


    return render_template('profile.html', user=user)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'email' not in session:
        return redirect(url_for('login'))

    movie = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    total_price = request.form['total_price']
    seats = request.form.getlist('seats') # getlist for multiple selected seats

    booking_id = str(uuid.uuid4())

    # Save booking to DynamoDB
    booking_item = {
        'booking_id': booking_id,
        'user_email': session['email'],
        'movie': movie,
        'theater': theater,
        'price': total_price, # Store as string or number as per your DynamoDB table schema
        'time': time,
        'seats': ",".join(seats)
    }
    table_bookings.put_item(Item=booking_item)

    return render_template(
        'ticket_confirmation.html',
        booking=booking_item # Pass the dictionary for rendering
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

    # Check for existing bookings for these seats (race condition prevention)
    # This query needs to be efficient. For DynamoDB, this means carefully designed indexes.
    # A GSI on (movie, theater, time) would allow efficient querying of existing bookings for a show.
    # For now, we'll query by movie and theater and filter by time in Python, which is less efficient.
    
    # This query needs a Global Secondary Index (GSI) on (movie, theater) to work efficiently.
    # Alternatively, if you have a GSI on (movie, theater, time) as its partition key, that's even better.
    try:
        response = table_bookings.query(
            # Assuming you have a GSI named 'MovieTheaterTimeIndex' with Partition Key 'movie' and Sort Key 'theater'
            # and 'time' as a non-key attribute for filtering. If 'time' is part of the Sort Key, you can add it to KeyConditionExpression.
            # For simplicity, if you don't have this GSI, you might need to scan or query more broadly and filter in Python.
            IndexName='MovieTheaterTimeIndex', # Replace with your actual GSI name if you create one
            KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(movie_title) & boto3.dynamodb.conditions.Key('theater').eq(theater),
            FilterExpression=boto3.dynamodb.conditions.Attr('time').eq(time)
        )
        existing_bookings = response.get('Items', [])
    except Exception as e:
        print(f"Warning: Could not query existing bookings using GSI: {e}. Falling back to potentially less efficient methods if applicable.")
        # Fallback if GSI is not configured or fails.
        # This is a very inefficient way for large datasets and will likely hit read capacity issues.
        # It's here as a conceptual fallback; a proper DynamoDB design is crucial.
        # A full scan is NOT recommended for production.
        response = table_bookings.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('movie').eq(movie_title) & 
                             boto3.dynamodb.conditions.Attr('theater').eq(theater) & 
                             boto3.dynamodb.conditions.Attr('time').eq(time)
        )
        existing_bookings = response.get('Items', [])
        
    occupied_seats = []
    for b in existing_bookings:
        if 'seats' in b and isinstance(b['seats'], str):
            occupied_seats.extend(b['seats'].split(','))
    occupied_seats = list(set(occupied_seats)) # Ensure unique occupied seats

    for seat in seats:
        if seat in occupied_seats:
            flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
            return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time))

    # All good: Save booking
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)

    booking_item = {
        'booking_id': booking_id,
        'user_email': session['email'],
        'movie': movie_title,
        'theater': theater,
        'time': time,
        'price': total_price,
        'seats': ",".join(seats)
    }
    table_bookings.put_item(Item=booking_item)

    # Generate PDF
    buffer = generate_ticket_pdf(booking_item)

    # Email PDF (using SNS)
    email_ticket_via_sns(session['email'], buffer, booking_item)

    # Show confirmation
    return render_template(
        'ticket_confirmation.html',
        booking=booking_item
    )

def generate_ticket_pdf(booking):
    movie = next((m for m in MOVIES if m['title'] == booking['movie']), None)
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
    response = table_bookings.get_item(Key={'booking_id': booking_id})
    booking = response.get('Item')
    if not booking:
        flash("Booking not found.")
        return redirect(url_for('dashboard'))

    # Lookup movie in the MOVIES list
    movie = next((m for m in MOVIES if m['title'] == booking['movie']), None)
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
    qr_url = f"http://localhost:5000/view_ticket/{booking['booking_id']}"
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
    booking_url = f"http://localhost:5000/view_ticket/{booking_id}"
    qr = qrcode.make(booking_url)
    # It's better to serve the QR code directly from buffer instead of saving to disk
    qr_buf = BytesIO()
    qr.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    return send_file(qr_buf, mimetype='image/png')


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

    user = get_current_user() # User is a dictionary now
    if not user:
        flash("User not found in session.")
        return redirect(url_for('login'))

    # Retrieve user's bookings from DynamoDB using a Global Secondary Index (GSI)
    # on user_email. You will need to create a GSI on 'MovieMagicBookings' table
    # with 'user_email' as the Partition Key.
    try:
        response = table_bookings.query(
            IndexName='UserEmailIndex', # <<< REPLACE with your actual GSI name (e.g., 'UserEmailGSI')
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_email').eq(user['email'])
        )
        bookings = response.get('Items', [])
    except Exception as e:
        print(f"Error querying bookings by user email: {e}")
        flash("Could not retrieve your bookings. Please try again later.")
        bookings = [] # Default to empty list on error

    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

def open_browser():
    webbrowser.open_new("http://localhost:5000/")

if __name__ == '__main__':
    # Ensure you have your AWS credentials configured
    # For example, by setting AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
    # or by having a ~/.aws/credentials file.
    # Also, ensure the DynamoDB tables 'MovieMagicUsers' and 'MovieMagicBookings' exist
    # and have the correct primary keys and GSIs (if used).
    
    # Required DynamoDB Tables:
    # 1. MovieMagicUsers: Primary Key 'email' (String)
    # 2. MovieMagicBookings: Primary Key 'booking_id' (String)
    #    - Optional GSI for efficient querying:
    #      - 'UserEmailIndex': Partition Key 'user_email' (String)
    #      - 'MovieTheaterTimeIndex': Partition Key 'movie' (String), Sort Key 'theater' (String)
    #         - And filter on 'time' if not part of sort key or GSI key.

    # Small delay before opening browser to allow server to start
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
