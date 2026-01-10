from flask import (
    Flask,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    session,
    jsonify,
)
from flask_migrate import Migrate
from extensions import db
from models import *
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy.orm import joinedload
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = "THIS_IS_A_FIXED_SECRET_KEY"

# --- Base Directory ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# --- Upload Configuration ---
VIDEO_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads/videos")
PROFILE_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/photos")
MATERIAL_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads/materials")

# Create folders if they don't exist
os.makedirs(VIDEO_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MATERIAL_UPLOAD_FOLDER, exist_ok=True)

# Allowed video extensions
ALLOWED_EXTENSIONS = {"mp4", "mkv", "webm"}
ALLOWED_MATERIALS = {"pdf", "docx", "pptx", "ppt", "zip", "txt", "jpg", "jpeg", "png"}

# Configure app
app.config["UPLOAD_FOLDER_VIDEOS"] = VIDEO_UPLOAD_FOLDER  # For recorded videos
app.config["UPLOAD_FOLDER_PHOTOS"] = PROFILE_UPLOAD_FOLDER  # For profile photos
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024 * 1024  # 1 GB limit for videos
app.config["MATERIAL_FOLDER"] = MATERIAL_UPLOAD_FOLDER

# --- Database Configuration ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    BASE_DIR, "database.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Initialize DB and Migrations ---
db.init_app(app)
migrate = Migrate(app, db)


@app.route("/")  # home page
def home():
    return render_template("index.html")


@app.route("/student")  # student home page
def student_index():
    return render_template("student_index.html")


@app.route("/teacher")  # teacher home page
def teacher_index():
    return render_template("teacher_index.html")


@app.route(
    "/admin/login", methods=["GET", "POST"]
)  # admin login (email =admin@gmail.com, password=admin@123 )
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, password):
            session["admin_id"] = admin.id
            session["role"] = "admin"
            session.permanent = True
            return redirect(url_for("admin_index"))
        print(Admin.query.all())

        flash("Invalid credentials", "danger")

    return render_template("admin_login.html")


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_index"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_index():
    courses = Course.query.all()

    labels = []
    counts = []  # students per course
    material_labels = []
    material_count = []  # materials per course

    for course in courses:
        labels.append(course.name)
        counts.append(len(course.students))
        material_labels.append(course.name)
        material_count.append(len(course.materials))

    return render_template(
        "admin_index.html",
        labels=labels,
        counts=counts,
        material_labels=material_labels,
        material_count=material_count,
        total_students=Student.query.count(),
        total_teachers=Teacher.query.count(),
        total_courses=Course.query.count(),
        total_materials=StudyMaterial.query.count(),
    )


@app.route("/register", methods=["GET", "POST"])
def student_registration():
    courses = Course.query.all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        age = request.form.get("age", "").strip()
        grade = request.form.get("grade", "").strip()
        course_ids = request.form.getlist("course_ids")

        # ----------------- Validation -----------------
        if (
            not name
            or not email
            or not password
            or not age
            or not grade
            or not course_ids
        ):
            flash("All fields are required.", "danger")
            return redirect(url_for("student_registration"))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address.", "danger")
            return redirect(url_for("student_registration"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("student_registration"))

        try:
            age = int(age)
            if age < 10 or age > 100:
                flash("Age must be between 10 and 100.", "danger")
                return redirect(url_for("student_registration"))
        except ValueError:
            flash("Age must be a number.", "danger")
            return redirect(url_for("student_registration"))

        # ----------------- Student Check -----------------
        student = Student.query.filter_by(email=email).first()

        if not student:
            # First-time registration
            hashed_password = generate_password_hash(password)
            student = Student(
                name=name, email=email, password=hashed_password, age=age, grade=grade
            )
            db.session.add(student)
            db.session.flush()  # Get student.id

        # ----------------- Course Enrollment -----------------
        already_enrolled = False

        for cid in course_ids:
            course = Course.query.get(int(cid))
            if course:
                if course in student.courses:
                    already_enrolled = True
                else:
                    student.courses.append(course)

        if already_enrolled:
            flash(
                "You were already enrolled in one or more selected courses.", "warning"
            )

        db.session.commit()

        flash("Registration / Enrollment successful!", "success")
        return redirect(url_for("login"))

    return render_template("student_register.html", courses=courses)


@app.route("/check_student_email")
def check_student_email():
    email = request.args.get("email")
    exists = Student.query.filter_by(email=email).first() is not None
    return jsonify({"exists": exists})


@app.route("/admin/students")
@admin_required
def admin_students():  # admin view students
    search = request.args.get("search")
    course_id = request.args.get("course_id")
    courses = Course.query.all()
    query = Student.query

    if search:
        query = query.filter(
            (Student.name.ilike(f"%{search}%")) | (Student.email.ilike(f"%{search}%"))
        )

    if course_id:
        query = query.join(Student.courses).filter(Course.id == course_id)

    students = query.all()
    return render_template("admin_student.html", students=students, courses=courses)


@app.route("/teacher_register", methods=["GET", "POST"])
def teacher_registration():
    courses = Course.query.all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        qualifications = request.form.get("qualifications", "").strip()
        availability = request.form.get("availability", "").strip()
        years_of_experience = request.form.get("years_of_experience", "").strip()
        contact = request.form.get("contact", "").strip()
        place = request.form.get("place", "").strip()
        course_id = request.form.get("course")
        second_course_id = request.form.get("second_course")

        # ----------------- Validation -----------------
        if (
            not name
            or not email
            or not password
            or not qualifications
            or not availability
            or not years_of_experience
            or not contact
            or not place
        ):
            flash("All fields except second course are required.", "danger")
            return redirect(url_for("teacher_registration"))

        # Email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address.", "danger")
            return redirect(url_for("teacher_registration"))

        # Password length
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("teacher_registration"))

        # Years of experience validation
        try:
            years_of_experience = int(years_of_experience)
            if years_of_experience < 0 or years_of_experience > 50:
                flash("Years of experience must be between 0 and 50.", "danger")
                return redirect(url_for("teacher_registration"))
        except ValueError:
            flash("Years of experience must be a number.", "danger")
            return redirect(url_for("teacher_registration"))

        # Contact validation (10 digits)
        if not re.match(r"^\d{10}$", contact):
            flash("Contact must be a 10-digit number.", "danger")
            return redirect(url_for("teacher_registration"))

        # Email uniqueness
        existing_teacher = Teacher.query.filter_by(email=email).first()
        if existing_teacher:
            flash("Email already registered.", "danger")
            return redirect(url_for("teacher_registration"))

        # ----------------- Handle Photo -----------------
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config["UPLOAD_FOLDER_PHOTOS"], filename))
        else:
            filename = "default.jpg"

        # ----------------- Save Teacher -----------------
        hashed_password = generate_password_hash(password)
        new_teacher = Teacher(
            name=name,
            email=email,
            password=hashed_password,
            qualifications=qualifications,
            availability=availability,
            years_of_experience=years_of_experience,
            contact=contact,
            place=place,
            photo=filename,
        )
        db.session.add(new_teacher)
        db.session.flush()
        # Assign courses
        if course_id:
            course = Course.query.get(int(course_id))
            if course:
                new_teacher.courses.append(course)
        if second_course_id:
            second_course = Course.query.get(int(second_course_id))
            if second_course:
                new_teacher.courses.append(second_course)

        db.session.commit()
        flash("Teacher registered successfully.", "success")
        return redirect(url_for("login"))

    return render_template("teacher_register.html", courses=courses)


