from app import app, db, Attendance, ExcuseRequest, Student, Class
from datetime import date

with app.app_context():
    # Test the new workflow: Submit excuse request without manual attendance
    print("=== Testing New Excuse Request Workflow ===")
    
    # Get a student and class for testing
    student = Student.query.first()
    class_obj = Class.query.first()
    
    if student and class_obj:
        test_date = date(2025, 9, 15)  # Use a new date for testing
        
        print(f"Student: {student.name} (ID: {student.id})")
        print(f"Class: {class_obj.name} (ID: {class_obj.id})")
        print(f"Test Date: {test_date}")
        
        # Check if there's already an excuse request for this date
        existing_request = ExcuseRequest.query.filter_by(
            student_id=student.id,
            class_id=class_obj.id,
            absence_date=test_date
        ).first()
        
        if existing_request:
            print(f"Excuse request already exists: ID {existing_request.id}")
        else:
            print("No existing excuse request found - this is perfect for testing!")
        
        # Check if there's already an attendance record
        existing_attendance = Attendance.query.filter_by(
            student_id=student.id,
            class_id=class_obj.id,
            date=test_date
        ).first()
        
        if existing_attendance:
            print(f"Attendance record already exists: ID {existing_attendance.id}, Status: {existing_attendance.status}")
        else:
            print("No existing attendance record - new one will be created automatically!")
            
        print("\n=== What will happen when excuse request is submitted ===")
        print("1. Excuse request will be created with 'Pending' status")
        print("2. Attendance record will be automatically created as 'Excused'")
        print("3. The two records will be linked via excuse_request_id")
        print("4. UI will show 'Pending Review' badge (yellow)")
        print("5. When approved → 'Approved Request' (green)")
        print("6. When disapproved → 'Excuse Denied' (red) + status changes to 'Absent'")
        
    else:
        print("No student or class found for testing")