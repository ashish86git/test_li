from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid, random
import os
import qrcode
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"

# -------------------- DB Config --------------------
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user='u7tqojjihbpn7s',
        password='p1b1897f6356bab4e52b727ee100290a84e4bf71d02e064e90c2c705bfd26f4a5',
        host='c7s7ncbk19n97r.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com',
        port=5432,
        database='d8lp4hr6fmvb9m'
    )
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Upload folder config
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB limit

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------- Models --------------------
class User(db.Model):
    __tablename__ = "users_library"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mobile = db.Column(db.String(20))
    password = db.Column(db.String(200), nullable=False)
    profile_address = db.Column(db.Text)

    messages = db.relationship("Message", backref="user", cascade="all, delete-orphan")
    bookings = db.relationship("Booking", backref="user", cascade="all, delete-orphan")

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey("users_library.id", ondelete="CASCADE"))
    text = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime, nullable=False)

class Seat(db.Model):
    __tablename__ = "seats"
    id = db.Column(db.String(36), primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # available, booked, blocked

    bookings = db.relationship("Booking", backref="seat", cascade="all, delete-orphan")

class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey("users_library.id", ondelete="CASCADE"))
    seat_id = db.Column(db.String(36), db.ForeignKey("seats.id", ondelete="CASCADE"))
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    valid_till = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(50))
    email = db.Column(db.String(150))
    aadhaar = db.Column(db.String(300))   # ONLY filename stored
    photo = db.Column(db.String(300))     # ONLY filename stored


# -------------------- Constants --------------------
PRICE_MAP = {
    "Deluxe": 1800,
    "Premium": 1700,
    "Unreserved": 1200,
    "12Hrs-Day": 1500,
    "12Hrs-Night": 800,
    "12Hrs-Day-UR": 1000,
    "12Hrs-Night-UR": 600
}

LOCATIONS = ["Hall-A", "Hall-B", "First-Floor", "Second-Floor"]
TYPES = list(PRICE_MAP.keys())

# -------------------- Helpers --------------------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)

def get_seat_types():
    return sorted({s.type for s in Seat.query.all()})

def get_locations():
    return sorted({s.location for s in Seat.query.all()})

def get_grouped_locations():
    return {
        "Wazirabad": ["Hall-A", "Hall-B"],
        "Sant Kabir Nagar": ["First-Floor", "Second-Floor"]
    }

# -------------------- Seat Initialization --------------------
def init_seats():
    if Seat.query.count() == 0:
        random.seed(3)
        for i in range(1, 301):
            seat_type = random.choice(TYPES)
            location = random.choice(LOCATIONS)
            seat = Seat(
                id=f"S{i}",
                number=i,
                type=seat_type,
                price=PRICE_MAP[seat_type],
                location=location,
                status="available"
            )
            db.session.add(seat)
        db.session.commit()

# -------------------- Routes --------------------
@app.route("/")
def index():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if session.get("user_id"):
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))

