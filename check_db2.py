from app import app, db, Attendance, ExcuseRequest, Student
from datetime import date

with app.app_context():
    # Check if there's an excuse request for Brady Beloso on 2025-09-14
    target_date = date(2025, 9, 14)
    brady_excuse = ExcuseRequest.query.join(Student).filter(
        Student.name == 'Brady Beloso',
        ExcuseRequest.absence_date == target_date
    ).first()
    
    if brady_excuse:
        print(f'Found excuse request for 2025-09-14: ID {brady_excuse.id}, Status: {brady_excuse.status}')
    else:
        print('No excuse request found for Brady Beloso on 2025-09-14')
    
    # Check all excuse requests for Brady Beloso
    print('\nAll excuse requests for Brady Beloso:')
    all_brady_excuses = ExcuseRequest.query.join(Student).filter(
        Student.name == 'Brady Beloso'
    ).all()
    
    for req in all_brady_excuses:
        print(f'  Request {req.id}: Date {req.absence_date}, Status: {req.status}')