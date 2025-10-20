"""
Demo Data Generator for Testing Enhanced Analytics
Run this script to populate your database with sample attendance data
"""

from app import app, db, Teacher, Class, Student, Attendance, ExcuseRequest
from datetime import datetime, date, time, timedelta
import random
from werkzeug.security import generate_password_hash

def generate_demo_data():
    """Generate comprehensive demo data for testing analytics"""
    
    with app.app_context():
        print("🚀 Generating demo data for analytics testing...")
        
        # Create demo teacher if not exists
        teacher = Teacher.query.filter_by(username='demo_teacher').first()
        if not teacher:
            teacher = Teacher(
                username='demo_teacher',
                password=generate_password_hash('demo123')
            )
            db.session.add(teacher)
            db.session.commit()
            print("✅ Created demo teacher (username: demo_teacher, password: demo123)")
        
        # Create demo classes
        classes_data = [
            {'name': 'Mathematics 101', 'start_time': time(8, 0), 'end_time': time(9, 30)},
            {'name': 'Science Lab', 'start_time': time(10, 0), 'end_time': time(11, 30)},
            {'name': 'English Literature', 'start_time': time(13, 0), 'end_time': time(14, 30)},
            {'name': 'History Class', 'start_time': time(15, 0), 'end_time': time(16, 30)}
        ]
        
        demo_classes = []
        for class_data in classes_data:
            existing_class = Class.query.filter_by(
                name=class_data['name'], 
                teacher_id=teacher.id
            ).first()
            
            if not existing_class:
                demo_class = Class(
                    name=class_data['name'],
                    teacher_id=teacher.id,
                    start_time=class_data['start_time'],
                    end_time=class_data['end_time']
                )
                db.session.add(demo_class)
                demo_classes.append(demo_class)
            else:
                demo_classes.append(existing_class)
        
        db.session.commit()
        print(f"✅ Created {len(demo_classes)} demo classes")
        
        # Create demo students
        student_names = [
            'Alice Johnson', 'Bob Smith', 'Charlie Brown', 'Diana Prince',
            'Edward Norton', 'Fiona Green', 'George Wilson', 'Hannah Davis',
            'Ian Mitchell', 'Julia Roberts', 'Kevin Hart', 'Luna Lovegood',
            'Michael Jordan', 'Nina Simone', 'Oscar Wilde', 'Penny Lane',
            'Quincy Jones', 'Rachel Green', 'Samuel Jackson', 'Tina Turner',
            'Uma Thurman', 'Victor Hugo', 'Wendy Williams', 'Xavier Woods',
            'Yara Shahidi', 'Zoe Saldana', 'Aaron Paul', 'Bella Swan',
            'Carlos Santana', 'Demi Moore'
        ]
        
        demo_students = []
        for i, name in enumerate(student_names):
            student_number = f"STU{2024}{i+1:03d}"
            existing_student = Student.query.filter_by(student_number=student_number).first()
            
            if not existing_student:
                # Randomly assign to a class
                assigned_class = random.choice(demo_classes)
                
                student = Student(
                    name=name,
                    student_number=student_number,
                    class_id=assigned_class.id,
                    qr_code_path=f'static/qr/{student_number}.png'
                )
                db.session.add(student)
                demo_students.append(student)
            else:
                demo_students.append(existing_student)
        
        db.session.commit()
        print(f"✅ Created {len(demo_students)} demo students")
        
        # Generate attendance data for the last 60 days
        end_date = date.today()
        start_date = end_date - timedelta(days=60)
        
        attendance_count = 0
        excuse_count = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Skip weekends for more realistic data
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                
                for demo_class in demo_classes:
                    # Get students for this class
                    class_students = [s for s in demo_students if s.class_id == demo_class.id]
                    
                    for student in class_students:
                        # Skip some students randomly to create varied attendance patterns
                        if random.random() < 0.15:  # 15% chance to skip
                            continue
                        
                        # Check if attendance already exists
                        existing = Attendance.query.filter_by(
                            student_id=student.id,
                            class_id=demo_class.id,
                            date=current_date
                        ).first()
                        
                        if existing:
                            continue
                        
                        # Generate realistic attendance patterns
                        attendance_probability = random.random()
                        
                        if attendance_probability < 0.75:  # 75% present
                            status = 'Present'
                            scan_time = demo_class.start_time
                            late_minutes = 0
                            late_arrival = False
                            
                        elif attendance_probability < 0.85:  # 10% late
                            status = 'Late'
                            # Random late arrival (5-30 minutes)
                            late_minutes = random.randint(5, 30)
                            start_datetime = datetime.combine(current_date, demo_class.start_time)
                            late_datetime = start_datetime + timedelta(minutes=late_minutes)
                            scan_time = late_datetime.time()
                            late_arrival = True
                            
                        elif attendance_probability < 0.95:  # 10% absent
                            status = 'Absent'
                            scan_time = demo_class.end_time
                            late_minutes = 0
                            late_arrival = False
                            
                        else:  # 5% excused
                            status = 'Excused'
                            scan_time = demo_class.start_time
                            late_minutes = 0
                            late_arrival = False
                            
                            # Create excuse request
                            excuse_reasons = [
                                'Medical appointment',
                                'Family emergency',
                                'Illness',
                                'School event',
                                'Transportation issue'
                            ]
                            
                            excuse_request = ExcuseRequest(
                                student_id=student.id,
                                class_id=demo_class.id,
                                teacher_id=teacher.id,
                                absence_date=current_date,
                                reason=random.choice(excuse_reasons),
                                status=random.choice(['Pending', 'Approved', 'Disapproved']),
                                submitted_at=datetime.combine(current_date, time(7, 0))
                            )
                            db.session.add(excuse_request)
                            excuse_count += 1
                        
                        # Create attendance record
                        attendance = Attendance(
                            student_id=student.id,
                            class_id=demo_class.id,
                            teacher_id=teacher.id,
                            date=current_date,
                            scan_time=scan_time,
                            status=status,
                            late_arrival=late_arrival,
                            late_minutes=late_minutes,
                            notes=f"Demo data - {status.lower()}"
                        )
                        db.session.add(attendance)
                        attendance_count += 1
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        print(f"✅ Generated {attendance_count} attendance records")
        print(f"✅ Generated {excuse_count} excuse requests")
        
        # Generate some specific patterns for testing
        print("\n🎯 Creating specific test patterns...")
        
        # Create a high-risk student (poor attendance)
        if demo_students:
            risk_student = demo_students[0]
            recent_dates = [end_date - timedelta(days=i) for i in range(1, 8)]
            
            for test_date in recent_dates:
                if test_date.weekday() < 5:  # Weekday
                    existing = Attendance.query.filter_by(
                        student_id=risk_student.id,
                        date=test_date
                    ).first()
                    
                    if not existing:
                        attendance = Attendance(
                            student_id=risk_student.id,
                            class_id=risk_student.class_id,
                            teacher_id=teacher.id,
                            date=test_date,
                            scan_time=time(8, 0),
                            status='Absent',
                            notes="High-risk pattern for testing"
                        )
                        db.session.add(attendance)
            
            print(f"✅ Created high-risk pattern for {risk_student.name}")
        
        # Create a perfect attendance student
        if len(demo_students) > 1:
            perfect_student = demo_students[1]
            recent_dates = [end_date - timedelta(days=i) for i in range(1, 15)]
            
            for test_date in recent_dates:
                if test_date.weekday() < 5:  # Weekday
                    existing = Attendance.query.filter_by(
                        student_id=perfect_student.id,
                        date=test_date
                    ).first()
                    
                    if not existing:
                        attendance = Attendance(
                            student_id=perfect_student.id,
                            class_id=perfect_student.class_id,
                            teacher_id=teacher.id,
                            date=test_date,
                            scan_time=time(7, 55),  # Early arrival
                            status='Present',
                            notes="Perfect attendance for testing"
                        )
                        db.session.add(attendance)
            
            print(f"✅ Created perfect attendance pattern for {perfect_student.name}")
        
        db.session.commit()
        
        print("\n🎉 Demo data generation complete!")
        print("\n📊 Summary:")
        print(f"   • Teacher: demo_teacher (password: demo123)")
        print(f"   • Classes: {len(demo_classes)}")
        print(f"   • Students: {len(demo_students)}")
        print(f"   • Attendance Records: {attendance_count}")
        print(f"   • Excuse Requests: {excuse_count}")
        print(f"   • Date Range: {start_date} to {end_date}")
        
        print("\n🚀 You can now:")
        print("   1. Login with demo_teacher / demo123")
        print("   2. Visit the Enhanced Analytics dashboard")
        print("   3. Explore different time periods and filters")
        print("   4. Generate detailed reports")

if __name__ == '__main__':
    generate_demo_data()