# -------- AUTH --------
ADMIN_EMAIL = "admin@library.com"
ADMIN_PASSWORD = "admin123"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        pwd = request.form["password"].strip()

        # Admin login
        if email == ADMIN_EMAIL and pwd == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        # Normal user login
        user = User.query.filter_by(email=email, password=pwd).first()
        if user:
            session.clear()
            session["user_id"] = user.id
            session["is_admin"] = False
            return redirect(url_for("student_dashboard"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uid = str(uuid.uuid4())
        user = User(
            id=uid,
            name=request.form["name"],
            email=request.form["email"],
            mobile=request.form["mobile"],
            password=request.form["password"],
            profile_address=""
        )
        db.session.add(user)
        db.session.commit()
        session.clear()
        session["user_id"] = uid
        session["is_admin"] = False
        return redirect(url_for("student_dashboard"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------- STUDENT --------
@app.route("/student_dashboard")
def student_dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    filter_type = request.args.get("type", "").strip()
    filter_location = request.args.get("location", "").strip()

    q = Seat.query
    if filter_type:
        q = q.filter_by(type=filter_type)
    if filter_location:
        q = q.filter_by(location=filter_location)
    # ✅ Always sort seats by number so map fixed रहे
    filtered_seats = q.order_by(Seat.number.asc()).all()

    my_bookings = Booking.query.filter_by(user_id=user.id).all()

    return render_template(
        "student_dashboard.html",
        seats=filtered_seats,
        bookings=my_bookings,
        user=user,
        seat_types=get_seat_types(),
        locations=get_locations(),
        grouped_locations=get_grouped_locations(),
        filter_type=filter_type,
        filter_location=filter_location
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = User.query.filter_by(id=user_id).first()
    if request.method == "POST":
        # update logic
        user.name = request.form["name"]
        user.email = request.form["email"]
        user.mobile = request.form["mobile"]
        user.password = request.form["password"]
        user.profile_address = request.form["profile_address"]
        db.session.commit()
        flash("Profile updated successfully")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)





@app.route("/book", methods=["POST"])
def book():
    user = current_user()
    if not user:
        return jsonify({"success": False, "message": "Login required"})

    seat_id = request.form.get("seat_id")
    name = request.form.get("name") or user.name
    contact = request.form.get("contact") or user.mobile or ""
    email = request.form.get("email") or user.email
    valid_till_str = request.form.get("valid_till")

    aadhaar_file = request.files.get("aadhaar")
    photo_file = request.files.get("photo")

    if not aadhaar_file or not allowed_file(aadhaar_file.filename):
        return jsonify({"success": False, "message": "Invalid Aadhaar file"})
    if not photo_file or not allowed_file(photo_file.filename):
        return jsonify({"success": False, "message": "Invalid Photo file"})

    # Save files to static/uploads
    aadhaar_filename = secure_filename(f"AADHAAR_{uuid.uuid4()}_{aadhaar_file.filename}")
    photo_filename = secure_filename(f"PHOTO_{uuid.uuid4()}_{photo_file.filename}")

    aadhaar_save_path = os.path.join(app.config["UPLOAD_FOLDER"], aadhaar_filename)
    photo_save_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_filename)

    aadhaar_file.save(aadhaar_save_path)
    photo_file.save(photo_save_path)

    seat = Seat.query.get(seat_id)
    if not seat:
        return jsonify({"success": False, "message": "Seat not found"})
    if seat.status != "available":
        return jsonify({"success": False, "message": "Seat not available"})

    try:
        valid_till = datetime.strptime(valid_till_str, "%Y-%m-%d") if valid_till_str else (datetime.now() + timedelta(days=30))
    except Exception:
        valid_till = datetime.now() + timedelta(days=30)

    seat.status = "booked"
    booking = Booking(
        id=str(uuid.uuid4()),
        user_id=user.id,
        seat_id=seat.id,
        amount=seat.price,
        created_at=datetime.now(),
        valid_till=valid_till,
        name=name,
        contact=contact,
        email=email,
        aadhaar=aadhaar_filename,
        photo=photo_filename
    )
    db.session.add(booking)
    db.session.commit()

    return jsonify({"success": True, "booking_id": booking.id})



@app.route("/invoice/<bid>")
def invoice(bid):
    booking = Booking.query.get(bid)
    user = current_user()
    if not booking or not user:
        return "Not found", 404
    seat = Seat.query.get(booking.seat_id)

    # QR code data
    qr_data = f"""
    Booking ID: {booking.id}
    Name: {booking.name}
    Seat: {seat.id} ({seat.type})
    Amount: ₹{booking.amount}
    Valid Till: {booking.valid_till.strftime('%Y-%m-%d')}
    """

    qr_folder = os.path.join(app.static_folder, "qrcodes")
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, f"{booking.id}.png")

    if not os.path.exists(qr_path):
        img = qrcode.make(qr_data)
        img.save(qr_path)

    return render_template("invoice.html", booking=booking, seat=seat, user=user)


# -------- ADMIN --------
@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    filter_type = request.args.get("type", "").strip()
    filter_location = request.args.get("location", "").strip()

    q = Seat.query
    if filter_type:
        q = q.filter_by(type=filter_type)
    if filter_location:
        q = q.filter_by(location=filter_location)
    # ✅ Always keep seats ordered by number
    filtered_seats = q.order_by(Seat.number.asc()).all()

    return render_template(
        "admin_dashboard.html",
        seats=filtered_seats,
        bookings=Booking.query.all(),
        users=User.query.all(),
        seat_types=get_seat_types(),
        locations=get_locations(),
        grouped_locations=get_grouped_locations(),
        filter_type=filter_type,
        filter_location=filter_location
    )

@app.route("/admin_action", methods=["POST"])
def admin_action():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Not authorized"})
    seat_id = request.json.get("seat_id")
    action = request.json.get("action")
    seat = Seat.query.get(seat_id)
    if not seat:
        return jsonify({"success": False})

    if action == "block":
        seat.status = "blocked"
    elif action == "unblock":
        seat.status = "available"
    elif action == "unbook":
        seat.status = "available"
        Booking.query.filter_by(seat_id=seat_id).delete()
    db.session.commit()
    return jsonify({"success": True})

@app.route("/admin_message", methods=["POST"])
def admin_message():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Not authorized"})
    uid = request.form["user_id"]
    msg = request.form["message"]
    message = Message(
        id=str(uuid.uuid4()),
        user_id=uid,
        text=msg,
        time=datetime.now()
    )
    db.session.add(message)
    db.session.commit()
    return jsonify({"success": True})

@app.route("/admin_update_seat", methods=["POST"])
def admin_update_seat():
    if not session.get("is_admin"):
        return "Not authorized", 403

    sid = request.form["seat_id"]
    stype = request.form["type"]
    sprice = int(request.form["price"])
    sloc = request.form["location"]

    seat = Seat.query.get(sid)
    if seat:
        seat.type = stype
        seat.price = sprice
        seat.location = sloc
        db.session.commit()
        return redirect(url_for("admin_dashboard"))
    return "Seat not found", 404


@app.route("/dashboard")
def dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    today = datetime.today().date()

    # ✅ Today Booked Seats
    today_booked = Booking.query.filter(
        db.func.date(Booking.created_at) == today
    ).count()

    # ✅ Today Validity Ending
    today_ending = Booking.query.filter(
        db.func.date(Booking.valid_till) == today
    ).count()

    # ✅ Last 7 Days Payments
    last7days_payment = db.session.query(
        db.func.sum(Booking.amount)
    ).filter(
        Booking.created_at >= datetime.today() - timedelta(days=7)
    ).scalar() or 0

    # ✅ Total Payment (All Time)
    total_payment = db.session.query(
        db.func.sum(Booking.amount)
    ).scalar() or 0

    # ✅ Seat Counts
    total_booked = Seat.query.filter_by(status="booked").count()
    total_available = Seat.query.filter_by(status="available").count()
    total_blocked = Seat.query.filter_by(status="blocked").count()
    total_seats = Seat.query.count()

    # ✅ Payments per day & Seat Bookings per day
    payments_by_day = []
    bookings_by_day = []
    labels = []
    for i in range(6, -1, -1):  # last 7 days
        day = today - timedelta(days=i)
        labels.append(day.strftime("%d %b"))

        # Payment
        amount = db.session.query(
            db.func.sum(Booking.amount)
        ).filter(db.func.date(Booking.created_at) == day).scalar() or 0
        payments_by_day.append(amount)

        # Seat bookings
        booked = Booking.query.filter(
            db.func.date(Booking.created_at) == day
        ).count()
        bookings_by_day.append(booked)

    return render_template("dashboard.html",
        today_booked=today_booked,
        today_ending=today_ending,
        last7days_payment=last7days_payment,
        total_payment=total_payment,
        total_booked=total_booked,
        total_available=total_available,
        total_blocked=total_blocked,
        total_seats=total_seats,
        labels=labels,
        payments_by_day=payments_by_day,
        bookings_by_day=bookings_by_day
    )



# ---------- Run ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        init_seats()
    app.run(debug=True)
