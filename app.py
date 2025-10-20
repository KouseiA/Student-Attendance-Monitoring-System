from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
from flask_login import UserMixin
from datetime import date, time, datetime, timedelta
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import abort
import qrcode
from io import BytesIO
from flask import send_file
from datetime import datetime
import csv
from flask import Response
from sqlalchemy import event
from sqlalchemy.engine import Engine
# from flask_migrate import Migrate
import io
from flask import session
from math import ceil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
# Photo upload configuration
app.config['UPLOAD_FOLDER'] = 'static/photos'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# migrate = Migrate(app, db)

# Models will be added here

class Teacher(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    classes = db.relationship('Class', backref='teacher', lazy=True)

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    start_time = db.Column(db.Time, default=time(8, 0), nullable=False)  # Default 8:00 AM
    end_time = db.Column(db.Time, default=time(17, 0), nullable=False)   # Default 5:00 PM
    students = db.relationship('Student', backref='class_', lazy=True)
    attendances = db.relationship('Attendance', backref='class_', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_number = db.Column(db.String(50), unique=True, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=True)
    qr_code_path = db.Column(db.String(200))
    photo_path = db.Column(db.String(200), nullable=True)  # New field for student photos
    attendances = db.relationship('Attendance', backref='student', lazy=True, cascade='all, delete-orphan')

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    scan_time = db.Column(db.Time, default=datetime.now().time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=True)  # Actual arrival time for late students
    status = db.Column(db.String(20), nullable=False)  # Present/Absent/Late/Excused
    late_arrival = db.Column(db.Boolean, default=False, nullable=False)  # Flag for late arrival
    late_minutes = db.Column(db.Integer, default=0, nullable=False)  # Minutes late
    notes = db.Column(db.Text, nullable=True)  # Optional notes for late arrivals
    excuse_request_id = db.Column(db.Integer, db.ForeignKey('excuse_request.id'), nullable=True)  # Link to excuse request

class ExcuseRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    absence_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    excuse_letter_path = db.Column(db.String(200), nullable=True)  # Path to uploaded excuse letter
    status = db.Column(db.String(20), default='Pending', nullable=False)  # Pending/Approved/Disapproved
    submitted_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    teacher_notes = db.Column(db.Text, nullable=True)  # Teacher's notes on the decision
    
    # Relationships
    student = db.relationship('Student', backref='excuse_requests')
    class_ = db.relationship('Class', backref='excuse_requests')
    teacher = db.relationship('Teacher', backref='excuse_requests')
    attendance = db.relationship('Attendance', backref='excuse_request', uselist=False)

# Helper functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def auto_expire_pending_excuses():
    """Automatically mark pending excuse requests as absent after 7 days"""
    from datetime import timedelta
    
    # Calculate the cutoff date (7 days ago)
    cutoff_date = datetime.now() - timedelta(days=7)
    
    # Find all pending excuse requests older than 7 days
    expired_requests = ExcuseRequest.query.filter(
        ExcuseRequest.status == 'Pending',
        ExcuseRequest.submitted_at < cutoff_date
    ).all()
    
    expired_count = 0
    for request in expired_requests:
        # Update excuse request status to expired/disapproved
        request.status = 'Disapproved'
        request.reviewed_at = datetime.now()
        request.teacher_notes = 'Automatically disapproved - no response within 7 days'
        
        # Update corresponding attendance record to Absent
        attendance = Attendance.query.filter_by(
            student_id=request.student_id,
            class_id=request.class_id,
            date=request.absence_date
        ).first()
        
        if attendance:
            attendance.status = 'Absent'
            attendance.notes = f"Excuse expired after 7 days: {request.reason}"
        else:
            # Create new absent attendance record if none exists
            attendance = Attendance(
                student_id=request.student_id,
                class_id=request.class_id,
                teacher_id=request.teacher_id,
                date=request.absence_date,
                scan_time=datetime.now().time(),
                status='Absent',
                excuse_request_id=request.id,
                notes=f"Excuse expired after 7 days: {request.reason}"
            )
            db.session.add(attendance)
        
        expired_count += 1
    
    if expired_count > 0:
        db.session.commit()
        print(f"Auto-expired {expired_count} pending excuse requests older than 7 days")
    
    return expired_count

def save_photo(photo, student_number):
    if photo and allowed_file(photo.filename):
        filename = secure_filename(f"{student_number}.{photo.filename.rsplit('.', 1)[1].lower()}")
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(photo_path)
        return f'static/photos/{filename}'
    return None

def save_excuse_letter(file, student_id, class_id, date_str):
    """Save uploaded excuse letter file"""
    if file and allowed_file(file.filename):
        # Create filename with student_id, class_id, and date for uniqueness
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"excuse_{student_id}_{class_id}_{date_str}.{file_ext}")
        
        # Create excuse_letters directory
        excuse_folder = os.path.join('static', 'excuse_letters')
        os.makedirs(excuse_folder, exist_ok=True)
        
        file_path = os.path.join(excuse_folder, filename)
        file.save(file_path)
        return f'static/excuse_letters/{filename}'
    return None

def calculate_late_arrival(arrival_time, class_start_time):
    """
    Calculate if arrival is late and by how many minutes.
    
    Args:
        arrival_time (time): Time when student arrived
        class_start_time (time): Official class start time from Class model
    
    Returns:
        tuple: (is_late: bool, minutes_late: int)
    """
    if arrival_time <= class_start_time:
        return False, 0
    
    # Convert to datetime for calculation
    today = date.today()
    arrival_dt = datetime.combine(today, arrival_time)
    start_dt = datetime.combine(today, class_start_time)
    
    # Calculate difference in minutes
    diff = arrival_dt - start_dt
    minutes_late = int(diff.total_seconds() / 60)
    
    return True, minutes_late

def calculate_arrival_status(arrival_time, class_start_time):
    """
    Calculate enhanced arrival status with early/on-time/late distinction.
    
    Args:
        arrival_time (time): Time when student arrived
        class_start_time (time): Official class start time from Class model
    
    Returns:
        dict: {
            'status': str,  # 'early', 'on_time', 'late'
            'is_late': bool,
            'minutes_difference': int,  # positive = late, negative = early, 0 = on time
            'display_text': str,  # formatted display text
            'badge_class': str,  # CSS class for styling
            'icon': str  # Font Awesome icon
        }
    """
    # Convert to datetime for calculation
    today = date.today()
    arrival_dt = datetime.combine(today, arrival_time)
    start_dt = datetime.combine(today, class_start_time)
    
    # Calculate difference in minutes
    diff = arrival_dt - start_dt
    minutes_difference = int(diff.total_seconds() / 60)
    
    if minutes_difference > 0:
        # Late arrival
        hours = minutes_difference // 60
        mins = minutes_difference % 60
        if hours > 0:
            display_text = f"{hours}h {mins}m late" if mins > 0 else f"{hours}h late"
        else:
            display_text = f"{mins} min late"
        
        return {
            'status': 'late',
            'is_late': True,
            'minutes_difference': minutes_difference,
            'display_text': display_text,
            'badge_class': 'badge bg-warning text-dark',
            'icon': 'fas fa-clock'
        }
    elif minutes_difference < 0:
        # Early arrival
        early_minutes = abs(minutes_difference)
        hours = early_minutes // 60
        mins = early_minutes % 60
        if hours > 0:
            display_text = f"{hours}h {mins}m early" if mins > 0 else f"{hours}h early"
        else:
            display_text = f"{mins} min early"
        
        return {
            'status': 'early',
            'is_late': False,
            'minutes_difference': minutes_difference,
            'display_text': display_text,
            'badge_class': 'badge bg-success',
            'icon': 'fas fa-check-circle'
        }
    else:
        # Exactly on time
        return {
            'status': 'on_time',
            'is_late': False,
            'minutes_difference': 0,
            'display_text': 'On time',
            'badge_class': 'badge bg-primary',
            'icon': 'fas fa-clock'
        }

def is_class_in_session(current_time, class_start_time, class_end_time):
    """
    Check if class is currently in session.
    
    Args:
        current_time (time): Current time
        class_start_time (time): Class start time
        class_end_time (time): Class end time
    
    Returns:
        bool: True if class is in session, False otherwise
    """
    return class_start_time <= current_time <= class_end_time

def auto_mark_absent_students(class_id, attendance_date=None):
    """
    Automatically mark students as absent for a class that has ended.
    
    Args:
        class_id (int): ID of the class
        attendance_date (date): Date to mark attendance for (defaults to today)
    
    Returns:
        int: Number of students marked as absent
    """
    from datetime import datetime, date
    
    # Use today's date if none provided
    if attendance_date is None:
        attendance_date = date.today()
    
    # Get the class
    class_ = Class.query.get(class_id)
    if not class_:
        return 0
    
    # Check if class has ended
    current_time = datetime.now().time()
    if not class_.end_time or current_time < class_.end_time:
        # Class hasn't ended yet, don't auto-mark
        return 0
    
    # Get all students
    all_students = Student.query.all()
    
    # Get students who already have attendance records for this class/date
    existing_attendance = Attendance.query.filter_by(
        class_id=class_id,
        date=attendance_date
    ).all()
    
    # Create a set of student IDs who already have attendance records
    attended_student_ids = {record.student_id for record in existing_attendance}
    
    # Find students who haven't attended
    absent_students = [student for student in all_students 
                      if student.id not in attended_student_ids]
    
    # Mark absent students
    absent_count = 0
    for student in absent_students:
        # Create absent attendance record
        attendance = Attendance(
            student_id=student.id,
            class_id=class_id,
            teacher_id=class_.teacher_id,
            date=attendance_date,
            scan_time=class_.end_time,  # Use class end time as scan time
            arrival_time=None,  # No arrival time for absent students
            status='Absent',
            late_arrival=False,
            late_minutes=0,
            notes='Auto-marked absent - did not attend class'
        )
        db.session.add(attendance)
        absent_count += 1
    
    # Commit all changes at once
    if absent_count > 0:
        db.session.commit()
    
    return absent_count

@app.context_processor
def utility_processor():
    def get_class_status(class_start_time, class_end_time):
        """Get current status of a class based on time"""
        from datetime import datetime
        current_time = datetime.now().time()
        
        if current_time < class_start_time:
            return 'upcoming'
        elif class_start_time <= current_time <= class_end_time:
            return 'in_session'
        else:
            return 'ended'
    
    def format_duration(start_time, end_time):
        """Calculate and format class duration"""
        if not start_time or not end_time:
            return "N/A"
        
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        duration = end_minutes - start_minutes
        
        if duration >= 60:
            hours = duration // 60
            minutes = duration % 60
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            return f"{duration}m"
    
    def get_arrival_status(arrival_time, class_start_time):
        """Get enhanced arrival status for template display"""
        if not arrival_time or not class_start_time:
            return {
                'display_text': 'N/A',
                'badge_class': 'badge bg-secondary',
                'icon': 'fas fa-question'
            }
        return calculate_arrival_status(arrival_time, class_start_time)
    
    return dict(
        get_class_status=get_class_status,
        format_duration=format_duration,
        get_arrival_status=get_arrival_status,
        current_time=datetime.now().time()
    )

@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']
        if Teacher.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        hashed_pw = generate_password_hash(password)
        new_teacher = Teacher(username=username, password=hashed_pw)
        db.session.add(new_teacher)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        teacher = Teacher.query.filter_by(username=username).first()
        if teacher and check_password_hash(teacher.password, password):
            login_user(teacher)
            session.permanent = True  # Enable session timeout
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm', '')

        if not username or not new_password or not confirm_password:
            flash('All fields are required.', 'danger')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')

        teacher = Teacher.query.filter_by(username=username).first()
        if not teacher:
            flash('No account found with that username.', 'danger')
            return render_template('reset_password.html')

        teacher.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password has been reset. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # Run automatic expiration check for pending excuse requests
    auto_expire_pending_excuses()
    
    # Enhanced date and class filter with range support
    date_filter = request.args.get('date')
    date_range = request.args.get('date_range', 'today')  # today, week, month, custom
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')
    class_id = request.args.get('class_id', 'all')
    today = date.today()
    
    # Calculate date range based on selection
    if date_range == 'today':
        start_date = end_date = today
    elif date_range == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif date_range == 'month':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    elif date_range == 'custom' and start_date_param and end_date_param:
        try:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
        except ValueError:
            start_date = end_date = today
    elif date_filter:
        try:
            start_date = end_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            start_date = end_date = today
    else:
        start_date = end_date = today
    
    # Get classes for current teacher
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    
    # Global system statistics
    total_students_count = Student.query.count()
    total_classes_count = len(classes)
    total_attendance_records = Attendance.query.join(Class).filter(Class.teacher_id == current_user.id).count()
    
    # Basic analytics for today/selected range
    analytics = []
    total_present = total_late = total_absent = total_excused = 0
    filtered_classes = classes if class_id == 'all' else [c for c in classes if str(c.id) == class_id]
    
    for c in filtered_classes:
        # Get attendance records
        records = Attendance.query.filter(
            Attendance.class_id == c.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        present = sum(1 for r in records if r.status == 'Present')
        late = sum(1 for r in records if r.status == 'Late')
        absent = sum(1 for r in records if r.status == 'Absent')
        # Count only records with 'Excused' status that have PENDING excuse requests
        # Use join to efficiently get excuse request status instead of individual queries
        excused_with_pending = db.session.query(Attendance).join(
            ExcuseRequest, Attendance.excuse_request_id == ExcuseRequest.id
        ).filter(
            Attendance.class_id == c.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
            Attendance.status == 'Excused',
            ExcuseRequest.status == 'Pending'
        ).count()
        
        excused = excused_with_pending
        
        # Count approved excuse requests as Present (they're already counted as Present in attendance records)
        # Get approved excuse requests for this class and date range that have attendance records
        approved_excuse_requests = ExcuseRequest.query.filter(
            ExcuseRequest.class_id == c.id,
            ExcuseRequest.absence_date >= start_date,
            ExcuseRequest.absence_date <= end_date,
            ExcuseRequest.status == 'Approved'
        ).all()
        
        # Count approved excuses that don't already have attendance records as Present
        additional_present = 0
        for excuse_req in approved_excuse_requests:
            # Check if there's already an attendance record for this student/class/date
            existing_attendance = next((r for r in records 
                                     if r.student_id == excuse_req.student_id 
                                     and r.date == excuse_req.absence_date), None)
            if not existing_attendance:
                additional_present += 1
        
        present += additional_present
        
        # Calculate attendance rate - approved excuses now count as present
        total_students_system = Student.query.count()
        total_attendance = present + late + absent + excused
        # Count Present (including approved excuses), Late as attending
        attending_count = present + late
        attendance_rate = attending_count / total_attendance * 100 if total_attendance > 0 else 0
        
        total_present += present
        total_late += late
        total_absent += absent
        total_excused += excused
        
        analytics.append({
            'class_name': c.name,
            'class_id': c.id,
            'present': present,
            'late': late,
            'absent': absent,
            'excused': excused,
            'attendance_rate': round(attendance_rate, 1),
            'total_students': total_students_system
        })
    
    # Recent activity feed (last 10 attendance records)
    recent_activities = []
    recent_records = db.session.query(Attendance, Student, Class).join(
        Student, Attendance.student_id == Student.id
    ).join(
        Class, Attendance.class_id == Class.id
    ).filter(
        Class.teacher_id == current_user.id
    ).order_by(Attendance.date.desc(), Attendance.id.desc()).limit(10).all()
    
    for attendance, student, class_obj in recent_records:
        recent_activities.append({
            'student_name': student.name,
            'class_name': class_obj.name,
            'status': attendance.status,
            'date': attendance.date
        })
    
    # Weekly trend analysis (last 7 days) - filtered by class if selected
    weekly_trends = []
    for i in range(7):
        trend_date = today - timedelta(days=6-i)
        day_query = Attendance.query.join(Class).filter(
            Class.teacher_id == current_user.id,
            Attendance.date == trend_date
        )
        
        # Filter by class if specified
        if class_id != 'all':
            day_query = day_query.filter(Class.id == class_id)
        
        day_records = day_query.all()
        
        day_present = sum(1 for r in day_records if r.status == 'Present')
        day_late = sum(1 for r in day_records if r.status == 'Late')
        day_absent = sum(1 for r in day_records if r.status == 'Absent')
        
        # Count only records with 'Excused' status that have PENDING excuse requests using efficient query
        day_excused_query = db.session.query(Attendance).join(
            ExcuseRequest, Attendance.excuse_request_id == ExcuseRequest.id
        ).join(Class).filter(
            Class.teacher_id == current_user.id,
            Attendance.date == trend_date,
            Attendance.status == 'Excused',
            ExcuseRequest.status == 'Pending'
        )
        
        # Filter by class if specified
        if class_id != 'all':
            day_excused_query = day_excused_query.filter(Class.id == class_id)
        
        day_excused = day_excused_query.count()
        
        # Also count approved excuse requests for this day that don't have attendance records as Present
        excuse_query = ExcuseRequest.query.join(Class).filter(
            Class.teacher_id == current_user.id,
            ExcuseRequest.absence_date == trend_date,
            ExcuseRequest.status == 'Approved'
        )
        
        # Filter by class if specified
        if class_id != 'all':
            excuse_query = excuse_query.filter(Class.id == class_id)
        
        day_excuse_requests = excuse_query.all()
        
        # Count approved excuse requests that don't already have attendance records as Present
        additional_present = 0
        for excuse_req in day_excuse_requests:
            # Check if there's already an attendance record for this student/class/date
            existing_attendance = next((r for r in day_records 
                                     if r.student_id == excuse_req.student_id 
                                     and r.date == excuse_req.absence_date 
                                     and r.class_id == excuse_req.class_id), None)
            if not existing_attendance:
                additional_present += 1
        
        day_present += additional_present
        day_total = len(day_records) + additional_present
        # Count Present (including approved excuses) and Late as attending
        day_attending = day_present + day_late
        day_rate = day_attending / day_total * 100 if day_total > 0 else 0
        
        weekly_trends.append({
            'date': trend_date.strftime('%m/%d'),
            'day_name': trend_date.strftime('%a'),
            'present': day_present,
            'late': day_late,
            'absent': day_absent,
            'excused': day_excused,
            'rate': round(day_rate, 1)
        })
    
    # Monthly comparison (current vs previous month) - filtered by class if selected
    current_month_start = today.replace(day=1)
    if today.month == 1:
        prev_month_start = date(today.year - 1, 12, 1)
        prev_month_end = date(today.year, 1, 1) - timedelta(days=1)
    else:
        prev_month_start = date(today.year, today.month - 1, 1)
        prev_month_end = current_month_start - timedelta(days=1)
    
    # Apply class filter to monthly analytics
    current_month_query = Attendance.query.join(Class).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= current_month_start,
        Attendance.date <= today
    )
    prev_month_query = Attendance.query.join(Class).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= prev_month_start,
        Attendance.date <= prev_month_end
    )
    
    # Filter by class if specified
    if class_id != 'all':
        current_month_query = current_month_query.filter(Class.id == class_id)
        prev_month_query = prev_month_query.filter(Class.id == class_id)
    
    current_month_records = current_month_query.all()
    prev_month_records = prev_month_query.all()
    
    # Also get excuse requests for monthly comparison
    current_month_excuse_query = ExcuseRequest.query.join(Class).filter(
        Class.teacher_id == current_user.id,
        ExcuseRequest.absence_date >= current_month_start,
        ExcuseRequest.absence_date <= today,
        ExcuseRequest.status == 'Approved'
    )
    prev_month_excuse_query = ExcuseRequest.query.join(Class).filter(
        Class.teacher_id == current_user.id,
        ExcuseRequest.absence_date >= prev_month_start,
        ExcuseRequest.absence_date <= prev_month_end,
        ExcuseRequest.status == 'Approved'
    )
    
    # Filter by class if specified
    if class_id != 'all':
        current_month_excuse_query = current_month_excuse_query.filter(Class.id == class_id)
        prev_month_excuse_query = prev_month_excuse_query.filter(Class.id == class_id)
    
    current_month_excuse_requests = current_month_excuse_query.all()
    prev_month_excuse_requests = prev_month_excuse_query.all()
    
    current_month_rate = 0
    prev_month_rate = 0
    
    if current_month_records or current_month_excuse_requests:
        current_present = sum(1 for r in current_month_records if r.status in ['Present', 'Late'])
        
        # Count only records with 'Excused' status that have PENDING excuse requests using efficient query
        current_excused_query = db.session.query(Attendance).join(
            ExcuseRequest, Attendance.excuse_request_id == ExcuseRequest.id
        ).join(Class).filter(
            Class.teacher_id == current_user.id,
            Attendance.date >= current_month_start,
            Attendance.date <= today,
            Attendance.status == 'Excused',
            ExcuseRequest.status == 'Pending'
        )
        
        # Filter by class if specified
        if class_id != 'all':
            current_excused_query = current_excused_query.filter(Class.id == class_id)
        
        current_excused = current_excused_query.count()
        
        # Count approved excuse requests that don't already have attendance records as Present
        additional_current_present = 0
        for excuse_req in current_month_excuse_requests:
            existing_attendance = next((r for r in current_month_records 
                                     if r.student_id == excuse_req.student_id 
                                     and r.date == excuse_req.absence_date 
                                     and r.class_id == excuse_req.class_id), None)
            if not existing_attendance:
                additional_current_present += 1
        
        total_current = len(current_month_records) + additional_current_present
        # Only Present and Late count as attending (approved excuses are now counted as Present)
        current_attending = current_present + additional_current_present
        current_month_rate = current_attending / total_current * 100 if total_current > 0 else 0
    
    if prev_month_records or prev_month_excuse_requests:
        prev_present = sum(1 for r in prev_month_records if r.status in ['Present', 'Late'])
        
        # Count only records with 'Excused' status that have PENDING excuse requests using efficient query
        prev_excused_query = db.session.query(Attendance).join(
            ExcuseRequest, Attendance.excuse_request_id == ExcuseRequest.id
        ).join(Class).filter(
            Class.teacher_id == current_user.id,
            Attendance.date >= prev_month_start,
            Attendance.date <= prev_month_end,
            Attendance.status == 'Excused',
            ExcuseRequest.status == 'Pending'
        )
        
        # Filter by class if specified
        if class_id != 'all':
            prev_excused_query = prev_excused_query.filter(Class.id == class_id)
        
        prev_excused = prev_excused_query.count()
        
        # Count approved excuse requests that don't already have attendance records as Present
        additional_prev_present = 0
        for excuse_req in prev_month_excuse_requests:
            existing_attendance = next((r for r in prev_month_records 
                                     if r.student_id == excuse_req.student_id 
                                     and r.date == excuse_req.absence_date 
                                     and r.class_id == excuse_req.class_id), None)
            if not existing_attendance:
                additional_prev_present += 1
        
        total_prev = len(prev_month_records) + additional_prev_present
        # Only Present and Late count as attending (approved excuses are now counted as Present)
        prev_attending = prev_present + additional_prev_present
        prev_month_rate = prev_attending / total_prev * 100 if total_prev > 0 else 0
    
    # Real-time status indicators
    current_time = datetime.now().time()
    classes_in_session = []
    upcoming_classes = []
    
    for c in classes:
        if c.start_time and c.end_time:
            if c.start_time <= current_time <= c.end_time:
                # Class in session - check today's attendance
                today_attendance = Attendance.query.filter_by(
                    class_id=c.id, 
                    date=today
                ).all()
                
                classes_in_session.append({
                    'class': c,
                    'attendance_count': len(today_attendance),
                    'present_count': sum(1 for a in today_attendance if a.status in ['Present', 'Late']),
                    'total_students': total_students_count  # Add total students available
                })
            elif c.start_time > current_time:
                upcoming_classes.append({
                    'class': c,
                    'starts_in': str(datetime.combine(today, c.start_time) - datetime.combine(today, current_time)).split('.')[0]
                })
    
    # Calculate overall statistics - approved excuses are now counted as present
    total_attendance = total_present + total_late + total_absent + total_excused
    overall_attending = total_present + total_late  # Present now includes approved excuses
    overall_rate = overall_attending / total_attendance * 100 if total_attendance > 0 else 0
    month_comparison = current_month_rate - prev_month_rate
    
    return render_template('dashboard.html', 
                         analytics=analytics, 
                         weekly_trends=weekly_trends,
                         classes_in_session=classes_in_session,
                         upcoming_classes=upcoming_classes,
                         recent_activities=recent_activities,
                         total_students_count=total_students_count,
                         total_classes_count=total_classes_count,
                         total_attendance_records=total_attendance_records,
                         current_month_rate=round(current_month_rate, 1),
                         prev_month_rate=round(prev_month_rate, 1),
                         month_comparison=round(month_comparison, 1),
                         overall_rate=round(overall_rate, 1),
                         date_filter=date_filter, 
                         date_range=date_range,
                         start_date=start_date,
                         end_date=end_date,
                         total_present=total_present, 
                         total_late=total_late, 
                         total_absent=total_absent, 
                         total_excused=total_excused, 
                         classes=classes, 
                         class_id=class_id, 
                         teacher_name=current_user.username)