@app.route("/admin/teachers")
@admin_required
def admin_teachers():  # admin view teachers
    search = request.args.get("search")
    course_id = request.args.get("course_id")

    courses = Course.query.all()
    query = Teacher.query

    if search:
        query = query.filter(
            (Teacher.name.ilike(f"%{search}%")) | (Teacher.email.ilike(f"%{search}%"))
        )
    if course_id:
        query = (
            query.join(Teacher.courses).filter(Course.id == int(course_id)).distinct()
        )
    teachers = query.all()
    return render_template("admin_teachers.html", teachers=teachers, courses=courses)

# for admin
@app.route("/admin/remove_teacher/<int:teacher_id>")
@admin_required
def remove_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    try:
        db.session.delete(teacher)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    return redirect(url_for("admin_teachers"))


# login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        student = Student.query.filter_by(email=email).first()
        if student and check_password_hash(student.password, password):
            session["student_id"] = student.id
            return redirect(url_for("student_dashboard"))

        teacher = Teacher.query.filter_by(email=email).first()
        if teacher and check_password_hash(teacher.password, password):
            session["teacher_id"] = teacher.id
            return redirect(url_for("teacher_dashboard"))

        return render_template("invalid_login.html")

    return render_template("login.html")


# invalid
@app.route("/invalid_login")
def invalid_login():
    return render_template("invalid_login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# Dashboard
@app.route("/teacher_dashboard")
def teacher_dashboard():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get(teacher_id)
    students = Student.query.all()
    current_date = datetime.now().strftime("%B %d, %Y")
    created_exams = Exam.query.filter_by(teacher_id=teacher_id).all()
    return render_template(
        "teacher_dashboard.html",
        current_date=current_date,
        datetime=datetime,
        teacher=teacher,
        students=students,
        created_exams=created_exams,
    )


@app.route("/student_dashboard")
def student_dashboard():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)
    course_ids = [c.id for c in student.courses]

    current_date = datetime.now().strftime("%B %d, %Y")

    # Attendance
    records = (
        Attendance.query.filter_by(student_id=student_id)
        .order_by(Attendance.date)
        .all()
    )
    total_days = len(records)
    percent_attendance = (
        round(attendance_percentage(student_id), 2) if total_days else 0
    )

    # Progress
    completed_materials = Progress.query.filter(
        Progress.student_id == student_id,
        Progress.material_id.isnot(None),
        Progress.completed.is_(True),
    ).count()

    completed_recorded = Progress.query.filter(
        Progress.student_id == student_id,
        Progress.recorded_class_id.isnot(None),
        Progress.completed.is_(True),
    ).count()

    completed_live = Progress.query.filter(
        Progress.student_id == student_id,
        Progress.live_class_id.isnot(None),
        Progress.completed.is_(True),
    ).count()

    completed_exams = Progress.query.filter(
        Progress.student_id == student_id,
        Progress.exam_id.isnot(None),
        Progress.completed.is_(True),
    ).count()

    completed_items = (
        completed_materials + completed_recorded + completed_live + completed_exams
    )

    total_items = (
        StudyMaterial.query.filter(StudyMaterial.course_id.in_(course_ids)).count()
        + RecordedClass.query.filter(RecordedClass.course_id.in_(course_ids)).count()
        + LiveClass.query.filter(LiveClass.course_id.in_(course_ids)).count()
        + Exam.query.filter(Exam.course_id.in_(course_ids)).count()
    )

    progress = int((completed_items / total_items) * 100) if total_items else 0

    # Exams
    assigned_exams = (
        Exam.query.filter(Exam.course_id.in_(course_ids))
        .order_by(Exam.created_at.desc())
        .all()
    )
    exam_count = len(assigned_exams)

    attempts = ExamAttempt.query.filter_by(student_id=student_id).all()
    exams_attended = list({a.exam.id: a.exam for a in attempts}.values())
    attended_exam_ids = {a.exam_id for a in attempts}

    # Classes and Materials
    recorded_classes = RecordedClass.query.filter(
        RecordedClass.course_id.in_(course_ids)
    ).all()
    live_classes = LiveClass.query.filter(LiveClass.course_id.in_(course_ids)).all()
    materials = StudyMaterial.query.filter(
        StudyMaterial.course_id.in_(course_ids)
    ).all()
    exams = assigned_exams

    return render_template(
        "student_dashboard.html",
        current_date=current_date,
        student=student,
        attendance=records,
        percent_attendance=percent_attendance,
        total_days=total_days,
        progress=progress,
        completed_items=completed_items,
        total_items=total_items,
        exam_count=exam_count,
        exams_attended=exams_attended,
        recorded_classes=recorded_classes,
        live_classes=live_classes,
        materials=materials,
        exams=exams,
        attended_exam_ids=attended_exam_ids,
    )


