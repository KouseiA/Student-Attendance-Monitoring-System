from app import app, db, Attendance, ExcuseRequest, Student, Class
from datetime import date

with app.app_context():
    # Test scenario: Create an excuse request for Brady Beloso on 2025-09-14
    # Find Brady Beloso
    brady = Student.query.filter_by(name='Brady Beloso').first()
    if brady:
        print(f"Found student: {brady.name} (ID: {brady.id}, Class ID: {brady.class_id})")
        
        # Get a valid class for the request
        if brady.class_id:
            class_obj = Class.query.get(brady.class_id)
            teacher_id = class_obj.teacher_id if class_obj else 1
        else:
            # If Brady doesn't have a class, use the first available class
            class_obj = Class.query.first()
            teacher_id = class_obj.teacher_id if class_obj else 1
            print(f"Using class: {class_obj.name} (ID: {class_obj.id}) with teacher ID: {teacher_id}")
        
        # Check if there's already an excuse request for 2025-09-14
        target_date = date(2025, 9, 14)
        existing_request = ExcuseRequest.query.filter_by(
            student_id=brady.id,
            absence_date=target_date
        ).first()
        
        if existing_request:
            print(f"Excuse request already exists: ID {existing_request.id}, Status: {existing_request.status}")
        else:
            # Create a new excuse request for 2025-09-14
            new_request = ExcuseRequest(
                student_id=brady.id,
                class_id=brady.class_id or class_obj.id,
                teacher_id=teacher_id,
                absence_date=target_date,
                reason="Medical appointment - doctor's note attached",
                status='Pending'
            )
            db.session.add(new_request)
            db.session.commit()
            print(f"Created new excuse request: ID {new_request.id}")
        
        # Check current attendance record for 2025-09-14
        attendance = Attendance.query.filter_by(
            student_id=brady.id,
            date=target_date
        ).first()
        
        if attendance:
            print(f"Current attendance: ID {attendance.id}, Status: {attendance.status}, Excuse Request ID: {attendance.excuse_request_id}")
        else:
            print("No attendance record found for 2025-09-14")
    else:
        print("Brady Beloso not found")