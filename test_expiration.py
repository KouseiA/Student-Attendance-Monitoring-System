from app import app, db, Attendance, ExcuseRequest, Student, Class, auto_expire_pending_excuses
from datetime import date, datetime, timedelta

with app.app_context():
    print("=== Testing 7-Day Excuse Request Expiration ===")
    
    # Create a test excuse request that's 8 days old (should expire)
    student = Student.query.first()
    class_obj = Class.query.first()
    
    if student and class_obj:
        # Create an old request (8 days ago)
        old_date = datetime.now() - timedelta(days=8)
        test_date = date.today() - timedelta(days=8)
        
        # Check if test request already exists
        existing = ExcuseRequest.query.filter_by(
            student_id=student.id,
            absence_date=test_date
        ).first()
        
        if not existing:
            # Create old excuse request
            old_request = ExcuseRequest(
                student_id=student.id,
                class_id=class_obj.id,
                teacher_id=class_obj.teacher_id or 1,
                absence_date=test_date,
                reason="Test request - should expire automatically",
                status='Pending',
                submitted_at=old_date
            )
            db.session.add(old_request)
            
            # Create corresponding attendance record
            old_attendance = Attendance(
                student_id=student.id,
                class_id=class_obj.id,
                teacher_id=class_obj.teacher_id or 1,
                date=test_date,
                scan_time=datetime.now().time(),
                status='Excused',
                excuse_request_id=None,  # Will be set after commit
                notes="Test excuse - should become absent after 7 days"
            )
            db.session.add(old_attendance)
            db.session.commit()
            
            # Link them
            old_attendance.excuse_request_id = old_request.id
            db.session.commit()
            
            print(f"Created test excuse request ID {old_request.id} (8 days old)")
            print(f"Created test attendance record ID {old_attendance.id} (Excused status)")
        else:
            print(f"Test request already exists: ID {existing.id}")
            old_request = existing
            old_attendance = Attendance.query.filter_by(
                student_id=student.id,
                date=test_date
            ).first()
        
        # Show current status
        print(f"\nBefore expiration:")
        print(f"  Excuse Request: ID {old_request.id}, Status: {old_request.status}")
        if old_attendance:
            print(f"  Attendance: ID {old_attendance.id}, Status: {old_attendance.status}")
        
        # Run expiration check
        print(f"\nRunning auto_expire_pending_excuses()...")
        expired_count = auto_expire_pending_excuses()
        print(f"Expired {expired_count} requests")
        
        # Refresh objects and show new status
        db.session.refresh(old_request)
        if old_attendance:
            db.session.refresh(old_attendance)
        
        print(f"\nAfter expiration:")
        print(f"  Excuse Request: ID {old_request.id}, Status: {old_request.status}")
        print(f"  Teacher Notes: {old_request.teacher_notes}")
        if old_attendance:
            print(f"  Attendance: ID {old_attendance.id}, Status: {old_attendance.status}")
            print(f"  Notes: {old_attendance.notes}")
        
        print(f"\n=== Expected Behavior ===")
        print(f"- Old pending requests (>7 days) → Status becomes 'Disapproved'")
        print(f"- Attendance status changes from 'Excused' → 'Absent'")
        print(f"- Auto-added teacher notes about expiration")
        print(f"- This runs automatically when dashboard is accessed")
        
    else:
        print("No student or class found for testing")