@app.route("/student_profile")
def student_profile():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)

    teachers = set()
    for course in student.courses:
        for teacher in course.teachers:
            teachers.add(teacher)

    return render_template(
        "student_profile.html", student=student, teachers=list(teachers)
    )


@app.route("/teacher_profile")
def teacher_profile():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))
    teacher = Teacher.query.get(teacher_id)

    return render_template("teacher_profile.html", teacher=teacher)


@app.route("/admin/teacher_profile/<int:teacher_id>")
def admin_teacher_profile(teacher_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)
    return render_template("teacher_profile.html", teacher=teacher)


@app.route("/teacher_edit_profile", methods=["GET", "POST"])
def teacher_edit_profile():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)
    courses = Course.query.all()

    if request.method == "POST":

        # -------- Photo Upload --------
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join("static/photos", filename))
            teacher.photo = filename

        # -------- Text Fields --------
        teacher.name = request.form["name"]
        teacher.email = request.form["email"]
        teacher.password = request.form["password"]
        teacher.qualifications = request.form["qualifications"]
        teacher.availability = request.form["availability"]
        teacher.years_of_experience = request.form["years_of_experience"]
        teacher.contact = request.form["contact"]
        teacher.place = request.form["place"]

        # -------- SUBJECT DROPDOWN LOGIC --------
        teacher.courses.clear()  # remove old subjects

        # primary subject (required)
        course_id = request.form.get("course_id")
        if course_id:
            course = Course.query.get(course_id)
            teacher.courses.append(course)

        # second subject (optional)
        second_course_id = request.form.get("second_course_id")
        if second_course_id:
            second_course = Course.query.get(second_course_id)
            teacher.courses.append(second_course)

        db.session.commit()
        return redirect(url_for("teacher_profile"))

    return render_template(
        "teacher_edit_profile.html", teacher=teacher, courses=courses
    )


@app.route("/student_edit_profile", methods=["GET", "POST"])
def student_edit_profile():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get(student_id)
    courses = Course.query.all()

    if request.method == "POST":
        # Update text fields
        student.name = request.form.get("name")
        student.email = request.form.get("email")
        student.age = request.form.get("age")
        student.grade = request.form.get("grade")

        course_ids = request.form.getlist("course_ids")
        student.courses.clear()
        for cid in course_ids:
            course = Course.query.get(int(cid))
            if course:
                student.courses.append(course)

        db.session.commit()
        return redirect(url_for("student_profile"))

    courses = Course.query.all()
    return render_template(
        "student_edit_profile.html", student=student, courses=courses
    )


@app.route("/teacher/students")
def teacher_students():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)
    # ✅ Filter students directly by assigned teacher
    students = set()
    for course in teacher.courses:
        for student in course.students:
            students.add(student)

    return render_template("teacher_student.html", students=list(students))


@app.route("/teacher/attendance", methods=["GET", "POST"])
def mark_attendance():
    teacher_id = session.get("teacher_id")

    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)

    students = set()
    for course in teacher.courses:
        for student in course.students:
            students.add(student)

    students = list(students)

    formatted_date = date.today().strftime("%d-%m-%Y")

    if request.method == "POST":
        for student in students:
            status = request.form.get(f"status_{student.id}")
            if status:
                new_attendance = Attendance(
                    student_id=student.id,
                    teacher_id=teacher_id,
                    status=status,
                    date=date.today(),
                )
                db.session.add(new_attendance)

        db.session.commit()
        return render_template(
            "attendence.html", students=students, today=formatted_date, success=True
        )

    return render_template(
        "attendence.html", students=students, today=formatted_date, success=False
    )


