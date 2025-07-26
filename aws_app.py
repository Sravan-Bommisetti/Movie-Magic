from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import boto3
from boto3.dynamodb.conditions import Key # Import Key for DynamoDB queries
from botocore.exceptions import ClientError # Import ClientError for specific error handling
import qrcode, os, threading, webbrowser
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json # Import json for SNS message
import time # Import time for adding timestamp to bookings
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key_CHANGE_THIS_IN_PRODUCTION' # IMPORTANT: Change this to a strong, random key in production

# AWS Setup
# Ensure your AWS credentials are configured (e.g., via environment variables, ~/.aws/credentials, or IAM role)
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

USER_TABLE = 'MovieMagicUsers'
BOOKING_TABLE = 'MovieMagicBookings'
# IMPORTANT: Replace with your actual SNS Topic ARN
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:YourMovieMagicSNSTopic' # <<< REPLACE THIS!

table_users = dynamodb.Table(USER_TABLE)
table_bookings = dynamodb.Table(BOOKING_TABLE)


# Helper funcs
def get_current_user():
    if 'email' in session:
        try:
            resp = table_users.get_item(Key={'email': session['email']})
            return resp.get('Item')
        except ClientError as e:
            print(f"DynamoDB error getting user: {e.response['Error']['Message']}")
            return None
    return None

def get_user_bookings(email):
    # This query assumes you have a GSI named 'UserEmailIndex' on table_bookings
    # with 'user_email' as Partition Key.
    try:
        response = table_bookings.query(
            IndexName='UserEmailIndex',
            KeyConditionExpression=Key('user_email').eq(email)
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"DynamoDB query error for user bookings: {e.response['Error']['Message']}")
        return []

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
        'teaser_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', # Example YouTube URL
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
        'teaser_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
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
        'teaser_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
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

        try:
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
        except ClientError as e:
            print(f"DynamoDB error during registration: {e.response['Error']['Message']}")
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email') or ''
    if request.method == 'POST':
        email = request.form['email']
        new_password = generate_password_hash(request.form['password'])

        try:
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
        except ClientError as e:
            print(f"DynamoDB error during password reset: {e.response['Error']['Message']}")
            flash("An error occurred during password reset. Please try again.")
            return redirect(url_for('reset_password', email=email))
    return render_template('reset_password.html', email=email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Get user from DynamoDB
            resp = table_users.get_item(Key={'email': email})
            user = resp.get('Item')

            if user and check_password_hash(user['password'], password):
                session['email'] = email
                return redirect(url_for('home1'))
            flash("Invalid credentials.")
        except ClientError as e:
            print(f"DynamoDB error during login: {e.response['Error']['Message']}")
            flash("An error occurred during login. Please try again.")
        except Exception as e:
            print(f"Unexpected error during login: {e}")
            flash("An unexpected error occurred. Please try again.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
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
    selected_day = request.args.get('day', 'TODAY') # Default to TODAY

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    # Filter theaters based on location if provided
    filtered_theaters = [
        t for t in movie['theaters']
        if location in t['name'].lower()
    ] if location else movie['theaters'] # If no location, show all theaters

    # Get available days from the first theater (assuming consistency or iterate)
    available_days = []
    if filtered_theaters:
        first_theater_timings = filtered_theaters[0]['timings_by_day']
        available_days = list(first_theater_timings.keys())
        # Ensure selected_day is one of the available days
        if selected_day not in available_days:
            selected_day = 'TODAY' if 'TODAY' in available_days else available_days[0] if available_days else ''


    return render_template('booking_form.html',
                           movie=movie,
                           theaters=filtered_theaters,
                           selected_location=location,
                           available_days=available_days,
                           selected_day=selected_day)

@app.route('/select_seats')
def select_seats():
    if 'email' not in session:
        return redirect(url_for('login'))

    title = request.args.get('title')
    theater_name = request.args.get('theater')
    time_slot = request.args.get('time') # Renamed to time_slot to avoid conflict with imported 'time' module
    day = request.args.get('day') # New: Get selected day

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    theater = next((t for t in movie['theaters'] if t['name'] == theater_name), None)
    if not theater:
        flash("Theater not found.")
        return redirect(url_for('home1'))

    # Construct the composite key for the GSI query
    # IMPORTANT: Ensure 'theater_time_composite' is the Sort Key of 'MovieTheaterTimeIndex' GSI
    composite_key_value = f"{theater_name}#{time_slot}#{day}" # Include day in composite key

    occupied_seats = []
    try:
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex',
            KeyConditionExpression=Key('movie').eq(title) &
                                   Key('theater_time_composite').eq(composite_key_value)
        )
        for b in response.get('Items', []):
            occupied_seats.extend(b['seats'].split(','))
    except ClientError as e:
        print(f"DynamoDB query error in select_seats: {e.response['Error']['Message']}")
        flash("Error fetching occupied seats. Please try again.")
        return redirect(url_for('home1'))


    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time_slot,
        selected_price=theater['price'],
        occupied_seats=occupied_seats,
        selected_day=day # Pass day to template
    )

