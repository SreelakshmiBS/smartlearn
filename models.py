from extensions import db
from datetime import date, datetime

# =========================
# ADMIN
# =========================
class Admin(db.Model):
    __tablename__ = 'admin'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))

# =========================
# ASSOCIATION TABLES
# =========================
student_course = db.Table(
    'student_course',
    db.Column('student_id',db.Integer,db.ForeignKey('student.id', name='fk_student_course_student'),primary_key=True),
    db.Column('course_id',db.Integer,db.ForeignKey('course.id', name='fk_student_course_course'),primary_key=True),
    db.Column('enrolled_on', db.Date, default=date.today))

teacher_course = db.Table(
    'teacher_course',
    db.Column('teacher_id',db.Integer,db.ForeignKey('teacher.id', name='fk_teacher_course_teacher'),primary_key=True),
    db.Column('course_id',db.Integer,db.ForeignKey('course.id', name='fk_teacher_course_course'),primary_key=True))


# =========================
# COURSE
# =========================
class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255))
    start_date = db.Column(db.Date)

    teachers = db.relationship('Teacher', secondary=teacher_course, back_populates='courses')
    students = db.relationship('Student', secondary=student_course, back_populates='courses')
    materials = db.relationship('StudyMaterial', back_populates='course', cascade='all, delete')
    recorded_classes = db.relationship('RecordedClass', back_populates='course', cascade='all, delete')
    live_classes = db.relationship('LiveClass', back_populates='course', cascade='all, delete')
    exams = db.relationship('Exam', back_populates='course', cascade='all, delete')

# =========================
# TEACHER
# =========================
class Teacher(db.Model):
    __tablename__ = 'teacher'

    id = db.Column(db.Integer, primary_key=True)
    photo = db.Column(db.String(200), default='default.jpg')
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100), nullable=False)
    qualifications = db.Column(db.String(200), nullable=False)
    availability = db.Column(db.String(100), nullable=False)
    years_of_experience = db.Column(db.Integer, nullable=False)
    contact = db.Column(db.String(15), nullable=False)
    place = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20),default="Active")

    courses = db.relationship('Course', secondary=teacher_course, back_populates='teachers',cascade='all,delete')
    attendance = db.relationship('Attendance', back_populates='teacher', cascade='all, delete')
    materials = db.relationship('StudyMaterial', back_populates='teacher', cascade='all, delete')
    recorded_classes = db.relationship('RecordedClass', back_populates='teacher', cascade='all, delete')
    live_classes = db.relationship('LiveClass', back_populates='teacher', cascade='all, delete')
    exams = db.relationship('Exam', back_populates='teacher', cascade='all, delete')


# =========================
# STUDENT
# =========================
class Student(db.Model):
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    courses = db.relationship('Course', secondary=student_course, back_populates='students')

    attendance = db.relationship('Attendance', back_populates='student', cascade='all, delete')
    progresses = db.relationship('Progress', back_populates='student', cascade='all, delete')
    answers = db.relationship('StudentAnswer', back_populates='student', cascade='all, delete')
    results = db.relationship('ExamResult', back_populates='student', cascade='all, delete')


# =========================
# ATTENDANCE
# =========================
class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer,db.ForeignKey('student.id', name='fk_attendance_student'),nullable=False)
    teacher_id = db.Column(db.Integer,db.ForeignKey('teacher.id', name='fk_attendance_teacher'),nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)

    student = db.relationship('Student', back_populates='attendance')
    teacher = db.relationship('Teacher', back_populates='attendance')

# =========================
# RECORDED CLASS
# =========================
class RecordedClass(db.Model):
    __tablename__ = 'recorded_class'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer,db.ForeignKey('teacher.id', name='fk_recorded_teacher'),nullable=False)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id', name='fk_recorded_course'),nullable=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    filename = db.Column(db.String(300), nullable=False)

    teacher = db.relationship('Teacher', back_populates='recorded_classes')
    course = db.relationship('Course', back_populates='recorded_classes')
    