@app.route("/manage_class")
def manage_class():
    # You can fetch recorded and live classes from DB
    recorded_classes = RecordedClass.query.filter_by(
        teacher_id=session["teacher_id"]
    ).all()
    live_classes = LiveClass.query.filter_by(teacher_id=session["teacher_id"]).all()
    return render_template(
        "manage_class.html",
        recorded_classes=recorded_classes,
        live_classes=live_classes,
    )


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/teacher/upload_recorded_class", methods=["GET", "POST"])
def upload_recorded_class():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)

    # Optional: restrict courses to this teacher only
    courses = teacher.courses

    if request.method == "POST":
        title = request.form.get("title")
        date_str = request.form.get("date")
        video = request.files.get("video")
        course_id = request.form.get("course_id")

        if not title or not course_id:
            flash("Title and course are required", "danger")
            return redirect(url_for("upload_recorded_class"))

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format", "danger")
            return redirect(url_for("upload_recorded_class"))

        if not video or video.filename == "":
            flash("Please upload a video!", "danger")
            return redirect(url_for("upload_recorded_class"))

        filename = secure_filename(video.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER_VIDEOS"], filename)
        video.save(save_path)

        new_recorded = RecordedClass(
            teacher_id=teacher.id,
            course_id=course_id,
            title=title,
            date=date_obj,
            filename=filename,
        )
        db.session.add(new_recorded)
        db.session.commit()
        return redirect(url_for("manage_class"))

    return render_template(
        "upload_recorded_class.html", teacher=teacher, courses=courses
    )


@app.route("/teacher/upload_live_class", methods=["GET", "POST"])
def upload_live_class():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        flash("Login required!", "danger")
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)
    courses = teacher.courses  # Only show teacher's courses

    if request.method == "POST":
        title = request.form.get("title")
        date_str = request.form.get("date")
        time_str = request.form.get("time")
        platform = request.form.get("platform")
        link = request.form.get("link")
        course_id = request.form.get("course_id")

        # Basic validation
        if not all([title, date_str, time_str, platform, link, course_id]):
            return redirect(url_for("upload_live_class"))

        try:
            course_id = int(course_id)
            course = Course.query.get(course_id)
            if not course or course not in teacher.courses:
                flash("Invalid course selection!", "danger")
                return redirect(url_for("upload_live_class"))

            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            time_obj = datetime.strptime(time_str, "%H:%M").time()
        except (ValueError, TypeError):
            flash("Invalid date, time, or course selection!", "danger")
            return redirect(url_for("upload_live_class"))

        new_class = LiveClass(
            teacher_id=teacher.id,
            course_id=course_id,
            title=title,
            date=date_obj,
            time=time_obj,
            platform=platform,
            link=link,
        )

        db.session.add(new_class)
        db.session.commit()
        return redirect(url_for("manage_class"))

    return render_template("upload_live_class.html", teacher=teacher, courses=courses)


@app.route("/teacher/delete_recorded_class/<int:id>", methods=["GET"])
def delete_recorded_class(id):
    cls = RecordedClass.query.get_or_404(id)
    # Delete video file from storage
    file_path = os.path.join(app.config["UPLOAD_FOLDER_VIDEOS"], cls.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(cls)
    db.session.commit()

    return redirect(url_for("manage_class"))


@app.route("/edit_recorded_class/<int:id>", methods=["GET", "POST"])
def edit_recorded_class(id):
    cls = RecordedClass.query.get_or_404(id)

    if request.method == "POST":
        cls.title = request.form["title"]
        cls.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        cls.filename = request.form["filename"]

        db.session.commit()
        return redirect(url_for("manage_class"))

    return render_template("edit_recorded_cls.html", cls=cls)


@app.route("/edit_live-class/<int:id>", methods=["GET", "POST"])
def edit_live_class(id):
    cls = LiveClass.query.get_or_404(id)

    if request.method == "POST":
        cls.title = request.form["title"]
        cls.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()

        time_str = request.form["time"]
        if len(time_str) == 5:
            cls.time = datetime.strptime(time_str, "%H:%M").time()
        else:
            cls.time = datetime.strptime(time_str, "%H:%M:%S").time()

        cls.platform = request.form["platform"]
        cls.link = request.form["link"]

        db.session.commit()
        return redirect(url_for("manage_class"))

    return render_template("edit_live_cls.html", cls=cls)


@app.route("/delete_live_class/<int:id>", methods=["GET"])
def delete_live_class(id):
    cls = LiveClass.query.get_or_404(id)
    db.session.delete(cls)
    db.session.commit()
    return redirect(url_for("manage_class"))


def allowed_material(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_MATERIALS


@app.route("/upload_material", methods=["GET", "POST"])
def upload_material():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get_or_404(teacher_id)
    courses = teacher.courses

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        file = request.files["file"]
        course_id = request.form.get("course_id")

        if file and allowed_material(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["MATERIAL_FOLDER"], filename))

            material = StudyMaterial(
                course_id=course_id,
                teacher_id=teacher_id,
                title=title,
                description=description,
                filename=filename,
                upload_date=date.today(),
            )
            db.session.add(material)
            db.session.commit()
            return redirect(url_for("manage_materials"))
    return render_template("upload_materials.html", courses=courses)


@app.route("/manage_materials")
def manage_materials():
    teacher_id = session.get("teacher_id")
    materials = StudyMaterial.query.filter_by(teacher_id=teacher_id).all()
    return render_template("manage_materials.html", materials=materials)


@app.route("/edit_material/<int:id>", methods=["GET", "POST"])
def edit_material(id):
    material = StudyMaterial.query.get_or_404(id)

    if request.method == "POST":
        material.title = request.form["title"]
        material.description = request.form["description"]
        db.session.commit()
        return redirect(url_for("manage_materials"))

    return render_template("edit_material.html", material=material)


@app.route("/delete_material/<int:id>")
def delete_material(id):
    material = StudyMaterial.query.get_or_404(id)
    db.session.delete(material)
    db.session.commit()
    return redirect(url_for("manage_materials"))


@app.route("/student/view_material_student/<int:course_id>")
def view_material_student(course_id):
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    # Fetch all materials for this course
    materials = StudyMaterial.query.filter_by(course_id=course_id).all()
    if not materials:
        return redirect(url_for("student_dashboard"))

    # Fetch progress for this student for all materials in this course
    progress_dict = {
        p.material_id: p
        for p in Progress.query.filter(
            Progress.student_id == student_id,
            Progress.material_id.in_([m.id for m in materials]),
        ).all()
    }

    return render_template(
        "view_material_student.html", materials=materials, progress_dict=progress_dict
    )


@app.route("/student_progress", methods=["GET", "POST"])
def student_progress():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)

    # Student-related content
    materials = StudyMaterial.query.all()
    course_ids = [c.id for c in student.courses]

    recorded_classes = RecordedClass.query.filter(
        RecordedClass.course_id.in_(course_ids)
    ).all()

    live_classes = LiveClass.query.filter(LiveClass.course_id.in_(course_ids)).all()

    exams = Exam.query.filter(Exam.course_id.in_(course_ids)).all()

    # Fetch all progress records once
    progress_records = Progress.query.filter_by(student_id=student_id).all()

    material_progress = {
        p.material_id: p.completed for p in progress_records if p.material_id
    }
    recorded_progress = {
        p.recorded_class_id: p.completed
        for p in progress_records
        if p.recorded_class_id
    }
    live_progress = {
        p.live_class_id: p.completed for p in progress_records if p.live_class_id
    }
    exam_progress = {p.exam_id: p.completed for p in progress_records if p.exam_id}

    # ---------- POST: Save progress ----------
    if request.method == "POST":

        # Materials
        for m in materials:
            completed = request.form.get(f"material_{m.id}") == "on"
            progress = Progress.query.filter_by(
                student_id=student_id, material_id=m.id
            ).first()

            if not progress:
                db.session.add(
                    Progress(
                        student_id=student_id, material_id=m.id, completed=completed
                    )
                )
            else:
                progress.completed = completed

        # Recorded Classes
        for rc in recorded_classes:
            completed = request.form.get(f"recorded_{rc.id}") == "on"
            progress = Progress.query.filter_by(
                student_id=student_id, recorded_class_id=rc.id
            ).first()

            if not progress:
                db.session.add(
                    Progress(
                        student_id=student_id,
                        recorded_class_id=rc.id,
                        completed=completed,
                    )
                )
            else:
                progress.completed = completed

        # Live Classes
        for lc in live_classes:
            completed = request.form.get(f"live_{lc.id}") == "on"
            progress = Progress.query.filter_by(
                student_id=student_id, live_class_id=lc.id
            ).first()

            if not progress:
                db.session.add(
                    Progress(
                        student_id=student_id, live_class_id=lc.id, completed=completed
                    )
                )
            else:
                progress.completed = completed

        # Exams ✅ FIXED
        for ex in exams:
            completed = request.form.get(f"exam_{ex.id}") == "on"
            progress = Progress.query.filter_by(
                student_id=student_id, exam_id=ex.id
            ).first()

            if not progress:
                db.session.add(
                    Progress(student_id=student_id, exam_id=ex.id, completed=completed)
                )
            else:
                progress.completed = completed

        db.session.commit()
        return redirect(url_for("student_progress"))

    # ---------- Progress Percentage ----------
    total_items = (
        len(materials) + len(recorded_classes) + len(live_classes) + len(exams)
    )

    completed_count = sum(1 for p in progress_records if p.completed)

    progress_percent = int((completed_count / total_items) * 100) if total_items else 0

    return render_template(
        "student_progress.html",
        student=student,
        progress=progress_percent,
        total_items=total_items,
        materials=materials,
        recorded_classes=recorded_classes,
        live_classes=live_classes,
        exams=exams,
        material_progress=material_progress,
        recorded_progress=recorded_progress,
        live_progress=live_progress,
        exam_progress=exam_progress,
    )


