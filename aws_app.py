from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import boto3, qrcode, os, threading, webbrowser
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
# IMPORTANT: In a production environment, use a strong, randomly generated secret key
# For example: os.urandom(24).hex()
app.secret_key = 'your_super_secret_key_here_replace_this_for_prod' 

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
        try:
            resp = table_users.get_item(Key={'email': session['email']})
            return resp.get('Item')
        except Exception as e:
            print(f"Error fetching user from DynamoDB: {e}")
            return None
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
        # Convert BytesIO content to hex string for transport via SNS
        "pdf_hex": pdf_buffer.getvalue().hex() 
    }
    try:
        # SNS message must be a string. We'll stringify the dict.
        sns.publish(TopicArn=SNS_TOPIC_ARN, Message=str(payload), Subject="Your Movie Magic Ticket")
        print(f"SNS email sent to {to_email} for booking {booking['booking_id']}")
    except Exception as e:
        print(f"Error sending SNS email: {e}")

# ---------------------- Movie Data----------------------
# Helper to get dates for TODAY, TOMORROW, DAY OF TOMORROW
def get_display_dates():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)
    return {
        'TODAY': today.strftime('%Y-%m-%d'),
        'TOMORROW': tomorrow.strftime('%Y-%m-%d'),
        'DAY OF TOMORROW': day_after_tomorrow.strftime('%Y-%m-%d')
    }