# =========================
# LIVE CLASS
# =========================
class LiveClass(db.Model):
    __tablename__ = 'live_class'
    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(db.Integer,db.ForeignKey('teacher.id', name='fk_live_teacher'),nullable=False)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id', name='fk_live_course'),nullable=True)

    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    platform = db.Column(db.String(100))
    link = db.Column(db.String(300), nullable=False)

    teacher = db.relationship('Teacher', back_populates='live_classes')
    course = db.relationship('Course', back_populates='live_classes')

# =========================
# STUDY MATERIAL
# =========================
class StudyMaterial(db.Model):
    __tablename__ = 'studymaterial'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer,db.ForeignKey('teacher.id', name='fk_material_teacher'),nullable=False)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id', name='fk_material_course'),nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(300))
    upload_date = db.Column(db.Date, nullable=False)

    teacher = db.relationship('Teacher', back_populates='materials')
    course = db.relationship('Course', back_populates='materials')

# =========================
# PROGRESS
# =========================
class Progress(db.Model):
    __tablename__ = 'progress'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer,db.ForeignKey('student.id', name='fk_progress_student'),nullable=False)
    material_id = db.Column(db.Integer,db.ForeignKey('studymaterial.id', name='fk_progress_material'),nullable=True)
    recorded_class_id = db.Column(db.Integer,db.ForeignKey('recorded_class.id', name='fk_progress_recorded'),nullable=True)
    live_class_id = db.Column(db.Integer,db.ForeignKey('live_class.id', name='fk_progress_live'),nullable=True)
    exam_id = db.Column(db.Integer,db.ForeignKey('exam.id',name='fk_progress_exam'),nullable =True)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id', name='fk_progress_course'),nullable=True)
    completed = db.Column(db.Boolean, default=False)
    completion_date = db.Column(db.Date)
    
    student = db.relationship('Student', back_populates='progresses')
    material = db.relationship('StudyMaterial', backref='progress_entries')
    recorded_class = db.relationship('RecordedClass', backref='progress_entries')
    live_class = db.relationship('LiveClass', backref='progress_entries')
    exam =db.relationship('Exam',backref='progress_entries')

# =========================
# EXAM
# =========================
class Exam(db.Model):
    __tablename__ = 'exam'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer,db.ForeignKey('teacher.id', name='fk_exam_teacher'),nullable=False)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id', name='fk_exam_course'),nullable=False)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('Teacher', back_populates='exams')
    course = db.relationship('Course', back_populates='exams')
    questions = db.relationship('Question',cascade='all, delete-orphan',back_populates='exam')
    
# =========================
# EXAM ATTEMPT
# =========================
class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempt'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    exam_id = db.Column(db.Integer,db.ForeignKey('exam.id'),nullable=False)
    course_id = db.Column(db.Integer,db.ForeignKey('course.id'),nullable=False)
    score = db.Column(db.Float)
    attended_date = db.Column(db.DateTime)

    student = db.relationship('Student', backref='exam_attempts')
    exam = db.relationship('Exam', backref='attempts')
    course = db.relationship('Course', backref='exam_attempts')

# =========================
# QUESTION
# =========================
class Question(db.Model):
    __tablename__ = 'question'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer,db.ForeignKey('exam.id', name='fk_question_exam'),nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200))
    option_d = db.Column(db.String(200))
    correct_option = db.Column(db.String(1), nullable=False)

    exam = db.relationship('Exam', back_populates='questions')

# =========================
# STUDENT ANSWER
# =========================
class StudentAnswer(db.Model):
    __tablename__ = 'student_answer'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer,db.ForeignKey('student.id', name='fk_answer_student'),nullable=False)
    exam_id = db.Column(db.Integer,db.ForeignKey('exam.id', name='fk_answer_exam'),nullable=False)
    question_id = db.Column(db.Integer,db.ForeignKey('question.id', name='fk_answer_question'),nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)

    student = db.relationship('Student', back_populates='answers')
    
# =========================
# EXAM RESULT
# =========================
class ExamResult(db.Model):
    __tablename__ = 'exam_result'
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer,db.ForeignKey('student.id', name='fk_result_student'))
    exam_id = db.Column(db.Integer,db.ForeignKey('exam.id', name='fk_result_exam'))
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', back_populates='results')
    
# =========================
#FEEDBACK
# =========================
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    teacher_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_at = db.Column(db.DateTime, nullable=True)
    