@app.route('/classes')
@login_required
def view_classes():
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    
    # Get total students in the system (since all students can attend any class)
    total_students = Student.query.count()
    
    # Add total student count for each class display
    classes_with_counts = []
    for class_ in classes:
        classes_with_counts.append({
            'class': class_,
            'student_count': total_students  # All students available for any class
        })
    
    return render_template('classes.html', classes_with_counts=classes_with_counts, total_students=total_students)

@app.route('/classes/add', methods=['GET', 'POST'])
@login_required
def add_class():
    if request.method == 'POST':
        name = request.form['name']
        start_time_str = request.form.get('start_time', '08:00')
        end_time_str = request.form.get('end_time', '17:00')
        
        if not name:
            flash('Class name is required.', 'danger')
            return render_template('add_class.html')
        
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
            
            if start_time >= end_time:
                flash('Start time must be before end time.', 'danger')
                return render_template('add_class.html')
                
        except ValueError:
            flash('Invalid time format. Please use HH:MM format.', 'danger')
            return render_template('add_class.html')
        
        new_class = Class(name=name, teacher_id=current_user.id, start_time=start_time, end_time=end_time)
        db.session.add(new_class)
        db.session.commit()
        flash('Class added successfully.', 'success')
        return redirect(url_for('view_classes'))
    return render_template('add_class.html')