@app.route("/update_progress", methods=["POST"])
def update_progress():
    student_id = session.get("student_id")
    if not student_id:
        return "", 401

    item_type = request.form.get("type")
    item_id = request.form.get("id")
    completed = request.form.get("completed") == "true"

    progress = None

    # Fetch existing progress
    if item_type == "material":
        progress = Progress.query.filter_by(
            student_id=student_id, material_id=item_id
        ).first()
    elif item_type == "recorded":
        progress = Progress.query.filter_by(
            student_id=student_id, recorded_class_id=item_id
        ).first()
    elif item_type == "live":
        progress = Progress.query.filter_by(
            student_id=student_id, live_class_id=item_id
        ).first()
    elif item_type == "exam":
        progress = Progress.query.filter_by(
            student_id=student_id, exam_id=item_id
        ).first()

    # Create if not exists
    if not progress:
        progress = Progress(student_id=student_id)

        if item_type == "material":
            progress.material_id = item_id
        elif item_type == "recorded":
            progress.recorded_class_id = item_id
        elif item_type == "live":
            progress.live_class_id = item_id
        elif item_type == "exam":
            progress.exam_id = item_id

        db.session.add(progress)

    progress.completed = completed
    progress.completion_date = datetime.utcnow() if completed else None

    db.session.commit()
    return "", 204


@app.route("/student/view_classes")
def student_view_classes():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)
    course_ids = [c.id for c in student.courses]

    recorded_classes = RecordedClass.query.filter(
        RecordedClass.course_id.in_(course_ids)
    ).all()

    live_classes = LiveClass.query.filter(LiveClass.course_id.in_(course_ids)).all()

    progresses = Progress.query.filter_by(student_id=student_id).all()

    # ✅ Completed status
    recorded_progress = {}
    live_progress = {}
    material_progress = {}

    # ✅ Completion dates
    recorded_dates = {}
    live_dates = {}
    material_dates = {}

    for p in progresses:
        if p.recorded_class_id:
            recorded_progress[p.recorded_class_id] = p.completed
            recorded_dates[p.recorded_class_id] = p.completion_date

        if p.live_class_id:
            live_progress[p.live_class_id] = p.completed
            live_dates[p.live_class_id] = p.completion_date

        if p.material_id:
            material_progress[p.material_id] = p.completed
            material_dates[p.material_id] = p.completion_date

    return render_template(
        "student_classes.html",
        student=student,
        recorded_classes=recorded_classes,
        live_classes=live_classes,
        recorded_progress=recorded_progress,
        recorded_dates=recorded_dates,
        live_progress=live_progress,
        live_dates=live_dates,
        material_progress=material_progress,
        material_dates=material_dates,
    )