DISPLAY_DATE_MAPPING = get_display_dates()

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
        'teaser_url': 'https://www.youtube.com/embed/tgbNymZ7vqY', # Example YouTube URL
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
        try:
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
        except Exception as e:
            flash(f"Error during registration: {e}")
            print(f"Error registering user: {e}")
            return render_template('register.html')
    return render_template('register.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email') or ''
    if request.method == 'POST':
        email = request.form['email']
        new_password = generate_password_hash(request.form['password'])

        # Check if user exists in DynamoDB
        try:
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
        except Exception as e:
            flash(f"Error during password reset: {e}")
            print(f"Error resetting password: {e}")
            return render_template('reset_password.html', email=email)
    return render_template('reset_password.html', email=email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Get user from DynamoDB
        try:
            response = table_users.get_item(Key={'email': email})
            user = response.get('Item')

            if user and check_password_hash(user['password'], password):
                session['email'] = email
                return redirect(url_for('home1'))
            flash("Invalid credentials.")
        except Exception as e:
            flash(f"Error during login: {e}")
            print(f"Error logging in user: {e}")
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
    
    # Filter movies by location if a location is provided
    if location:
        filtered_movies = []
        for movie in MOVIES:
            # Check if any theater in the movie list matches the location
            matched_theaters = [t for t in movie['theaters'] if location in t['name'].lower()]
            if matched_theaters:
                movie_copy = movie.copy() # Make a copy to avoid modifying original MOVIES data
                movie_copy['theaters'] = matched_theaters # Only include matched theaters
                filtered_movies.append(movie_copy)
    else:
        # If no location, show all movies
        filtered_movies = MOVIES

    return render_template('home1.html', movies=filtered_movies, location=location)

@app.route('/booking_form')
def booking_form():
    if 'email' not in session:
        flash("Please log in to book tickets.")
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
    
    # Pass date mapping to template for display
    current_dates = get_display_dates()

    return render_template('booking_form.html',
                           movie=movie,
                           theaters=filtered_theaters,
                           selected_location=location,
                           display_dates=current_dates)

@app.route('/select_seats')
def select_seats():
    if 'email' not in session:
        flash("Please log in to select seats.")
        return redirect(url_for('login'))

    title = request.args.get('title')
    theater_name = request.args.get('theater')
    time = request.args.get('time')
    date_key = request.args.get('date_key') # e.g., 'TODAY', 'TOMORROW'

    if not all([title, theater_name, time, date_key]):
        flash("Missing movie, theater, time, or date information.")
        return redirect(url_for('home1'))

    movie = next((m for m in MOVIES if m['title'] == title), None)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for('home1'))

    theater = next((t for t in movie['theaters'] if t['name'] == theater_name), None)
    if not theater:
        flash("Theater not found.")
        return redirect(url_for('home1'))

    # Construct the full booking date string for the database query
    booking_date = DISPLAY_DATE_MAPPING.get(date_key)
    if not booking_date:
        flash("Invalid date selection.")
        return redirect(url_for('home1'))

    # Query DynamoDB for occupied seats for this specific movie, theater, date, and time
    # This query relies on the 'MovieTheaterTimeIndex' GSI.
    occupied_seats = []
    try:
        # Note: DynamoDB Query does not support FilterExpression on 'time' if 'time' is not part of the key.
        # It's more efficient to combine movie, theater, and date into the GSI if possible.
        # For current GSI design (movie PK, theater SK), we query by movie/theater and filter by date/time
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex', # This GSI MUST BE CREATED IN YOUR AWS ACCOUNT
            KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(title) &
                                 boto3.dynamodb.conditions.Key('theater').eq(theater_name),
            FilterExpression=boto3.dynamodb.conditions.Attr('booking_date').eq(booking_date) &
                             boto3.dynamodb.conditions.Attr('time').eq(time)
        )
        occupied_bookings = response.get('Items', [])
        for b in occupied_bookings:
            if 'seats' in b and isinstance(b['seats'], str):
                occupied_seats.extend(b['seats'].split(','))
        occupied_seats = list(set(occupied_seats)) # Remove duplicates

    except boto3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and 'MovieTheaterTimeIndex' in str(e):
            flash("Database index missing! Please set up 'MovieTheaterTimeIndex' GSI in DynamoDB.")
            print(f"DynamoDB ValidationException: {e}")
        else:
            flash(f"Error retrieving occupied seats: {e}")
            print(f"Error querying occupied seats: {e}")
        # As a fallback (NOT RECOMMENDED FOR PRODUCTION), you might scan the table.
        # This will be very slow and expensive for large tables.
        try:
            print("Attempting full table scan for occupied seats (inefficient fallback)...")
            scan_response = table_bookings.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('movie').eq(title) &
                                 boto3.dynamodb.conditions.Attr('theater').eq(theater_name) &
                                 boto3.dynamodb.conditions.Attr('booking_date').eq(booking_date) &
                                 boto3.dynamodb.conditions.Attr('time').eq(time)
            )
            occupied_bookings = scan_response.get('Items', [])
            for b in occupied_bookings:
                if 'seats' in b and isinstance(b['seats'], str):
                    occupied_seats.extend(b['seats'].split(','))
            occupied_seats = list(set(occupied_seats))
        except Exception as scan_e:
            print(f"Fallback scan also failed: {scan_e}")
            flash(f"Critical database error. Please contact support. Error: {scan_e}")
            return redirect(url_for('home1'))
    except Exception as e:
        flash(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in select_seats: {e}")
        return redirect(url_for('home1'))


    return render_template(
        'select_seats.html',
        movie=movie,
        selected_theater=theater_name,
        selected_time=time,
        selected_date_key=date_key,
        selected_booking_date=booking_date, # Pass the actual date for consistency
        selected_price=theater['price'],
        occupied_seats=occupied_seats
    )

@app.route('/confirm_ticket', methods=['POST'])
def confirm_ticket():
    movie_title = request.form['movie']
    selected_time = request.form['time']
    theater = request.form['theater']
    date_key = request.form['date_key']
    selected_booking_date = request.form['booking_date']
    seat_price = int(request.form['price'])
    seats_str = request.form.get('seats', '') # Use get with default to avoid KeyError

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
        date_key=date_key,
        booking_date=selected_booking_date,
        seats=selected_seats,
        seat_count=seat_count,
        total_price=total_price,
        poster=poster,
        seat_price=seat_price
    )


