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
from datetime import datetime, timedelta # Used for 'TODAY', 'TOMORROW' logic if you expand on it

app = Flask(__name__)
# !!! IMPORTANT: CHANGE THIS TO A STRONG, RANDOM KEY IN PRODUCTION !!!
app.secret_key = 'your_secret_key_CHANGE_THIS_IN_PRODUCTION'

# AWS Setup
# Ensure your AWS credentials are configured:
# 1. IAM Role for EC2 (recommended for production)
# 2. AWS CLI configured (~/.aws/credentials) for local development
# 3. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

USER_TABLE = 'MovieMagicUsers'
BOOKING_TABLE = 'MovieMagicBookings'
# !!! IMPORTANT: Replace with YOUR ACTUAL SNS Topic ARN !!!
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:YourMovieMagicSNSTopic' # <<< REPLACE THIS!

table_users = dynamodb.Table(USER_TABLE)
table_bookings = dynamodb.Table(BOOKING_TABLE)


# Helper funcs
def get_current_user():
    """Retrieves current user details from DynamoDB based on session email."""
    if 'email' in session:
        try:
            resp = table_users.get_item(Key={'email': session['email']})
            return resp.get('Item')
        except ClientError as e:
            print(f"DynamoDB error getting user {session['email']}: {e.response['Error']['Message']}")
            return None
    return None

def get_user_bookings(email):
    """Retrieves all bookings for a given user email using GSI."""
    # This query assumes you have a GSI named 'UserEmailIndex' on table_bookings
    # with 'user_email' as Partition Key.
    try:
        response = table_bookings.query(
            IndexName='UserEmailIndex',
            KeyConditionExpression=Key('user_email').eq(email)
            # You can add ScanIndexForward=False here if you want most recent bookings first
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"DynamoDB query error for user bookings ({email}): {e.response['Error']['Message']}")
        return []

def email_ticket_via_sns(to_email, pdf_buffer, booking):
    """Sends movie ticket PDF as an email via AWS SNS."""
    pdf_buffer.seek(0)
    # The payload is a dictionary which will be converted to a JSON string for SNS
    # Your SNS consumer (e.g., Lambda) will parse this JSON.
    payload = {
        "to": to_email,
        "booking_id": booking['booking_id'],
        "movie": booking['movie'],
        "theater": booking['theater'],
        "time": booking['time'],
        "seats": booking['seats'],
        "selected_day": booking.get('selected_day', 'N/A'), # Include day in email payload
        "pdf_hex": pdf_buffer.getvalue().hex() # PDF content as hex string
    }
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(payload), # Message must be a string (JSON stringify)
            Subject='🎟️ Your Movie Magic Ticket!'
        )
        print(f"SNS email triggered successfully for {to_email} and booking {booking['booking_id']}")
    except Exception as e:
        print(f"Error publishing SNS message for email to {to_email}: {e}")