@app.route("/student/attendance")
def view_attendance():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    records = (
        Attendance.query.filter_by(student_id=student_id)
        .order_by(Attendance.date)
        .all()
    )

    if not records:
        return render_template("student_attendance.html", records=[], percentage=0)

    # Prepare data for template
    attendance_list = []
    present_count = 0

    for record in records:
        attendance_list.append(
            {"date": record.date.strftime("%d-%m-%Y"), "status": record.status}
        )
        if record.status.lower() == "present":
            present_count += 1

    total_days = len(records)
    attendance_percentage = (present_count / total_days) * 100

    return render_template(
        "student_attendance.html",
        records=attendance_list,
        percentage=attendance_percentage,
    )


def attendance_percentage(student_id):
    records = Attendance.query.filter_by(student_id=student_id).all()
    total_days = len(records)
    if not records:
        return 0

    present_count = sum(1 for r in records if r.status.lower() == "present")
    return (present_count / len(records)) * 100

@app.route("/admin/add_course", methods=["GET", "POST"])
def admin_add_course():
    courses = Course.query.all()

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        start_date_str = request.form.get("start_date")

        start_date = (
            datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if start_date_str
            else None
        )

        # Validation: Course name required
        if not name:
            flash("Course name is required", "danger")
            return redirect(url_for("admin_add_course"))

        # Validation: Duplicate course name
        if Course.query.filter_by(name=name).first():
            flash("Course already exists", "warning")
            return redirect(url_for("admin_add_course"))
        # Create course
        new_course = Course(
            name=name,
            description=description,
            start_date=start_date
        )
        db.session.add(new_course)
        db.session.commit()
        flash("Course added successfully", "success")

        return redirect(url_for("admin_add_course"))

    return render_template("admin_add_course.html", courses=courses)



@app.route("/courses")
def courses():
    courses = Course.query.all()
    return render_template("courses.html", courses=courses)


@app.route("/student_view_course")
def student_view_course():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))
    student = Student.query.get(student_id)
    if not student.course_id:
        return redirect(url_for("student_dashboard"))
    courses = []
    if student.course_id:
        course = Course.query.get(student.course_id)
        if course:
            courses.append(course)

    return render_template("student_view_course.html", student=student, courses=courses)


@app.route("/enroll_course")
def enroll_course():
    course_name = session.get("course_name")
    teacher_name = session.get("teacher_name")
    course_description = session.get("course_description")

    return render_template(
        "enroll_sucess.html",
        course_name=course_name,
        teacher_name=teacher_name,
        course_description=course_description,
    )


@app.route("/admin/view_course")
def view_course():
    courses = Course.query.all()
    return render_template("view_course.html", courses=courses)


@app.route("/admin/delete_course/<int:id>", methods=["GET", "POST"])
def delete_course(id):
    course = Course.query.get_or_404(id)

    if request.method == "POST":
        # Save deleted data to session for undo
        session["deleted_course"] = {
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "teacher_ids": [
                teacher.id for teacher in course.teachers
            ],  # store teacher IDs
        }

        # Delete the course from database
        db.session.delete(course)
        db.session.commit()

        flash("Course deleted successfully.", "success")
        return redirect(url_for("view_course"))

    return render_template("admin_delete_course.html", course=course)


@app.route("/admin/undo_delete_course", methods=["POST"])
def undo_delete_course():
    data = session.get("deleted_course")

    if data:
        # Recreate the course
        course = Course(name=data["name"], description=data["description"])

        # Restore teachers (many-to-many)
        course.teachers = Teacher.query.filter(
            Teacher.id.in_(data["teacher_ids"])
        ).all()

        db.session.add(course)
        db.session.commit()

        # Remove from session
        session.pop("deleted_course", None)

        flash("Course restored successfully.", "success")
    else:
        flash(" No course to restore.", "warning")

    return redirect(url_for("view_course"))


@app.route("/edit_course/<int:id>", methods=["GET", "POST"])
def edit_course(id):
    course = Course.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")

        if not name:
            return render_template("admin_edit_course.html", course=course)

        course.name = name
        course.description = description
        db.session.commit()
        return redirect(url_for("view_course"))
    return render_template("admin_edit_course.html", course=course)


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        email = request.form.get("email")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not email or not new_password or not confirm_password:
            flash("All fields are required", "danger")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("change_password"))

        # Check in all user tables
        user = (
            Student.query.filter_by(email=email).first()
            or Teacher.query.filter_by(email=email).first()
        )

        if not user:
            flash("No user found with this email", "danger")
            return redirect(url_for("change_password"))

        # Update password
        user.password = generate_password_hash(new_password)
        db.session.commit()

        flash("Password updated successfully!", "success")
        return redirect(url_for("login"))

    return render_template("change_password.html")


@app.route("/student/enrolled_courses")
def enrolled_courses():
    student_id = session.get("student_id")
    if not student_id:
        # Redirect to login if not logged in
        return redirect(url_for("login"))

    # Fetch the student
    student = Student.query.get(student_id)
    if not student:
        return "Student not found", 404

    # Get all enrolled courses
    courses = student.courses  # Assuming many-to-many relationship via student.courses

    return render_template("enrolled_courses.html", student=student, courses=courses)