@app.route('/view_ticket/<booking_id>')
def view_ticket(booking_id):
    try:
        response = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = response.get('Item')
        if not booking:
            flash("Ticket not found.")
            return "Ticket not found.", 404
        return render_template('view_ticket.html', booking=booking)
    except Exception as e:
        flash(f"Error retrieving ticket: {e}")
        print(f"Error viewing ticket {booking_id}: {e}")
        return "An error occurred while retrieving your ticket.", 500

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        flash("Please log in to view your profile.")
        return redirect(url_for('login'))

    user = get_current_user() # User is a dictionary from DynamoDB
    if not user:
        flash("User profile not found. Please re-login or contact support.")
        return redirect(url_for('login')) 

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        if new_name and new_name != user.get('name'):
            update_expression_parts.append('#N = :newName')
            expression_attribute_names['#N'] = 'name'
            expression_attribute_values[':newName'] = new_name
        
        if new_password: # If password field is filled, hash and update
            update_expression_parts.append('#P = :newPassword')
            expression_attribute_names['#P'] = 'password'
            expression_attribute_values[':newPassword'] = generate_password_hash(new_password)

        if update_expression_parts:
            try:
                table_users.update_item(
                    Key={'email': user['email']},
                    UpdateExpression='SET ' + ', '.join(update_expression_parts),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                flash("Profile updated successfully.")
            except Exception as e:
                flash(f"Error updating profile: {e}")
                print(f"Error updating user profile {user['email']}: {e}")
        else:
            flash("No changes to update.")
        
        # Always redirect after a POST request to prevent re-submission
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'email' not in session:
        flash("Please log in to complete your booking.")
        return redirect(url_for('login'))

    movie = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    booking_date = request.form['booking_date'] # Actual date string
    total_price = request.form['total_price']
    seats = request.form.getlist('seats') # getlist for multiple selected seats

    if not seats:
        flash("No seats selected for payment.")
        # Redirect back to seat selection or confirmation page, retaining context if possible
        return redirect(url_for('select_seats', title=movie, theater=theater, time=time, date_key=request.form['date_key']))

    booking_id = str(uuid.uuid4())

    # Save booking to DynamoDB
    booking_item = {
        'booking_id': booking_id,
        'user_email': session['email'], # Storing user_email for the GSI
        'movie': movie,
        'theater': theater,
        'price': total_price, 
        'time': time,
        'booking_date': booking_date, # Store the actual date
        'seats': ",".join(seats)
    }
    try:
        table_bookings.put_item(Item=booking_item)
    except Exception as e:
        flash(f"Error saving booking to database: {e}")
        print(f"Error putting booking item to DynamoDB: {e}")
        return redirect(url_for('confirm_ticket')) # Go back to allow retry

    # Generate PDF
    buffer = generate_ticket_pdf(booking_item)

    # Email PDF (using SNS) in a non-blocking way
    # Use threading to prevent email sending from blocking the web request
    threading.Thread(target=email_ticket_via_sns, args=(session['email'], buffer, booking_item)).start()

    return render_template(
        'ticket_confirmation.html',
        booking=booking_item # Pass the dictionary for rendering
    )


# Note: The finalize_booking route is essentially a duplicate of process_payment
# if it's meant to handle the final saving of the booking.
# I will keep it for now but recommend merging similar logic if they perform the same action.
@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    if 'email' not in session:
        flash("Please log in to finalize your booking.")
        return redirect(url_for('login'))

    movie_title = request.form['movie']
    theater = request.form['theater']
    time = request.form['time']
    date_key = request.form['date_key']
    booking_date = request.form['booking_date']
    seat_price = int(request.form['seat_price'])
    seats = request.form.getlist('seats')

    if not seats:
        flash("No seats selected.")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time, date_key=date_key))

    # Re-check for existing bookings to prevent race conditions just before finalization
    occupied_seats = []
    try:
        response = table_bookings.query(
            IndexName='MovieTheaterTimeIndex', # This GSI MUST BE CREATED IN YOUR AWS ACCOUNT
            KeyConditionExpression=boto3.dynamodb.conditions.Key('movie').eq(movie_title) &
                                 boto3.dynamodb.conditions.Key('theater').eq(theater),
            FilterExpression=boto3.dynamodb.conditions.Attr('booking_date').eq(booking_date) &
                             boto3.dynamodb.conditions.Attr('time').eq(time)
        )
        existing_bookings = response.get('Items', [])
        for b in existing_bookings:
            if 'seats' in b and isinstance(b['seats'], str):
                occupied_seats.extend(b['seats'].split(','))
        occupied_seats = list(set(occupied_seats)) # Ensure unique occupied seats
    except boto3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and 'MovieTheaterTimeIndex' in str(e):
            flash("Database index missing for seat availability check! Please set up 'MovieTheaterTimeIndex' GSI in DynamoDB.")
            print(f"DynamoDB ValidationException in finalize_booking: {e}")
        else:
            flash(f"Error checking seat availability: {e}")
            print(f"Error querying existing bookings in finalize_booking: {e}")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time, date_key=date_key))
    except Exception as e:
        flash(f"An unexpected error occurred during seat check: {e}")
        print(f"Unexpected error in finalize_booking seat check: {e}")
        return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time, date_key=date_key))

    for seat in seats:
        if seat in occupied_seats:
            flash(f"Seat {seat} has just been booked by someone else. Please select different seats.")
            return redirect(url_for('select_seats', title=movie_title, theater=theater, time=time, date_key=date_key))

    # All good: Save booking
    booking_id = str(uuid.uuid4())
    total_price = str(len(seats) * seat_price)

    booking_item = {
        'booking_id': booking_id,
        'user_email': session['email'],
        'movie': movie_title,
        'theater': theater,
        'time': time,
        'booking_date': booking_date, # Store the actual date
        'price': total_price,
        'seats': ",".join(seats)
    }
    try:
        table_bookings.put_item(Item=booking_item)
    except Exception as e:
        flash(f"Error saving final booking: {e}")
        print(f"Error putting final booking item to DynamoDB: {e}")
        return redirect(url_for('confirm_ticket'))

    # Generate PDF
    buffer = generate_ticket_pdf(booking_item)

    # Email PDF (using SNS)
    threading.Thread(target=email_ticket_via_sns, args=(session['email'], buffer, booking_item)).start()

    # Show confirmation
    return render_template(
        'ticket_confirmation.html',
        booking=booking_item
    )