# ---------------------- Movie Data (Remains the same as provided) ----------------------

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
            resp = table_users.get_item(Key={'email': email})
            existing_user = resp.get('Item')

            if existing_user:
                flash("Email already registered. Please reset your password or log in.")
                return redirect(url_for('login')) # Redirect to login if email exists
            else:
                table_users.put_item(
                    Item={
                        'email': email,
                        'name': name,
                        'password': password # Stored as hash
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
            resp = table_users.get_item(Key={'email': email})
            user = resp.get('Item')

            if user:
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
            resp = table_users.get_item(Key={'email': email})
            user = resp.get('Item')

            if user and check_password_hash(user['password'], password):
                session['email'] = email
                flash(f"Welcome back, {user.get('name', user['email'])}!")
                return redirect(url_for('home1'))
            flash("Invalid email or password.")
        except ClientError as e:
            print(f"DynamoDB error during login: {e.response['Error']['Message']}")
            flash("An error occurred during login. Please try again.")
        except Exception as e: # Catch other potential errors like missing 'password' key
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
        flash("Please log in to view movies.")
        return redirect(url_for('login'))

    location = request.args.get('location', '').lower()
    filtered_movies = []

    if location:
        for movie in MOVIES:
            matched_theaters = [t for t in movie['theaters'] if location in t['name'].lower()]
            if matched_theaters:
                movie_copy = movie.copy()
                movie_copy['theaters'] = matched_theaters
                filtered_movies.append(movie_copy)
    else:
        filtered_movies = MOVIES

    return render_template('home1.html', movies=filtered_movies, location=location)

@app.route('/booking_form')
def booking_form():
    if 'email' not in session:
        flash("Please log in to book tickets.")
        return redirect(url_for('login'))

    title = request.args.get('title')
    location = request.args.get('location', '').lower()
    selected_day = request.args.get('day', 'TODAY') # Default to TODAY

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    filtered_theaters = [
        t for t in movie['theaters']
        if location in t['name'].lower()
    ] if location else movie['theaters']

    available_days = []
    if filtered_theaters:
        # Get all unique days available across all filtered theaters for this movie
        all_days = set()
        for theater_item in filtered_theaters:
            all_days.update(theater_item['timings_by_day'].keys())
        available_days = sorted(list(all_days), key=lambda x: (x != 'TODAY', x != 'TOMORROW', x != 'DAY OF TOMORROW', x)) # Sort for consistency
        
        # Ensure selected_day is valid, default if not
        if selected_day not in available_days:
            selected_day = 'TODAY' if 'TODAY' in available_days else (available_days[0] if available_days else '')


    return render_template('booking_form.html',
                           movie=movie,
                           theaters=filtered_theaters,
                           selected_location=location,
                           available_days=available_days,
                           selected_day=selected_day)

@app.route('/select_seats')
def select_seats():
    if 'email' not in session:
        flash("Please log in to select seats.")
        return redirect(url_for('login'))

    title = request.args.get('title')
    theater_name = request.args.get('theater')
    time_slot = request.args.get('time')
    day = request.args.get('day') # The selected day (e.g., 'TODAY', 'TOMORROW')

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    theater = next((t for t in movie['theaters'] if t['name'] == theater_name), None)
    if not theater:
        flash("Theater not found.")
        return redirect(url_for('home1'))
    
    # IMPORTANT: Construct the composite key exactly as it's defined as the Sort Key for your GSI
    # This must be consistent with how you save it in process_payment/finalize_booking
    composite_key_value = f"{theater_name}#{time_slot}#{day}"

    occupied_seats = []
    try:
        # Query DynamoDB using the GSI
        # Partition Key: 'movie' -> movie title
        # Sort Key: 'theater_time_composite' -> combination of theater name, time, and day
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex', # Ensure this GSI exists in DynamoDB
            KeyConditionExpression=Key('movie').eq(title) &
                                   Key('theater_time_composite').eq(composite_key_value)
        )
        for b in response.get('Items', []):
            occupied_seats.extend(b['seats'].split(','))
    except ClientError as e:
        print(f"DynamoDB query error in select_seats for movie '{title}': {e.response['Error']['Message']}")
        flash("Error fetching seat availability. Please try again.")
        # Redirect back to booking form in case of error
        return redirect(url_for('booking_form', title=title, location=request.args.get('location')))


    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time_slot,
        selected_price=theater['price'],
        occupied_seats=occupied_seats,
        selected_day=day # Pass day to template for hidden fields etc.
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
    seats_str = request.form['seats']
    selected_day = request.form['day'] # Get the day from the form

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
    """Displays a single ticket's details."""
    try:
        resp = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = resp.get('Item')

        if not booking:
            flash("Ticket not found.")
            return redirect(url_for('dashboard')) # Redirect to dashboard if ticket not found
        
        # Ensure data types are consistent for display if needed (e.g., price might be string from DB)
        # booking['price'] = float(booking['price']) # Example if you want to convert back to float

        return render_template('view_ticket.html', booking=booking)
    except ClientError as e:
        print(f"DynamoDB error viewing ticket {booking_id}: {e.response['Error']['Message']}")
        flash("An error occurred while fetching your ticket.")
        return redirect(url_for('dashboard')) # Redirect to dashboard on error

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """Allows users to view and update their profile details."""
    if 'email' not in session:
        flash("Please log in to view your profile.")
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User session invalid. Please log in again.")
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        # Build update expression dynamically
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        updated = False

        if new_name and new_name != user.get('name'):
            update_expression_parts.append('#n = :new_name')
            expression_attribute_names['#n'] = 'name'
            expression_attribute_values[':new_name'] = new_name
            user['name'] = new_name # Update in memory
            updated = True

        if new_password: # Check if a new password was provided
            hashed_password = generate_password_hash(new_password)
            # You might want a stronger check here, e.g., if password length > 0
            if hashed_password != user.get('password'): # Avoid updating if hash is identical (rare for new hashes)
                update_expression_parts.append('#pw = :new_password')
                expression_attribute_names['#pw'] = 'password'
                expression_attribute_values[':new_password'] = hashed_password
                user['password'] = hashed_password # Update in memory
                updated = True

        if updated:
            try:
                table_users.update_item(
                    Key={'email': user['email']},
                    UpdateExpression='SET ' + ', '.join(update_expression_parts),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                flash("Profile updated successfully.")
            except ClientError as e:
                print(f"DynamoDB error updating profile for {user['email']}: {e.response['Error']['Message']}")
                flash("An error occurred while updating your profile. Please try again.")
        else:
            flash("No changes were made to the profile.")

        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    """Processes payment and creates a new booking in DynamoDB."""
    if 'email' not in session:
        flash("Please log in to complete your booking.")
        return redirect(url_for('login'))

    movie = request.form['movie']
    theater = request.form['theater']
    time_slot = request.form['time']
    selected_day = request.form['selected_day'] # The day string from the form
    total_price = request.form['total_price']
    seats_str = request.form['seats'] # e.g., "A1,A2,B3"
    seats = seats_str.split(',') if seats_str else []

    if not seats:
        flash("No seats selected. Please go back and select your seats.")
        # Redirect back to seat selection with original parameters
        return redirect(url_for('select_seats', title=movie, theater=theater, time=time_slot, day=selected_day))

    user_email = session['email']
    booking_id = str(uuid.uuid4())
    timestamp = str(int(time.time())) # Unix timestamp for creation time

    # CRITICAL: Construct the composite key for the GSI query for checking occupied seats.
    # This MUST exactly match how you've configured the Sort Key of your 'MovieTheaterTimeIndex' GSI.
    # Assuming GSI Sort Key is 'theater_time_composite' which includes theater, time, and day.
    composite_key_value = f"{theater}#{time_slot}#{selected_day}"

    try:
        # Step 1: Check for concurrent bookings using the GSI
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex', # Ensure this GSI is correctly configured in DynamoDB
            KeyConditionExpression=Key('movie').eq(movie) &
                                   Key('theater_time_composite').eq(composite_key_value)
        )
        occupied_seats_for_time_slot = []
        for b in response.get('Items', []):
            # Extend with seats from existing bookings for this movie, theater, time, day
            occupied_seats_for_time_slot.extend(b['seats'].split(','))

        # Check if any of the requested seats are now occupied
        for seat in seats:
            if seat in occupied_seats_for_time_slot:
                flash(f"Seat {seat} has just been booked by someone else for this show. Please select different seats.")
                # Redirect back to seat selection to allow re-selection
                return redirect(url_for('select_seats', title=movie, theater=theater, time=time_slot, day=selected_day))

        # Step 2: If all seats are available, proceed to save the booking
        booking_item = {
            'booking_id': booking_id,         # Primary Key (Partition Key of table)
            'user_email': user_email,         # GSI Partition Key for UserEmailIndex
            'movie': movie,                   # GSI Partition Key for MovieTheaterTimeIndex
            'theater': theater,
            'time': time_slot,
            'price': total_price,             # Stored as string to avoid float precision issues in DynamoDB
            'seats': ",".join(seats),         # Stored as comma-separated string
            'timestamp': timestamp,           # Useful for sorting/ordering bookings
            'selected_day': selected_day,     # Store the specific day (TODAY/TOMORROW etc.)
            'theater_time_composite': composite_key_value # GSI Sort Key for MovieTheaterTimeIndex
        }

        table_bookings.put_item(Item=booking_item)
        flash("Payment processed and booking created successfully!")

        # Step 3: Generate PDF and send email asynchronously via SNS
        pdf_buffer = generate_ticket_pdf(booking_item)
        # It's good practice to run email sending in a background thread to not block the user
        threading.Thread(target=email_ticket_via_sns, args=(user_email, pdf_buffer, booking_item)).start()

        return render_template(
            'ticket_confirmation.html',
            booking=booking_item # Pass the booking item dictionary to the template
        )

    except ClientError as e:
        print(f"DynamoDB error during process_payment for {user_email}: {e.response['Error']['Message']}")
        flash(f"An error occurred during booking. Error details: {e.response['Error']['Message']}")
        # Redirect back to the confirmation page to allow retrying or re-selecting seats
        return redirect(url_for('confirm_ticket', movie=movie, theater=theater, time=time_slot, seats=seats_str, price=request.form['seat_price'], day=selected_day))
    except Exception as e:
        print(f"Unexpected error in process_payment: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('confirm_ticket', movie=movie, theater=theater, time=time_slot, seats=seats_str, price=request.form['seat_price'], day=selected_day))


# The 'finalize_booking' route seems to duplicate logic with 'process_payment'.
# For a real application, you'd typically have one route handling the final booking logic
# after payment confirmation. I'm keeping it updated here for completeness based on your original structure,
# but strongly recommend merging these into a single, cohesive flow.
@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    if 'email' not in session:
        flash("Please log in to finalize your booking.")
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time_slot = request.form['time']
    seat_price = int(request.form['seat_price'])
    seats_str = request.form['seats']
    seats = seats_str.split(',') if seats_str else []
    selected_day = request.form['selected_day'] # Get the day

    if not seats:
        flash("No seats selected.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))

    user_email = session['email']
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)
    timestamp = str(int(time.time()))

    # Composite key for GSI consistency
    composite_key_value = f"{theater}#{time_slot}#{selected_day}"

    try:
        # Check if any of the seats were already booked using GSI
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
            'selected_day': selected_day,
            'theater_time_composite': composite_key_value
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
        flash(f"An error occurred while finalizing your booking. Error details: {e.response['Error']['Message']}")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))
    except Exception as e:
        print(f"Unexpected error in finalize_booking: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time_slot, day=selected_day))


def generate_ticket_pdf(booking):
    """Generates a PDF ticket using ReportLab from booking details."""
    movie = next((m for m in MOVIES if m['title'] == booking['movie']), None)
    poster_path = os.path.join("static", movie['poster_filename']) if movie and movie.get('poster_filename') else None

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # Styling the PDF
    p.setFillColor(HexColor("#0d253f")) # Dark blue background
    p.rect(0, 0, A4[0], A4[1], fill=1)

    p.setFillColor(HexColor("#01b4e4")) # Light blue header bar
    p.rect(0, 770, A4[0], 50, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(A4[0]/2, 785, "🎟 Movie Magic - Your Ticket")

    # Movie Poster
    if poster_path and os.path.exists(poster_path):
        try:
            p.drawImage(poster_path, 50, 570, width=120, height=170)
        except Exception as e:
            print(f"Warning: Could not draw poster image '{poster_path}' on PDF: {e}")

    # Booking Details
    y = 700
    p.setFont("Helvetica", 14)
    p.setFillColor(white) # Text color for details
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

    # Divider line
    p.setStrokeColor(HexColor("#01b4e4"))
    p.setLineWidth(1)
    p.line(50, 550, A4[0]-50, 550)

    # QR Code for online ticket view
    # _external=True ensures a full URL is generated, important for QR codes
    qr_url = url_for('view_ticket', booking_id=booking['booking_id'], _external=True)
    qr_img = qrcode.make(qr_url)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format='PNG') # Specify format
    qr_buf.seek(0)
    p.drawImage(ImageReader(qr_buf), 50, 370, width=150, height=150)

    p.setFont("Helvetica-Oblique", 12)
    p.setFillColor(HexColor("#bbbbbb")) # Lighter color for italic text
    p.drawString(220, 470, "Scan to view ticket online.")

    # Footer
    p.setFont("Helvetica", 10)
    p.setFillColor(HexColor("#bbbbbb"))
    p.drawCentredString(A4[0]/2, 50, "Thank you for booking with Movie Magic. Enjoy the show!")

    p.showPage()
    p.save()
    buffer.seek(0) # Rewind buffer to the beginning
    return buffer


@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    """Allows authenticated users to download their ticket as a PDF."""
    if 'email' not in session:
        flash("Please log in to download tickets.")
        return redirect(url_for('login'))

    try:
        resp = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = resp.get('Item')

        if not booking:
            flash("Booking not found.")
            return redirect(url_for('dashboard'))

        # Optional: Add a check if the booking belongs to the current user
        if booking.get('user_email') != session['email']:
            flash("You do not have permission to download this ticket.")
            return redirect(url_for('dashboard'))

        # Generate the PDF again for download
        buffer = generate_ticket_pdf(booking)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'movie_magic_ticket_{booking_id}.pdf', # Clearer filename
            mimetype='application/pdf'
        )
    except ClientError as e:
        print(f"DynamoDB error during download_ticket for {booking_id}: {e.response['Error']['Message']}")
        flash("An error occurred while preparing your ticket for download. Please try again.")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Unexpected error in download_ticket: {e}")
        flash("An unexpected error occurred. Please try again.")
        return redirect(url_for('dashboard'))