@app.route("/teacher/student_progress_view/<int:student_id>")
def teacher_student_progress_view(student_id):
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("teacher_login"))

    teacher = Teacher.query.get_or_404(teacher_id)

    # Teacher's course IDs
    teacher_course_ids = [course.id for course in teacher.courses]

    if not teacher_course_ids:
        return redirect(url_for("teacher_dashboard"))

    # VALIDATE student belongs to teacher's courses
    student = (
        Student.query.join(Student.courses)
        .filter(Student.id == student_id, Course.id.in_(teacher_course_ids))
        .first_or_404()
    )

    # Fetch progress ONLY from teacher's courses
    progress = (
        Progress.query.filter(
            Progress.student_id == student.id,
            Progress.course_id.in_(teacher_course_ids),
        )
        .options(
            joinedload(Progress.material),
            joinedload(Progress.recorded_class),
            joinedload(Progress.live_class),
            joinedload(Progress.exam),
        )
        .all()
    )
    total_items = len(progress)
    completed_items = sum(1 for p in progress if p.completed)
    pending_items = total_items - completed_items
    progress_percent = int((completed_items / total_items) * 100) if total_items else 0

    return render_template(
        "teacher_student_progress_view.html",
        student=student,
        progress=progress,
        total_items=total_items,
        completed_items=completed_items,
        pending_items=pending_items,
        progress_percent=progress_percent,
    )


@app.route("/teacher/teacher_student_progress_table")
def teacher_student_progress_table():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("teacher_login"))

    teacher = Teacher.query.get_or_404(teacher_id)

    # Teacher's course IDs
    teacher_course_ids = [course.id for course in teacher.courses]

    if not teacher_course_ids:
        return render_template(
            "teacher_student_progress_table.html", student_progress=[]
        )

    # Students enrolled in teacher's courses ONLY
    students = (
        Student.query.join(Student.courses)
        .filter(Course.id.in_(teacher_course_ids))
        .distinct()
        .all()
    )

    student_progress = []

    for student in students:
        progress_records = Progress.query.filter(
            Progress.student_id == student.id,
            Progress.course_id.in_(teacher_course_ids),
        ).all()

        total_items = len(progress_records)
        completed_items = sum(1 for p in progress_records if p.completed)

        progress_percent = (
            int((completed_items / total_items) * 100) if total_items else 0
        )

        student_progress.append(
            {"id": student.id, "name": student.name, "progress": progress_percent}
        )

    return render_template(
        "teacher_student_progress_table.html", student_progress=student_progress
    )


@app.route("/create_exam", methods=["GET", "POST"])
def create_exam():
    teacher_id = session.get("teacher_id")
    if not teacher_id:
        return redirect(url_for("login"))

    teacher = Teacher.query.get(teacher_id)

    if request.method == "POST":
        title = request.form["title"]
        course_id = request.form["course_id"]

        exam = Exam(
            title=title,
            teacher_id=teacher_id,
            course_id=course_id,
            created_at=datetime.now(),
        )

        db.session.add(exam)
        db.session.commit()

        questions = request.form.getlist("question")
        options_a = request.form.getlist("option_a")
        options_b = request.form.getlist("option_b")
        options_c = request.form.getlist("option_c")
        options_d = request.form.getlist("option_d")
        correct = request.form.getlist("correct")

        for i in range(len(questions)):
            if questions[i].strip():
                q = Question(
                    exam_id=exam.id,
                    question_text=questions[i],
                    option_a=options_a[i],
                    option_b=options_b[i],
                    option_c=options_c[i],
                    option_d=options_d[i],
                    correct_option=correct[i],
                )
                db.session.add(q)

        db.session.commit()
        return redirect(url_for("teacher_dashboard"))
    return render_template("teacher_create_exam.html", teacher=teacher)


@app.route("/student/exams")
def student_exams():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)
    course_ids = [c.id for c in student.courses]

    # ✅ Only exams assigned to student's courses
    exams = (
        Exam.query.filter(Exam.course_id.in_(course_ids))
        .order_by(Exam.created_at.desc())
        .all()
    )

    attempts = ExamAttempt.query.filter_by(student_id=student_id).all()
    attended_exam_ids = {a.exam_id for a in attempts}
    attempt_dates = {a.exam_id: a.attended_date for a in attempts if a.attended_date}

    results = ExamResult.query.filter_by(student_id=student_id).all()
    result_exam_ids = {r.exam_id for r in results}

    return render_template(
        "student_exam_list.html",
        exams=exams,
        attended_exam_ids=attended_exam_ids,
        attempt_dates=attempt_dates,
        result_exam_ids=result_exam_ids,
    )


@app.route("/student/attend_exam/<int:exam_id>", methods=["GET", "POST"])
def attend_exam(exam_id):
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).all()

    attempt = ExamAttempt.query.filter_by(
        student_id=student_id, exam_id=exam_id
    ).first()

    if request.method == "POST":

        StudentAnswer.query.filter_by(student_id=student_id).filter(
            StudentAnswer.question_id.in_([q.id for q in questions])
        ).delete(synchronize_session=False)

        ExamResult.query.filter_by(student_id=student_id, exam_id=exam_id).delete()

        if not attempt:
            attempt = ExamAttempt(
                student_id=student_id,
                exam_id=exam_id,
                course_id=exam.course_id,  # ✅ REQUIRED
                attended_date=datetime.now(),
            )
            db.session.add(attempt)
        else:
            attempt.attended_date = datetime.now()

        db.session.commit()
        return redirect(url_for("student_exams"))

    return render_template(
        "student_attend_exam.html",
        exam=exam,
        questions=questions,
        attended_date=attempt.attended_date if attempt else None,
    )