def generate_ticket_pdf(booking):
    # 'booking' is expected to be a dictionary from DynamoDB get_item or put_item
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
            print(f"Error drawing poster image {poster_path}: {e}")

    y = 700
    p.setFont("Helvetica", 14)
    p.setFillColor(white) # Set text color to white
    details = [
        f"Booking ID: {booking.get('booking_id', 'N/A')}",
        f"Movie: {booking.get('movie', 'N/A')}",
        f"Theater: {booking.get('theater', 'N/A')}",
        f"Date: {booking.get('booking_date', 'N/A')}", # Display the actual date
        f"Time: {booking.get('time', 'N/A')}",
        f"Seats: {booking.get('seats', 'N/A')}",
        f"Total Price: ₹{booking.get('price', 'N/A')}"
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
    p.drawCentredString(A4[0]/2, 50, "Thank you for booking with Movie Magic.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


@app.route('/download_ticket/<booking_id>')
def download_ticket(booking_id):
    try:
        response = table_bookings.get_item(Key={'booking_id': booking_id})
        booking = response.get('Item')
        if not booking:
            flash("Booking not found.")
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"Error fetching booking for download: {e}")
        print(f"Error getting booking {booking_id} for download: {e}")
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
            print(f"Error loading image for PDF: {e}")

    # === Details ===
    p.setFont("Helvetica", 14)
    p.setFillColor(white)
    y = 700

    details = [
        f"Booking ID: {booking.get('booking_id', 'N/A')}",
        f"Movie: {booking.get('movie', 'N/A')}",
        f"Theater: {booking.get('theater', 'N/A')}",
        f"Date: {booking.get('booking_date', 'N/A')}", # Display the actual date
        f"Time: {booking.get('time', 'N/A')}",
        f"Seats: {booking.get('seats', 'N/A')}",
        f"Price: ₹{booking.get('price', 'N/A')}"
    ]

    for line in details:
        p.drawString(200, y, line)
        y -= 30

    # === Divider line ===
    p.setStrokeColor(HexColor("#01b4e4"))
    p.setLineWidth(1)
    p.line(50, 550, A4[0]-50, 550)

    # === QR Code ===
    # IMPORTANT: In production, use your actual domain for _external=True
    qr_url = url_for('view_ticket', booking_id=booking['booking_id'], _external=True) 
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
        download_name=f"movie_magic_ticket_{booking_id}.pdf",
        mimetype='application/pdf'
    )