@app.route('/ticket_qr/<booking_id>')
def ticket_qr(booking_id):
    """Generates and serves a QR code image for a given booking ID."""
    # This route is primarily for rendering QR images directly.
    # The QR is already embedded in the PDF, so this might be redundant unless you have specific needs.
    booking_url = url_for('view_ticket', booking_id=booking_id, _external=True)
    qr = qrcode.make(booking_url)
    qr_buf = BytesIO()
    qr.save(qr_buf, format="PNG") # Save to buffer as PNG
    qr_buf.seek(0)
    return send_file(qr_buf, mimetype='image/png')

@app.route('/payment_qr')
def payment_qr():
    """Generates a UPI payment QR code."""
    amount = request.args.get("amount", "0")
    # This is a generic UPI deep link. For a real payment system, you'd integrate with a payment gateway.
    upi_string = f"upi://pay?pa=merchant@upi&pn=MovieMagic&am={amount}&cu=INR"

    qr_img = qrcode.make(upi_string)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    return send_file(qr_buf, mimetype='image/png')

@app.route('/dashboard')
def dashboard():
    """Displays a user's profile and their past bookings."""
    if 'email' not in session:
        flash("Please log in to view your dashboard.")
        return redirect(url_for('login'))

    user = get_current_user()
    if not user:
        flash("User session invalid. Please log in again.")
        session.clear() # Clear session if user not found
        return redirect(url_for('login'))

    # Fetch user's bookings using the GSI on 'user_email'
    bookings = get_user_bookings(user['email'])
    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

def open_browser_on_startup():
    """Opens a browser window to the app's URL when the Flask app starts."""
    # This is useful for local development. In production, you would typically disable this.
    if app.debug: # Only opens in debug mode
        webbrowser.open_new("http://localhost:5000/")

if __name__ == '__main__':
    # It's crucial to have your AWS credentials and region configured in your environment
    # or via ~/.aws/credentials for boto3 to work.
    # For example, in your terminal before running:
    # export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
    # export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
    # export AWS_DEFAULT_REGION="us-east-1" # Or your chosen region

    # Start a timer to open the browser after the Flask server has a moment to start up
    threading.Timer(1.5, open_browser_on_startup).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