@app.route("/submit_exam/<int:exam_id>", methods=["POST"])
def submit_exam(exam_id):
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("student_login"))

    # Fetch exam and student
    exam = Exam.query.get_or_404(exam_id)
    student = Student.query.get_or_404(student_id)

    # Get submitted answers from form
    submitted_answers = request.form  # Example: {'1': 'A', '2': 'C'}

    # Remove any previous answers and results for this exam
    StudentAnswer.query.filter_by(student_id=student_id, exam_id=exam_id).delete()
    ExamResult.query.filter_by(student_id=student_id, exam_id=exam_id).delete()
    ExamAttempt.query.filter_by(student_id=student_id, exam_id=exam_id).delete()
    db.session.commit()

    # Initialize score
    score = 0
    total_questions = len(exam.questions)

    # Save each student answer
    for question in exam.questions:
        selected_option = submitted_answers.get(str(question.id))
        if not selected_option:
            continue  # Skip unanswered questions

        # Save the answer
        answer = StudentAnswer(
            student_id=student.id,
            exam_id=exam.id,
            question_id=question.id,
            selected_option=selected_option,
        )
        db.session.add(answer)

        # Auto-grade
        if selected_option == question.correct_option:
            score += 1

    # Save ExamResult
    result = ExamResult(
        student_id=student.id,
        exam_id=exam.id,
        score=score,
        total=total_questions,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(result)

    # Save ExamAttempt
    attempt = ExamAttempt(
        student_id=student.id,
        exam_id=exam.id,
        course_id=exam.course_id,
        score=score,
        attended_date=datetime.utcnow(),
    )
    db.session.add(attempt)

    # Commit everything
    db.session.commit()

    flash(
        f"Exam submitted successfully! Your score: {score}/{total_questions}", "success"
    )
    return redirect(url_for("student_dashboard"))


@app.route("/student/exam/<int:exam_id>/result")
def view_exam_result(exam_id):
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    # Fetch exam, result, and attempt
    exam = Exam.query.get_or_404(exam_id)
    result = ExamResult.query.filter_by(student_id=student_id, exam_id=exam_id).first()
    attempt = ExamAttempt.query.filter_by(
        student_id=student_id, exam_id=exam_id
    ).first()

    if not result:
        flash(
            "Exam result not found. Make sure you have submitted the exam.", "warning"
        )
        return redirect(url_for("student_dashboard"))

    # Fetch student answers
    student_answers = StudentAnswer.query.filter_by(
        student_id=student_id, exam_id=exam_id
    ).all()
    answers_dict = {a.question_id: a.selected_option for a in student_answers}

    return render_template(
        "view_exam_result.html",
        exam=exam,
        result=result,
        attempt=attempt,
        student_answers=answers_dict,
    )


@app.route("/created_exams", methods=["GET", "POST"])
def created_exams():
    teacher_id = session.get("teacher_id")
    exams = Exam.query.filter_by(teacher_id=teacher_id).all()
    return render_template("created_exams.html", exams=exams)


@app.route("/admin/student/<int:student_id>/progress")
@admin_required
def admin_student_progress(student_id):

    student = Student.query.get_or_404(student_id)

    progress_records = Progress.query.filter_by(student_id=student.id).all()

    total_items = len(progress_records)
    completed_items = sum(1 for p in progress_records if p.completed)

    progress_percent = (
        int((completed_items / total_items) * 100) if total_items > 0 else 0
    )

    print("DEBUG:", Progress, type(Progress))

    return render_template(
        "admin_student_progress.html",
        student=student,
        progress_records=progress_records,
        progress_percent=progress_percent,
    )


from datetime import datetime


@app.route("/student/feedback", methods=["GET", "POST"])
def student_feedback():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    student = Student.query.get_or_404(student_id)
    courses = student.courses  # enrolled courses

    if request.method == "POST":
        message = request.form.get("message")
        teacher_id = request.form.get("teacher_id")

        if not teacher_id or not message:
            flash("All fields are required", "danger")
            return redirect(url_for("student_feedback"))

        # Validate teacher belongs to student's enrolled courses
        valid_teacher_ids = {
            teacher.id for course in courses for teacher in course.teachers
        }

        if int(teacher_id) not in valid_teacher_ids:
            return redirect(url_for("student_feedback"))

        feedback = Feedback(
            student_id=student_id,
            teacher_id=int(teacher_id),
            message=message.strip(),
            created_at=datetime.utcnow(),
        )
        db.session.add(feedback)
        db.session.commit()
        return redirect(url_for("student_dashboard"))

    return render_template(
        "student_feedback.html",
        courses=courses,
        created_at=datetime.now().strftime("%d %B %Y"),
    )


@app.route("/teacher/feedbacks", methods=["GET", "POST"])
def teacher_feedbacks():
    teacher_id = session.get("teacher_id")

    feedbacks = (
        Feedback.query.filter_by(teacher_id=teacher_id)
        .order_by(Feedback.created_at.desc())
        .all()
    )

    if request.method == "POST":
        feedback_id = request.form.get("feedback_id")
        reply = request.form.get("reply")

        feedback = Feedback.query.get(feedback_id)
        if feedback and reply:
            feedback.reply = reply
            feedback.replied_at = datetime.utcnow()
            db.session.commit()
        return redirect(url_for("teacher_feedbacks"))
    return render_template("teacher_feedbacks.html", feedbacks=feedbacks)


@app.route("/student/my-feedbacks")
def student_my_feedbacks():
    student_id = session.get("student_id")
    feedbacks = Feedback.query.filter_by(student_id=student_id).all()
    return render_template("student_view_reply.html", feedbacks=feedbacks)


@app.route("/admin/material")
@admin_required
def admin_material():
    search = request.args.get("search")
    course_id = request.args.get("course_id")
    courses = Course.query.all()
    query = StudyMaterial.query

    if search:
        query = query.filter(StudyMaterial.title.ilike(f"%{search}%"))

    if course_id:
        query = (
            query.join(StudyMaterial.courses)
            .filter(Course.id == int(course_id))
            .distinct()
        )

    materials = query.all()

    return render_template("admin_material.html", materials=materials, courses=courses)


if __name__ == "__main__":
    app.run()