@app.route('/classes/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        name = request.form['name']
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        if not name:
            flash('Class name is required.', 'danger')
            return render_template('edit_class.html', class_=class_)
        
        try:
            if start_time_str:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                class_.start_time = start_time
            
            if end_time_str:
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                class_.end_time = end_time
            
            if class_.start_time >= class_.end_time:
                flash('Start time must be before end time.', 'danger')
                return render_template('edit_class.html', class_=class_)
                
        except ValueError:
            flash('Invalid time format. Please use HH:MM format.', 'danger')
            return render_template('edit_class.html', class_=class_)
        
        class_.name = name
        db.session.commit()
        flash('Class updated successfully.', 'success')
        return redirect(url_for('view_classes'))
    return render_template('edit_class.html', class_=class_)

@app.route('/classes/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    db.session.delete(class_)
    db.session.commit()
    flash('Class deleted successfully.', 'success')
    return redirect(url_for('view_classes'))

@app.route('/classes/<int:class_id>/students')
@login_required
def view_students(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    students = Student.query.filter_by(class_id=class_id).all()
    return render_template('students.html', class_=class_, students=students)

@app.route('/classes/<int:class_id>/students/add', methods=['GET', 'POST'])
@login_required
def add_student(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        name = request.form['name']
        student_number = request.form['student_number']
        avatar_filename = request.form.get('avatar')
        photo = request.files.get('photo')
        if not name or not student_number:
            flash('Name and student number are required.', 'danger')
            return render_template('add_student.html', class_=class_)
        if Student.query.filter_by(student_number=student_number).first():
            flash('Student number already exists.', 'danger')
            return render_template('add_student.html', class_=class_)
        # Generate QR code
        qr_data = f"{student_number}"
        qr = qrcode.make(qr_data)
        qr_path = f'static/qr/{student_number}.png'
        import os
        os.makedirs('static/qr', exist_ok=True)
        qr.save(qr_path)
        # Handle photo upload or avatar selection
        photo_path = None
        if photo and photo.filename != '':
            photo_path = save_photo(photo, student_number)
        elif avatar_filename:
            photo_path = f'static/avatars/{avatar_filename}'
        new_student = Student(name=name, student_number=student_number, class_id=class_id, qr_code_path=qr_path, photo_path=photo_path)
        db.session.add(new_student)
        db.session.commit()
        flash('Student added and QR code generated.', 'success')
        return redirect(url_for('view_students', class_id=class_id))
    return render_template('add_student.html', class_=class_)

@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    # class_ = Class.query.get_or_404(student.class_id)  # No longer needed
    # if class_.teacher_id != current_user.id:
    #     abort(403)
    if request.method == 'POST':
        name = request.form['name']
        photo = request.files.get('photo')  # Get uploaded photo
        
        if not name:
            flash('Name is required.', 'danger')
            return render_template('edit_student.html', student=student)
        
        # Update student name
        student.name = name
        
        # Handle photo upload
        if photo and photo.filename != '':
            # Delete old photo if it exists
            if student.photo_path and os.path.exists(student.photo_path):
                try:
                    os.remove(student.photo_path)
                except Exception as e:
                    print(f"Error deleting old photo: {e}")
            
            # Save new photo
            photo_path = save_photo(photo, student.student_number)
            if photo_path:
                student.photo_path = photo_path
                flash('Student updated with new photo.', 'success')
            else:
                flash('Student updated, but photo upload failed. Invalid photo format.', 'warning')
        
        db.session.commit()
        if not (photo and photo.filename != ''):
            flash('Student updated.', 'success')
        return redirect(url_for('manage_students'))
    return render_template('edit_student.html', student=student)

@app.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted.', 'success')
    return redirect(url_for('manage_students'))

@app.route('/students/qr/<int:student_id>')
@login_required
def download_qr(student_id):
    student = Student.query.get_or_404(student_id)
    if not student.qr_code_path:
        flash('QR code not found.', 'danger')
        return redirect(url_for('manage_students'))
    qr_path = os.path.join(os.getcwd(), student.qr_code_path)
    if not os.path.exists(qr_path):
        flash('QR code file does not exist.', 'danger')
        return redirect(url_for('manage_students'))
    return send_file(qr_path, as_attachment=True)

@app.route('/students/<int:student_id>/photo/delete', methods=['POST'])
@login_required
def delete_student_photo(student_id):
    student = Student.query.get_or_404(student_id)
    if student.photo_path:
        # Delete the photo file
        if os.path.exists(student.photo_path):
            try:
                os.remove(student.photo_path)
                flash('Photo deleted successfully.', 'success')
            except Exception as e:
                flash('Error deleting photo file.', 'warning')
                print(f"Error deleting photo: {e}")
        
        # Remove photo path from database
        student.photo_path = None
        db.session.commit()
    else:
        flash('No photo to delete.', 'info')
    
    return redirect(url_for('edit_student', student_id=student_id))

@app.route('/attendance/select', methods=['GET', 'POST'])
@login_required
def select_class_for_attendance():
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        if class_id:
            return redirect(url_for('take_attendance', class_id=class_id))
    return render_template('select_class_attendance.html', classes=classes)

@app.route('/classes/<int:class_id>/attendance', methods=['GET', 'POST'])
@login_required
def take_attendance(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    selected_date = request.form.get('attendance_date') if request.method == 'POST' else request.args.get('attendance_date')
    if selected_date:
        try:
            attendance_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            attendance_date = date.today()
    else:
        attendance_date = date.today()
    # Get all attendance records for today (to check existing records)
    all_today_records = Attendance.query.filter_by(class_id=class_id, date=attendance_date).all()
    present_students = [a for a in all_today_records if a.status == 'Present']
    present_ids = [a.student_id for a in present_students]
    students = Student.query.all()  # Show all students
    # Manual mark Absent/Excused/Late
    if request.method == 'POST' and 'manual_student_id' in request.form and 'manual_status' in request.form:
        student_id = int(request.form['manual_student_id'])
        status = request.form['manual_status']
        arrival_time_str = request.form.get('manual_arrival_time', '')
        notes = request.form.get('manual_notes', '').strip()
        
        student = Student.query.get(student_id)
        if not student:
            flash('Student not found.', 'danger')
        else:
            # Handle arrival time for late status
            arrival_time = None
            is_late = False
            minutes_late = 0
            
            if status == 'Late':
                if arrival_time_str:
                    try:
                        arrival_time = datetime.strptime(arrival_time_str, '%H:%M').time()
                        is_late, minutes_late = calculate_late_arrival(arrival_time, class_.start_time)
                    except ValueError:
                        flash('Invalid time format. Please use HH:MM format.', 'danger')
                        return redirect(url_for('take_attendance', class_id=class_id) + f'?attendance_date={attendance_date}')
                else:
                    # Default to current time if no time provided for late status
                    arrival_time = datetime.now().time()
                    is_late, minutes_late = calculate_late_arrival(arrival_time, class_.start_time)
            
            # Check if already has a record for this date/class
            record = Attendance.query.filter_by(student_id=student_id, class_id=class_id, date=attendance_date).first()
            if record:
                record.status = status
                record.scan_time = datetime.now().time()
                record.arrival_time = arrival_time
                record.late_arrival = is_late
                record.late_minutes = minutes_late
                record.notes = notes
                db.session.commit()
                
                if status == 'Late':
                    flash(f"{student.name}'s status updated to Late ({minutes_late} minutes late).", 'warning')
                else:
                    flash(f"{student.name}'s status updated to {status}.", 'success')
            else:
                attendance = Attendance(
                    student_id=student_id, 
                    class_id=class_id, 
                    teacher_id=current_user.id, 
                    date=attendance_date, 
                    scan_time=datetime.now().time(), 
                    arrival_time=arrival_time,
                    status=status,
                    late_arrival=is_late,
                    late_minutes=minutes_late,
                    notes=notes
                )
                db.session.add(attendance)
                db.session.commit()
                
                if status == 'Late':
                    flash(f"{student.name} marked as Late ({minutes_late} minutes late).", 'warning')
                else:
                    flash(f"{student.name} marked as {status}.", 'success')
        return redirect(url_for('take_attendance', class_id=class_id) + f'?attendance_date={attendance_date}')
    
    # Auto-mark absent students (new functionality)
    if request.method == 'POST' and 'auto_mark_absent' in request.form:
        absent_count = auto_mark_absent_students(class_id, attendance_date)
        if absent_count > 0:
            flash(f'Automatically marked {absent_count} student(s) as absent.', 'success')
        else:
            flash('No students to mark as absent, or class has not ended yet.', 'info')
        return redirect(url_for('take_attendance', class_id=class_id) + f'?attendance_date={attendance_date}')
    # QR scan present
    if request.method == 'POST' and 'qr_data' in request.form:
        qr_data = request.form.get('qr_data')
        arrival_time_str = request.form.get('arrival_time', '')  # Optional manual arrival time
        
        student = Student.query.filter_by(student_number=qr_data).first()  # Find by student_number only
        if not student:
            flash('Student not found.', 'danger')
        else:
            # Determine arrival time
            if arrival_time_str:
                try:
                    arrival_time = datetime.strptime(arrival_time_str, '%H:%M').time()
                except ValueError:
                    arrival_time = datetime.now().time()
                    flash('Invalid time format, using current time.', 'warning')
            else:
                arrival_time = datetime.now().time()
            
            # Calculate late arrival status using class-specific start time
            is_late, minutes_late = calculate_late_arrival(arrival_time, class_.start_time)
            
            # Determine status based on arrival time
            if is_late:
                status = 'Late'
            else:
                status = 'Present'
            
            # Check if student already has an attendance record for this date/class
            existing_record = Attendance.query.filter_by(
                student_id=student.id, 
                class_id=class_id, 
                date=attendance_date
            ).first()
            
            if existing_record:
                if existing_record.status in ['Present', 'Late']:
                    flash(f'{student.name} is already marked {existing_record.status.lower()}.', 'info')
                else:
                    # Update existing record
                    existing_record.status = status
                    existing_record.scan_time = datetime.now().time()
                    existing_record.arrival_time = arrival_time
                    existing_record.late_arrival = is_late
                    existing_record.late_minutes = minutes_late
                    db.session.commit()
                    
                    if is_late:
                        flash(f'{student.name} marked as Late (arrived {minutes_late} minutes late).', 'warning')
                    else:
                        flash(f'{student.name} status updated to Present.', 'success')
            else:
                # Create new attendance record
                attendance = Attendance(
                    student_id=student.id, 
                    class_id=class_id, 
                    teacher_id=current_user.id, 
                    date=attendance_date, 
                    scan_time=datetime.now().time(),
                    arrival_time=arrival_time,
                    status=status,
                    late_arrival=is_late,
                    late_minutes=minutes_late
                )
                db.session.add(attendance)
                db.session.commit()
                
                if is_late:
                    flash(f'{student.name} marked as Late (arrived {minutes_late} minutes late).', 'warning')
                else:
                    flash(f'{student.name} marked present.', 'success')
        return redirect(url_for('take_attendance', class_id=class_id) + f'?attendance_date={attendance_date}')
    # Get all attendance records for the selected date and class
    all_attendance = Attendance.query.filter_by(class_id=class_id, date=attendance_date).all()
    
    # Separate students by status
    present_students = [a for a in all_attendance if a.status == 'Present']
    late_students = [a for a in all_attendance if a.status == 'Late']
    absent_students = [a for a in all_attendance if a.status == 'Absent']
    excused_students = [a for a in all_attendance if a.status == 'Excused']
    
    # Convert to student objects with attendance info
    present_list = [(Student.query.get(a.student_id), a) for a in present_students]
    late_list = [(Student.query.get(a.student_id), a) for a in late_students]
    absent_list = [(Student.query.get(a.student_id), a) for a in absent_students]
    excused_list = [(Student.query.get(a.student_id), a) for a in excused_students]
    
    return render_template('attendance.html', 
                         class_=class_, 
                         students=students, 
                         present_list=present_list,
                         late_list=late_list,
                         absent_list=absent_list,
                         excused_list=excused_list,
                         attendance_date=attendance_date)

@app.route('/attendance/edit/<int:attendance_id>', methods=['GET', 'POST'])
@login_required
def edit_attendance(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)
    student = Student.query.get(record.student_id)
    class_ = Class.query.get(record.class_id)
    
    if request.method == 'POST':
        status = request.form['status']
        scan_time = request.form['scan_time']
        arrival_time_str = request.form.get('arrival_time', '')
        notes = request.form.get('notes', '').strip()
        
        # Parse scan time
        try:
            h, m = map(int, scan_time.split(':'))
            record.scan_time = time(h, m, 0)
        except Exception:
            flash('Invalid scan time format. Use HH:MM format.', 'danger')
            return redirect(url_for('edit_attendance', attendance_id=attendance_id))
        
        # Handle arrival time and late calculation
        arrival_time = None
        is_late = False
        minutes_late = 0
        
        if status == 'Late':
            if arrival_time_str:
                try:
                    ah, am = map(int, arrival_time_str.split(':'))
                    arrival_time = time(ah, am, 0)
                except Exception:
                    flash('Invalid arrival time format. Use HH:MM format.', 'danger')
                    return redirect(url_for('edit_attendance', attendance_id=attendance_id))
            else:
                # Use scan time as arrival time if not specified
                arrival_time = record.scan_time
            
            # Calculate late status using class start time
            if class_ and class_.start_time:
                is_late, minutes_late = calculate_late_arrival(arrival_time, class_.start_time)
        
        # Update record
        record.status = status
        record.arrival_time = arrival_time
        record.late_arrival = is_late
        record.late_minutes = minutes_late
        record.notes = notes
        
        db.session.commit()
        flash('Attendance record updated successfully.', 'success')
        return redirect(url_for('attendance_records', class_id=record.class_id))
    
    return render_template('edit_attendance.html', record=record, student=student, class_=class_)

@app.route('/classes/<int:class_id>/records', methods=['GET', 'POST'])
@login_required
def attendance_records(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    date_filter = request.form.get('date') if request.method == 'POST' else None
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            filter_date = None
    else:
        filter_date = None
    if filter_date:
        records = Attendance.query.filter_by(class_id=class_id, date=filter_date).all()
    else:
        records = Attendance.query.filter_by(class_id=class_id).all()
    students = {s.id: s for s in Student.query.all()}
    return render_template('records.html', class_=class_, records=records, students=students, date_filter=date_filter)

@app.route('/classes/<int:class_id>/records/export')
@login_required
def export_records(class_id):
    class_ = Class.query.get_or_404(class_id)
    if class_.teacher_id != current_user.id:
        abort(403)
    records = Attendance.query.filter_by(class_id=class_id).all()
    students = {s.id: s for s in Student.query.all()}
    import csv
    import io
    from flask import Response
    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Student Name', 'Student Number', 'Scan Time', 'Arrival Time', 'Status', 'Late Minutes', 'Notes'])
        for r in records:
            s = students.get(r.student_id)
            scan_time = r.scan_time.strftime('%H:%M:%S') if r.scan_time else ''
            arrival_time = r.arrival_time.strftime('%H:%M:%S') if r.arrival_time else ''
            date_str = r.date.strftime('%Y-%m-%d') if hasattr(r.date, 'strftime') else str(r.date)
            late_minutes = r.late_minutes if r.late_minutes else ''
            notes = r.notes if r.notes else ''
            writer.writerow([date_str, s.name if s else '', s.student_number if s else '', 
                           scan_time, arrival_time, r.status, late_minutes, notes])
        return output.getvalue()
    return Response(generate(), mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename=attendance_{class_.name}.csv'})

@app.route('/students/manage', methods=['GET', 'POST'])
@login_required
def manage_students():
    """
    Global student management - all students can attend any class
    """
    students = Student.query.all()
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        student_number = request.form['student_number']
        photo = request.files.get('photo')  # Get uploaded photo
        avatar_filename = request.form.get('avatar')
        
        normalized_name = name.lower()
        duplicate = any(s.name.strip().lower() == normalized_name for s in students)
        
        if not name or not student_number:
            flash('All fields are required.', 'danger')
        elif not student_number.isdigit():
            flash('Student number must be digits only.', 'danger')
        elif Student.query.filter_by(student_number=student_number).first():
            flash('Student number already exists.', 'danger')
        elif duplicate:
            flash('A student with this name already exists.', 'danger')
        else:
            # Handle photo upload
            photo_path = None
            if photo and photo.filename != '':
                photo_path = save_photo(photo, student_number)
                if not photo_path:
                    flash('Invalid photo format. Please use PNG, JPG, JPEG, or GIF.', 'warning')
            elif avatar_filename:
                photo_path = f'static/avatars/{avatar_filename}'
            
            # Optimize QR code generation: only generate if file does not exist
            import qrcode, os
            qr_data = f"{student_number}"
            qr_path = f'static/qr/{student_number}.png'
            os.makedirs('static/qr', exist_ok=True)
            if not os.path.exists(qr_path):
                qr = qrcode.make(qr_data)
                qr.save(qr_path)
            
            # Create student without specific class assignment (can attend any class)
            new_student = Student(
                name=name, 
                student_number=student_number, 
                class_id=None,  # No specific class assignment
                qr_code_path=qr_path, 
                photo_path=photo_path
            )
            db.session.add(new_student)
            db.session.commit()
            
            success_msg = 'Student added successfully. They can now attend any class.'
            if photo_path:
                success_msg += ' Photo uploaded successfully.'
            flash(success_msg, 'success')
            return redirect(url_for('manage_students'))
    
    return render_template('manage_students.html', students=students, classes=classes)

@app.route('/records/manage', methods=['GET', 'POST'])
@login_required
def manage_records():
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    # Support both POST (form submission) and GET (URL parameters) for filtering
    class_id = request.form.get('class_id') or request.args.get('class_id')
    date_filter = request.form.get('date') or request.args.get('date')
    page = int(request.args.get('page', 1))
    per_page = 10
    query = Attendance.query.join(Class).filter(Class.teacher_id == current_user.id)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if date_filter:
        from datetime import datetime
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Attendance.date == filter_date)
        except ValueError:
            pass
    total_records = query.count()
    total_pages = ceil(total_records / per_page) if total_records else 1
    records = query.order_by(Attendance.date.desc(), Attendance.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    students = {s.id: s for s in Student.query.all()}
    class_dict = {c.id: c for c in classes}
    present = sum(1 for r in query if r.status == 'Present')
    absent = sum(1 for r in query if r.status == 'Absent')
    excused = sum(1 for r in query if r.status == 'Excused')
    return render_template('manage_records.html', classes=classes, records=records, students=students, class_dict=class_dict, class_id=class_id, date_filter=date_filter, present=present, absent=absent, excused=excused, page=page, total_pages=total_pages)

@app.route('/records/manage/export', methods=['POST'])
@login_required
def export_manage_records():
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    class_id = request.form.get('class_id')
    date_filter = request.form.get('date')
    query = Attendance.query.join(Class).filter(Class.teacher_id == current_user.id)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if date_filter:
        from datetime import datetime
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Attendance.date == filter_date)
        except ValueError:
            pass
    records = query.all()
    students = {s.id: s for s in Student.query.all()}
    class_dict = {c.id: c for c in classes}
    import csv
    import io
    from flask import Response
    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Class', 'Student Name', 'Student Number', 'Date', 'Scan Time', 'Status'])
        for r in records:
            s = students.get(r.student_id)
            c = class_dict.get(r.class_id)
            scan_time = r.scan_time.strftime('%H:%M:%S') if r.scan_time else ''
            date_str = r.date.strftime('%Y-%m-%d') if hasattr(r.date, 'strftime') else str(r.date)
            writer.writerow([
                c.name if c else '',
                s.name if s else '',
                s.student_number if s else '',
                date_str,
                scan_time,
                r.status
            ])
        return output.getvalue()
    return Response(generate(), mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=attendance_records.csv'})


app.jinja_env.globals.update(now=datetime.now)

# Excuse Request Management Routes
@app.route('/excuse-requests', methods=['GET', 'POST'])
@login_required
def manage_excuse_requests():
    """Manage excuse requests for teachers"""
    # Get all excuse requests for this teacher's classes
    excuse_requests = ExcuseRequest.query.filter_by(teacher_id=current_user.id).order_by(ExcuseRequest.submitted_at.desc()).all()
    
    return render_template('excuse_requests.html', excuse_requests=excuse_requests)

@app.route('/excuse-requests/<int:request_id>/review', methods=['POST'])
@login_required
def review_excuse_request(request_id):
    """Approve or disapprove an excuse request"""
    excuse_request = ExcuseRequest.query.get_or_404(request_id)
    
    # Check if teacher owns this request
    if excuse_request.teacher_id != current_user.id:
        abort(403)
    
    action = request.form.get('action')  # 'approve' or 'disapprove'
    teacher_notes = request.form.get('teacher_notes', '').strip()
    
    if action == 'approve':
        excuse_request.status = 'Approved'
        
        # Update or create attendance record as "Present" with approved status
        attendance = Attendance.query.filter_by(
            student_id=excuse_request.student_id,
            class_id=excuse_request.class_id,
            date=excuse_request.absence_date
        ).first()
        
        if attendance:
            # Update existing record to Present with approved excuse request link
            attendance.status = 'Present'
            attendance.excuse_request_id = excuse_request.id
            attendance.notes = f"Present (Approved Excuse): {excuse_request.reason}"
        else:
            # Create new present attendance record with excuse link
            attendance = Attendance(
                student_id=excuse_request.student_id,
                class_id=excuse_request.class_id,
                teacher_id=current_user.id,
                date=excuse_request.absence_date,
                scan_time=datetime.now().time(),
                status='Present',
                excuse_request_id=excuse_request.id,
                notes=f"Present (Approved Excuse): {excuse_request.reason}"
            )
            db.session.add(attendance)
        
        flash(f'Excuse request approved for {excuse_request.student.name}. Status updated to Present.', 'success')
        
    elif action == 'disapprove':
        excuse_request.status = 'Disapproved'
        
        # Update attendance record from Excused to Absent when disapproved
        attendance = Attendance.query.filter_by(
            student_id=excuse_request.student_id,
            class_id=excuse_request.class_id,
            date=excuse_request.absence_date
        ).first()
        
        if attendance:
            # Change from Excused to Absent since excuse was disapproved
            attendance.status = 'Absent'
            attendance.excuse_request_id = excuse_request.id  # Keep link for tracking
            attendance.notes = f"Excuse disapproved: {excuse_request.reason}" + (f" | Teacher notes: {teacher_notes}" if teacher_notes else "")
        else:
            # Create new absent attendance record
            attendance = Attendance(
                student_id=excuse_request.student_id,
                class_id=excuse_request.class_id,
                teacher_id=current_user.id,
                date=excuse_request.absence_date,
                scan_time=datetime.now().time(),
                status='Absent',
                excuse_request_id=excuse_request.id,
                notes=f"Excuse disapproved: {excuse_request.reason}" + (f" | Teacher notes: {teacher_notes}" if teacher_notes else "")
            )
            db.session.add(attendance)
        
        flash(f'Excuse request disapproved for {excuse_request.student.name}. Status changed to Absent.', 'warning')
    
    excuse_request.reviewed_at = datetime.now()
    excuse_request.teacher_notes = teacher_notes
    
    db.session.commit()
    return redirect(url_for('manage_excuse_requests'))

@app.route('/submit-excuse', methods=['GET', 'POST'])
def submit_excuse_request():
    """Allow students to submit excuse requests (simplified - normally would need student login)"""
    classes = Class.query.all()
    students = Student.query.all()
    
    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        class_id = int(request.form['class_id'])
        absence_date_str = request.form['absence_date']
        reason = request.form['reason'].strip()
        excuse_file = request.files.get('excuse_letter')
        
        try:
            absence_date = datetime.strptime(absence_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'danger')
            return render_template('submit_excuse.html', classes=classes, students=students)
        
        if not reason:
            flash('Reason for absence is required.', 'danger')
            return render_template('submit_excuse.html', classes=classes, students=students)
        
        # Get teacher for this class
        class_ = Class.query.get(class_id)
        if not class_:
            flash('Invalid class selected.', 'danger')
            return render_template('submit_excuse.html', classes=classes, students=students)
        
        # Save excuse letter if uploaded
        excuse_letter_path = None
        if excuse_file and excuse_file.filename:
            excuse_letter_path = save_excuse_letter(excuse_file, student_id, class_id, absence_date_str)
            if not excuse_letter_path:
                flash('Invalid file format. Please upload PNG, JPG, JPEG, or GIF files.', 'warning')
        
        # Create excuse request
        excuse_request = ExcuseRequest(
            student_id=student_id,
            class_id=class_id,
            teacher_id=class_.teacher_id,
            absence_date=absence_date,
            reason=reason,
            excuse_letter_path=excuse_letter_path
        )
        
        db.session.add(excuse_request)
        db.session.flush()  # Get the excuse request ID
        
        # Check if attendance record already exists for this date
        existing_attendance = Attendance.query.filter_by(
            student_id=student_id,
            class_id=class_id,
            date=absence_date
        ).first()
        
        if existing_attendance:
            # Update existing attendance record to link with excuse request
            if existing_attendance.status not in ['Present', 'Late']:  # Don't override Present/Late
                existing_attendance.status = 'Excused'
                existing_attendance.excuse_request_id = excuse_request.id
                existing_attendance.notes = f"Excuse request submitted: {reason}"
        else:
            # Create new attendance record with "Excused" status and pending excuse request
            new_attendance = Attendance(
                student_id=student_id,
                class_id=class_id,
                teacher_id=class_.teacher_id,
                date=absence_date,
                scan_time=datetime.now().time(),
                status='Excused',
                excuse_request_id=excuse_request.id,
                notes=f"Excuse request submitted: {reason}"
            )
            db.session.add(new_attendance)
        
        db.session.commit()
        
        flash('Excuse request submitted successfully. Attendance record created with pending status. Please wait for teacher approval.', 'success')
        return redirect(url_for('submit_excuse_request'))
    
    return render_template('submit_excuse.html', classes=classes, students=students)

@app.route('/excuse-requests/expire-pending', methods=['POST'])
@login_required
def expire_pending_excuses():
    """Manually trigger expiration of pending excuse requests older than 7 days"""
    expired_count = auto_expire_pending_excuses()
    if expired_count > 0:
        flash(f'Expired {expired_count} pending excuse requests older than 7 days.', 'warning')
    else:
        flash('No pending excuse requests found that are older than 7 days.', 'info')
    return redirect(url_for('manage_excuse_requests'))

@app.route('/excuse-requests/<int:request_id>/details')
@login_required
def get_excuse_details(request_id):
    """API endpoint to get excuse request details for modal display"""
    excuse_request = ExcuseRequest.query.get_or_404(request_id)
    
    # Check if teacher owns this request
    if excuse_request.teacher_id != current_user.id:
        abort(403)
    
    return {
        'student_name': excuse_request.student.name,
        'student_number': excuse_request.student.student_number,
        'absence_date': excuse_request.absence_date.strftime('%B %d, %Y'),
        'reason': excuse_request.reason,
        'status': excuse_request.status,
        'submitted_at': excuse_request.submitted_at.strftime('%B %d, %Y at %I:%M %p'),
        'reviewed_at': excuse_request.reviewed_at.strftime('%B %d, %Y at %I:%M %p') if excuse_request.reviewed_at else None,
        'teacher_notes': excuse_request.teacher_notes,
        'excuse_letter_path': excuse_request.excuse_letter_path
    }

# Inline Analytics Functions
def calculate_attendance_trends_inline(days=30, class_id=None):
    """Calculate attendance trends over specified period"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Base query
    query = db.session.query(
        Attendance.date,
        Attendance.status,
        func.count(Attendance.id).label('count')
    ).join(Class).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if class_id and class_id != 'all':
        query = query.filter(Class.id == class_id)
    
    results = query.group_by(Attendance.date, Attendance.status).all()
    
    # Process results into daily trends
    trends = {}
    for result in results:
        date_str = result.date.strftime('%Y-%m-%d')
        if date_str not in trends:
            trends[date_str] = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
        trends[date_str][result.status] = result.count
    
    # Fill missing dates with zeros
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        if date_str not in trends:
            trends[date_str] = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
        current_date += timedelta(days=1)
    
    return trends

def get_student_attendance_summary_inline(class_id=None, days=30):
    """Get detailed attendance summary per student"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get all students
    students_query = db.session.query(Student)
    if class_id and class_id != 'all':
        students_query = students_query.filter(Student.class_id == class_id)
    
    students = students_query.all()
    
    student_summaries = []
    
    for student in students:
        # Get attendance records for this student
        attendance_query = db.session.query(Attendance).join(Class).filter(
            Class.teacher_id == current_user.id,
            Attendance.student_id == student.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        )
        
        if class_id and class_id != 'all':
            attendance_query = attendance_query.filter(Class.id == class_id)
        
        records = attendance_query.all()
        
        # Calculate statistics
        total_days = len(records)
        present_count = sum(1 for r in records if r.status == 'Present')
        late_count = sum(1 for r in records if r.status == 'Late')
        absent_count = sum(1 for r in records if r.status == 'Absent')
        excused_count = sum(1 for r in records if r.status == 'Excused')
        
        # Calculate attendance rate
        attending_count = present_count + late_count
        attendance_rate = (attending_count / total_days * 100) if total_days > 0 else 0
        
        # Calculate average late minutes
        late_records = [r for r in records if r.status == 'Late' and r.late_minutes > 0]
        avg_late_minutes = sum(r.late_minutes for r in late_records) / len(late_records) if late_records else 0
        
        # Get recent attendance pattern (last 7 days)
        recent_records = [r for r in records if r.date >= (end_date - timedelta(days=7))]
        recent_pattern = [r.status for r in sorted(recent_records, key=lambda x: x.date)]
        
        # Calculate risk level
        if attendance_rate < 70 or absent_count > 5:
            risk_level = 'high'
        elif attendance_rate < 85 or absent_count > 3 or late_count > 5:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        student_summaries.append({
            'student': student,
            'total_days': total_days,
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'excused_count': excused_count,
            'attendance_rate': round(attendance_rate, 1),
            'avg_late_minutes': round(avg_late_minutes, 1),
            'recent_pattern': recent_pattern,
            'risk_level': risk_level
        })
    
    return sorted(student_summaries, key=lambda x: x['attendance_rate'])

def get_class_comparison_data_inline(days=30):
    """Compare attendance across different classes"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    comparison_data = []
    
    for class_ in classes:
        records = Attendance.query.filter(
            Attendance.class_id == class_.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        if not records:
            continue
        
        total_records = len(records)
        present_count = sum(1 for r in records if r.status == 'Present')
        late_count = sum(1 for r in records if r.status == 'Late')
        absent_count = sum(1 for r in records if r.status == 'Absent')
        
        attendance_rate = ((present_count + late_count) / total_records * 100) if total_records > 0 else 0
        
        # Calculate average daily attendance
        daily_attendance = defaultdict(int)
        for record in records:
            if record.status in ['Present', 'Late']:
                daily_attendance[record.date] += 1
        
        avg_daily_attendance = sum(daily_attendance.values()) / len(daily_attendance) if daily_attendance else 0
        
        comparison_data.append({
            'class_name': class_.name,
            'class_id': class_.id,
            'total_records': total_records,
            'attendance_rate': round(attendance_rate, 1),
            'avg_daily_attendance': round(avg_daily_attendance, 1),
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'start_time': class_.start_time.strftime('%H:%M') if class_.start_time else 'N/A',
            'end_time': class_.end_time.strftime('%H:%M') if class_.end_time else 'N/A'
        })
    
    return sorted(comparison_data, key=lambda x: x['attendance_rate'], reverse=True)

def get_time_based_analytics_inline(class_id=None, days=30):
    """Analyze attendance patterns by time of day and day of week"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    query = db.session.query(Attendance).join(Class).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if class_id and class_id != 'all':
        query = query.filter(Class.id == class_id)
    
    records = query.all()
    
    # Day of week analysis
    day_stats = defaultdict(lambda: {'Present': 0, 'Late': 0, 'Absent': 0, 'total': 0})
    
    # Hour of day analysis (for late arrivals)
    hour_stats = defaultdict(lambda: {'count': 0, 'late_minutes': 0})
    
    for record in records:
        day_name = record.date.strftime('%A')
        day_stats[day_name][record.status] += 1
        day_stats[day_name]['total'] += 1
        
        if record.status == 'Late' and record.scan_time:
            hour = record.scan_time.hour
            hour_stats[hour]['count'] += 1
            hour_stats[hour]['late_minutes'] += record.late_minutes or 0
    
    # Calculate attendance rates by day
    day_analysis = []
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        stats = day_stats[day]
        if stats['total'] > 0:
            attendance_rate = ((stats['Present'] + stats['Late']) / stats['total']) * 100
            day_analysis.append({
                'day': day,
                'attendance_rate': round(attendance_rate, 1),
                'total_records': stats['total'],
                'present': stats['Present'],
                'late': stats['Late'],
                'absent': stats['Absent']
            })
    
    # Process hour analysis
    hour_analysis = []
    for hour in range(24):
        if hour in hour_stats:
            avg_late_minutes = hour_stats[hour]['late_minutes'] / hour_stats[hour]['count']
            hour_analysis.append({
                'hour': hour,
                'hour_display': f"{hour:02d}:00",
                'late_count': hour_stats[hour]['count'],
                'avg_late_minutes': round(avg_late_minutes, 1)
            })
    
    return {
        'day_analysis': day_analysis,
        'hour_analysis': sorted(hour_analysis, key=lambda x: x['late_count'], reverse=True)
    }

def get_predictive_insights_inline(class_id=None):
    """Generate predictive insights based on attendance patterns"""
    # Get recent 60 days of data for analysis
    end_date = date.today()
    start_date = end_date - timedelta(days=60)
    
    student_summaries = get_student_attendance_summary_inline(class_id, 60)
    
    insights = {
        'at_risk_students': [],
        'improving_students': [],
        'consistent_performers': [],
        'recommendations': []
    }
    
    for summary in student_summaries:
        student = summary['student']
        attendance_rate = summary['attendance_rate']
        recent_pattern = summary['recent_pattern']
        
        # Analyze recent trend
        if len(recent_pattern) >= 5:
            recent_absences = recent_pattern[-5:].count('Absent')
            recent_lates = recent_pattern[-5:].count('Late')
            
            if attendance_rate < 75 or recent_absences >= 3:
                insights['at_risk_students'].append({
                    'student': student,
                    'attendance_rate': attendance_rate,
                    'recent_absences': recent_absences,
                    'risk_factors': []
                })
            elif attendance_rate > 90 and recent_absences == 0:
                insights['consistent_performers'].append({
                    'student': student,
                    'attendance_rate': attendance_rate
                })
    
    # Generate recommendations
    if insights['at_risk_students']:
        insights['recommendations'].append({
            'type': 'intervention',
            'message': f"{len(insights['at_risk_students'])} students need attention for poor attendance",
            'priority': 'high'
        })
    
    if len(insights['consistent_performers']) > len(student_summaries) * 0.8:
        insights['recommendations'].append({
            'type': 'positive',
            'message': "Excellent overall class attendance! Keep up the good work.",
            'priority': 'low'
        })
    
    return insights

def generate_attendance_report_inline(start_date, end_date, class_id=None):
    """Generate comprehensive attendance report"""
    
    # Get basic statistics
    query = db.session.query(Attendance).join(Class).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if class_id and class_id != 'all':
        query = query.filter(Class.id == class_id)
    
    records = query.all()
    
    # Calculate overall statistics
    total_records = len(records)
    present_count = sum(1 for r in records if r.status == 'Present')
    late_count = sum(1 for r in records if r.status == 'Late')
    absent_count = sum(1 for r in records if r.status == 'Absent')
    excused_count = sum(1 for r in records if r.status == 'Excused')
    
    overall_attendance_rate = ((present_count + late_count) / total_records * 100) if total_records > 0 else 0
    
    # Get trends data
    days_diff = (end_date - start_date).days + 1
    trends = calculate_attendance_trends_inline(days_diff, class_id)
    
    # Get student summaries
    student_summaries = get_student_attendance_summary_inline(class_id, days_diff)
    
    # Get time-based analytics
    time_analytics = get_time_based_analytics_inline(class_id, days_diff)
    
    report_data = {
        'period': {
            'start_date': start_date,
            'end_date': end_date,
            'total_days': days_diff
        },
        'overall_stats': {
            'total_records': total_records,
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'excused_count': excused_count,
            'attendance_rate': round(overall_attendance_rate, 1)
        },
        'trends': trends,
        'student_summaries': student_summaries,
        'time_analytics': time_analytics,
        'generated_at': datetime.now()
    }
    
    return report_data

# Enhanced Analytics Routes
@app.route('/analytics')
@login_required
def analytics_dashboard():
    """Enhanced analytics dashboard with advanced visualizations"""
    
    # Get filter parameters
    days = int(request.args.get('days', 30))
    class_id = request.args.get('class_id', 'all')
    
    # Get all classes for filter dropdown
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    
    # Calculate analytics data using inline functions to avoid import issues
    trends_data = calculate_attendance_trends_inline(days, class_id)
    student_summaries = get_student_attendance_summary_inline(class_id, days)
    class_comparison = get_class_comparison_data_inline(days)
    time_analytics = get_time_based_analytics_inline(class_id, days)
    predictive_insights = get_predictive_insights_inline(class_id)
    
    # Prepare chart data for frontend
    chart_data = {
        'trends': trends_data,
        'student_performance': [
            {
                'name': s['student'].name,
                'attendance_rate': s['attendance_rate'],
                'risk_level': s['risk_level']
            } for s in student_summaries[:20]  # Top 20 for chart
        ],
        'class_comparison': class_comparison,
        'day_analysis': time_analytics['day_analysis'],
        'hour_analysis': time_analytics['hour_analysis'][:10]  # Top 10 hours
    }
    
    return render_template('analytics_dashboard.html',
                         trends_data=trends_data,
                         student_summaries=student_summaries,
                         class_comparison=class_comparison,
                         time_analytics=time_analytics,
                         predictive_insights=predictive_insights,
                         chart_data=chart_data,
                         classes=classes,
                         selected_days=days,
                         selected_class_id=class_id)

@app.route('/analytics/report')
@login_required
def generate_report():
    """Generate detailed attendance report"""
    
    # Get parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    class_id = request.args.get('class_id', 'all')
    format_type = request.args.get('format', 'html')
    
    # Default to last 30 days if no dates provided
    if not start_date_str or not end_date_str:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('analytics_dashboard'))
    
    # Generate report using inline function
    report_data = generate_attendance_report_inline(start_date, end_date, class_id)
    
    if format_type == 'json':
        return Response(
            json.dumps(report_data, default=str, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename=attendance_report_{start_date}_{end_date}.json'}
        )
    else:
        # HTML format
        classes = Class.query.filter_by(teacher_id=current_user.id).all()
        return render_template('analytics_report.html',
                             report_data=report_data,
                             classes=classes,
                             selected_class_id=class_id)

@app.route('/analytics/export/csv')
@login_required
def export_csv():
    """Export attendance data as CSV"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    class_id = request.args.get('class_id', 'all')
    
    # Default to last 30 days
    if not start_date_str or not end_date_str:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Query attendance data
    query = db.session.query(
        Attendance, Student, Class
    ).join(
        Student, Attendance.student_id == Student.id
    ).join(
        Class, Attendance.class_id == Class.id
    ).filter(
        Class.teacher_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if class_id != 'all':
        query = query.filter(Class.id == class_id)
    
    records = query.all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date', 'Student Name', 'Student Number', 'Class', 
        'Status', 'Scan Time', 'Late Minutes', 'Notes'
    ])
    
    # Write data
    for attendance, student, class_obj in records:
        writer.writerow([
            attendance.date.strftime('%Y-%m-%d'),
            student.name,
            student.student_number,
            class_obj.name,
            attendance.status,
            attendance.scan_time.strftime('%H:%M:%S') if attendance.scan_time else '',
            attendance.late_minutes or 0,
            attendance.notes or ''
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_export_{start_date}_{end_date}.csv'}
    )

@app.route('/api/analytics/trends')
@login_required
def api_trends():
    """API endpoint for trend data (for AJAX charts)"""
    days = int(request.args.get('days', 30))
    class_id = request.args.get('class_id', 'all')
    
    trends = calculate_attendance_trends_inline(days, class_id)
    
    return {
        'success': True,
        'data': trends
    }

@app.route('/api/analytics/students')
@login_required
def api_student_analytics():
    """API endpoint for student performance data"""
    days = int(request.args.get('days', 30))
    class_id = request.args.get('class_id', 'all')
    
    summaries = get_student_attendance_summary_inline(class_id, days)
    
    # Convert to JSON-serializable format
    data = []
    for summary in summaries:
        data.append({
            'student_id': summary['student'].id,
            'student_name': summary['student'].name,
            'student_number': summary['student'].student_number,
            'attendance_rate': summary['attendance_rate'],
            'total_days': summary['total_days'],
            'present_count': summary['present_count'],
            'late_count': summary['late_count'],
            'absent_count': summary['absent_count'],
            'risk_level': summary['risk_level']
        })
    
    return {
        'success': True,
        'data': data
    }

if __name__ == '__main__':
    if not os.path.exists('attendance.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True) 