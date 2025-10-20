from app import app, db, Attendance, ExcuseRequest, Student
from sqlalchemy import inspect

with app.app_context():
    # Check if excuse_request_id column exists in Attendance table
    inspector = inspect(db.engine)
    columns = inspector.get_columns('attendance')
    print('Attendance table columns:')
    for col in columns:
        print(f'  {col["name"]} - {col["type"]}')
    
    # Check if there are any approved excuse requests without linked attendance
    print('\nApproved excuse requests:')
    approved = ExcuseRequest.query.filter_by(status='Approved').all()
    for req in approved:
        attendance = Attendance.query.filter_by(
            student_id=req.student_id,
            class_id=req.class_id, 
            date=req.absence_date
        ).first()
        print(f'  Request {req.id}: Student {req.student.name}, Date {req.absence_date}')
        if attendance:
            print(f'    Attendance ID: {attendance.id}, Status: {attendance.status}, Excuse Request ID: {attendance.excuse_request_id}')
        else:
            print('    No attendance record found')
    
    # Check all attendance records for Brady Beloso on 2025-09-14
    print('\nAll attendance records for Brady Beloso on 2025-09-14:')
    from datetime import date
    target_date = date(2025, 9, 14)
    brady_attendance = Attendance.query.join(Student).filter(
        Student.name == 'Brady Beloso',
        Attendance.date == target_date
    ).all()
    
    for att in brady_attendance:
        print(f'  Attendance ID: {att.id}, Student ID: {att.student_id}, Status: {att.status}, Excuse Request ID: {att.excuse_request_id}')