@app.route('/ticket_qr/<booking_id>')
def ticket_qr(booking_id):
    # In production, use your actual domain for _external=True
    booking_url = url_for('view_ticket', booking_id=booking_id, _external=True)
    qr = qrcode.make(booking_url)
    qr_buf = BytesIO()
    qr.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    return send_file(qr_buf, mimetype='image/png')

@app.route('/payment_qr')
def payment_qr():
    amount = request.args.get("amount", "0")
    # This UPI string is a placeholder. A real UPI payment flow requires more integration.
    upi_string = f"upi://pay?pa=merchant@upi&pn=MovieMagic&am={amount}&cu=INR"

    qr_img = qrcode.make(upi_string)
    qr_buf = BytesIO()
    qr_img.save(qr_buf)
    qr_buf.seek(0)

    return send_file(qr_buf, mimetype='image/png')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        flash("Please log in to view your dashboard.")
        return redirect(url_for('login'))

    user = get_current_user() # User is a dictionary now
    if not user:
        flash("User not found in session. Please re-login.")
        return redirect(url_for('login'))

    # Retrieve user's bookings from DynamoDB using the 'UserEmailIndex' GSI.
    # This GSI MUST BE CREATED IN YOUR AWS ACCOUNT with 'user_email' as Partition Key.
    bookings = []
    try:
        response = table_bookings.query(
            IndexName='UserEmailIndex', # This GSI MUST EXIST in DynamoDB
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_email').eq(user['email'])
        )
        bookings = response.get('Items', [])
        # Sort bookings by date and time (newest first) for better display
        bookings.sort(key=lambda x: (x.get('booking_date', ''), x.get('time', '')), reverse=True)
    except boto3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and 'UserEmailIndex' in str(e):
            flash("Database index missing for dashboard! Please set up 'UserEmailIndex' GSI in DynamoDB.")
            print(f"DynamoDB ValidationException: {e}")
        else:
            flash(f"Could not retrieve your bookings: {e}")
            print(f"Error querying bookings by user email: {e}")
    except Exception as e:
        flash(f"An unexpected error occurred while fetching bookings: {e}")
        print(f"Unexpected error in dashboard: {e}")

    return render_template('dashboard.html', user=user, tickets=bookings, total_tickets=len(bookings))

def open_browser():
    # Only open browser if not in a CI/CD or headless environment
    if not os.environ.get("WERKZEUG_RUN_MAIN"): # Prevents opening multiple tabs in debug mode
        print("Opening browser to http://localhost:5000/")
        webbrowser.open_new("http://localhost:5000/")

if __name__ == '__main__':
    # Initial setup guidance (for developer's convenience)
    print("\n--- Movie Magic Application Startup ---")
    print("Ensure the following AWS DynamoDB resources are set up in 'us-east-1':")
    print(f"  - Table: '{USER_TABLE}' with primary key 'email'")
    print(f"  - Table: '{BOOKING_TABLE}' with primary key 'booking_id'")
    print(f"  - GSI on '{BOOKING_TABLE}': 'MovieTheaterTimeIndex' (PK: 'movie', SK: 'theater')")
    print(f"  - GSI on '{BOOKING_TABLE}': 'UserEmailIndex' (PK: 'user_email')")
    print(f"  - SNS Topic ARN updated in code: '{SNS_TOPIC_ARN}'")
    print("Ensure your AWS credentials are configured (e.g., via environment variables, ~/.aws/credentials, or IAM roles).")
    print("--- Starting Flask App ---")

    # Small delay before opening browser to allow server to start
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