@app.route('/confirm_ticket', methods=['POST'])
def confirm_ticket():
    movie_title = request.form['movie']
    selected_time = request.form['time']
    theater = request.form['theater']
    seat_price = int(request.form['price'])
    seats_str = request.form['seats']
    selected_day = request.form['day'] # Get day from form

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
        seat_price=seat_price,
        selected_day=selected_day # Pass day to payment confirmation
    )


@app.route('/view_ticket/<booking_id>')
def view_ticket(booking_id):
    try:
        resp = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = resp.get('Item')

        if not booking:
            return "Ticket not found.", 404
        return render_template('view_ticket.html', booking=booking)
    except ClientError as e:
        print(f"DynamoDB error viewing ticket: {e.response['Error']['Message']}")
        return "An error occurred while fetching your ticket.", 500


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User not found.")
        session.clear() # Clear session if user somehow disappears
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        update_expression = 'SET '
        expression_attribute_values = {}
        expression_attribute_names = {}

        if new_name and new_name != user.get('name'):
            update_expression += '#n = :new_name, '
            expression_attribute_names['#n'] = 'name'
            expression_attribute_values[':new_name'] = new_name
            user['name'] = new_name # Update in memory for immediate display

        if new_password: # Only update if a new password is provided
            hashed_password = generate_password_hash(new_password)
            # Only update if the new hash is different from the stored hash (unlikely for new hash)
            # This check is more relevant if not hashing every time.
            if hashed_password != user.get('password'):
                update_expression += '#pw = :new_password, '
                expression_attribute_names['#pw'] = 'password'
                expression_attribute_values[':new_password'] = hashed_password
                user['password'] = hashed_password # Update in memory

        update_expression = update_expression.rstrip(', ') # Remove trailing comma and space

        if update_expression != 'SET': # Only update if there are changes
            try:
                table_users.update_item(
                    Key={'email': user['email']},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                flash("Profile updated successfully.")
            except ClientError as e:
                print(f"DynamoDB error updating profile: {e.response['Error']['Message']}")
                flash("An error occurred while updating your profile. Please try again.")
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
    time_slot = request.form['time'] # Renamed time to time_slot
    selected_day = request.form['selected_day'] # Get the selected day
    total_price = request.form['total_price']
    seats_str = request.form['seats']
    seats = seats_str.split(',') if seats_str else []

    if not seats:
        flash("No seats selected.")
        # Redirect back to seat selection with original parameters
        return redirect(url_for('select_seats', title=movie, theater=theater, time=time_slot, day=selected_day))

    user_email = session['email']
    booking_id = str(uuid.uuid4())
    timestamp = str(int(time.time())) # Unix timestamp

    # Construct the composite key for the GSI query for checking occupied seats
    # This must match the GSI 'MovieTheaterTimeIndex' definition
    composite_key_value = f"{theater}#{time_slot}#{selected_day}"

    # Check for concurrent bookings (double-checking to avoid conflicts)
    try:
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex',
            KeyConditionExpression=Key('movie').eq(movie) &
                                   Key('theater_time_composite').eq(composite_key_value)
        )
        occupied_seats = []
        for b in response.get('Items', []):
            occupied_seats.extend(b['seats'].split(','))

        for seat in seats:
            if seat in occupied_seats:
                flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
                return redirect(url_for('select_seats', title=movie, theater=theater, time=time_slot, day=selected_day))

        # All good: Save booking to DynamoDB
        booking_item = {
            'booking_id': booking_id,
            'user_email': user_email,
            'movie': movie,
            'theater': theater,
            'time': time_slot,
            'price': total_price,
            'seats': ",".join(seats),
            'timestamp': timestamp,
            'selected_day': selected_day, # Store the selected day
            'theater_time_composite': composite_key_value # Store the composite key
        }

        table_bookings.put_item(Item=booking_item)
        flash("Payment processed and booking created successfully!")

        # Now, generate PDF and email (or trigger SNS for email) asynchronously
        pdf_buffer = generate_ticket_pdf(booking_item)
        threading.Thread(target=email_ticket_via_sns, args=(user_email, pdf_buffer, booking_item)).start()

        return render_template(
            'ticket_confirmation.html',
            booking=booking_item
        )

    except ClientError as e:
        print(f"DynamoDB error during process_payment: {e.response['Error']['Message']}")
        flash("An error occurred during payment processing. Please try again.")
        return redirect(url_for('confirm_ticket', movie=movie, theater=theater, time=time_slot, seats=seats_str, price=request.form['seat_price'], day=selected_day))
    except Exception as e:
        print(f"Unexpected error in process_payment: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('confirm_ticket', movie=movie, theater=theater, time=time_slot, seats=seats_str, price=request.form['seat_price'], day=selected_day))


# Note: The 'finalize_booking' route below is largely redundant if 'process_payment' handles everything.
# I'm keeping it updated with DynamoDB logic for completeness, but consider consolidating.
@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    if 'email' not in session:
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time_slot = request.form['time'] # Renamed to time_slot
    seat_price = int(request.form['seat_price'])
    seats_str = request.form['seats']
    seats = seats_str.split(',') if seats_str else []
    selected_day = request.form['selected_day'] # Get the selected day

    if not seats:
        flash("No seats selected.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))

    user_email = session['email']
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)
    timestamp = str(int(time.time())) # Unix timestamp

    # Construct the composite key for the GSI query
    composite_key_value = f"{theater}#{time_slot}#{selected_day}"

    try:
        # Check if any of the seats were already booked
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex',
            KeyConditionExpression=Key('movie').eq(movie_title) &
                                   Key('theater_time_composite').eq(composite_key_value)
        )
        occupied_seats = []
        for b in response.get('Items', []):
            occupied_seats.extend(b['seats'].split(','))

        for seat in seats:
            if seat in occupied_seats:
                flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
                return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))

        # All good: Save booking
        booking_item = {
            'booking_id': booking_id,
            'user_email': user_email,
            'movie': movie_title,
            'theater': theater,
            'time': time_slot,
            'price': total_price,
            'seats': ",".join(seats),
            'timestamp': timestamp,
            'selected_day': selected_day, # Store the selected day
            'theater_time_composite': composite_key_value # Store the composite key
        }
        table_bookings.put_item(Item=booking_item)
        flash("Booking confirmed!")

        # Generate PDF
        buffer = generate_ticket_pdf(booking_item)

        # Email PDF via SNS (asynchronous)
        threading.Thread(target=email_ticket_via_sns, args=(user_email, buffer, booking_item)).start()

        # Show confirmation
        return render_template(
            'ticket_confirmation.html',
            booking=booking_item
        )

    except ClientError as e:
        print(f"DynamoDB error during finalize_booking: {e.response['Error']['Message']}")
        flash("An error occurred while finalizing your booking. Please try again.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))
    except Exception as e:
        print(f"Unexpected error in finalize_booking: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))


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
        try:
            p.drawImage(poster_path, 50, 570, width=120, height=170)
        except Exception as e:
            print(f"Error drawing poster image on PDF: {e}")

    y = 700
    p.setFont("Helvetica", 14)
    p.setFillColor(white) # Ensure text is white on dark background
    details = [
        f"Booking ID: {booking['booking_id']}",
        f"Movie: {booking['movie']}",
        f"Theater: {booking['theater']}",
        f"Date: {booking.get('selected_day', 'N/A')}", # Display the day
        f"Time: {booking['time']}",
        f"Seats: {booking['seats']}",
        f"Total Price: ₹{booking['price']}"
    ]
    for line in details:
        p.drawString(200, y, line)
        y -= 30

    p.setStrokeColor(HexColor("#01b4e4"))
    p.line(50, 550, A4[0]-50, 550)

    # Use _external=True to get a full URL for the QR code
    qr_url = url_for('view_ticket', booking_id=booking['booking_id'], _external=True)
    qr_img = qrcode.make(qr_url)
    qr_buf = BytesIO()
    qr_img.save(qr_buf)
    qr_buf.seek(0)
    p.drawImage(ImageReader(qr_buf), 50, 370, width=150, height=150)

    p.setFont("Helvetica-Oblique", 12)
    p.setFillColor(HexColor("#bbbbbb")) # Lighter color for italic text
    p.drawString(220, 470, "Scan to view ticket online.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    try:
        resp = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = resp.get('Item')

        if not booking:
            flash("Booking not found.")
            return redirect(url_for('dashboard'))

        # Generate the PDF again (or retrieve from storage if stored)
        buffer = generate_ticket_pdf(booking)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'movie_magic_ticket_{booking_id}.pdf',
            mimetype='application/pdf'
        )
    except ClientError as e:
        print(f"DynamoDB error during download_ticket: {e.response['Error']['Message']}")
        flash("An error occurred while preparing your ticket for download.")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Unexpected error in download_ticket: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('dashboard'))


@app.route('/ticket_qr/<booking_id>')
def ticket_qr(booking_id):
    # This route is mainly for generating the QR image directly if needed,
    # but the PDF generation embeds the QR code, making this less critical.
    booking_url = url_for('view_ticket', booking_id=booking_id, _external=True)
    qr = qrcode.make(booking_url)
    qr_buf = BytesIO() # Use BytesIO to avoid saving to disk unnecessarily
    qr.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    return send_file(qr_buf, mimetype='image/png')

@app.route('/payment_qr')
def payment_qr():
    amount = request.args.get("amount", "0")
    # For actual payment, replace 'merchant@upi' with a real UPI ID or a payment gateway integration
    upi_string = f"upi://pay?pa=merchant@upi&pn=MovieMagic&am={amount}&cu=INR"

    qr_img = qrcode.make(upi_string)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    return send_file(qr_buf, mimetype='image/png')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User session invalid. Please log in again.")
        session.clear()
        return redirect(url_for('login'))

    # Fetch user's bookings
    bookings = get_user_bookings(user['email'])
    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

def open_browser():
    # Only open browser if not in debug mode for production deployment
    # Or keep for local dev convenience, but disable in actual deployed envs.
    if app.debug: # Only open browser if debug is true (typical for local dev)
        webbrowser.open_new("http://localhost:5000/")

if __name__ == '__main__':
    # It's good practice to set up your AWS environment variables or ~/.aws/credentials
    # before running this.
    # For example:
    # export AWS_ACCESS_KEY_ID='YOUR_ACCESS_KEY'
    # export AWS_SECRET_ACCESS_KEY='YOUR_SECRET_KEY'
    # export AWS_DEFAULT_REGION='us-east-1'

    # The Timer ensures the browser opens after Flask has started listening
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
