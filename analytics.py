"""
Enhanced Analytics Module for Attendance System
Provides advanced reporting and visualization capabilities
"""

from datetime import datetime, date, timedelta
from collections import defaultdict, Counter
from sqlalchemy import func, and_, or_
import json

def calculate_attendance_trends(db, current_user, days=30, class_id=None):
    """Calculate attendance trends over specified period"""
    from app import Attendance, Student, Class, ExcuseRequest
    
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

def get_student_attendance_summary(db, current_user, class_id=None, days=30):
    """Get detailed attendance summary per student"""
    from app import Attendance, Student, Class
    
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
            'risk_level': calculate_risk_level(attendance_rate, absent_count, late_count)
        })
    
    return sorted(student_summaries, key=lambda x: x['attendance_rate'])

def calculate_risk_level(attendance_rate, absent_count, late_count):
    """Calculate student risk level based on attendance patterns"""
    if attendance_rate < 70 or absent_count > 5:
        return 'high'
    elif attendance_rate < 85 or absent_count > 3 or late_count > 5:
        return 'medium'
    else:
        return 'low'

def get_class_comparison_data(db, current_user, days=30):
    """Compare attendance across different classes"""
    from app import Attendance, Class
    
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

def get_time_based_analytics(db, current_user, class_id=None, days=30):
    """Analyze attendance patterns by time of day and day of week"""
    from app import Attendance, Class
    
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

def generate_attendance_report(db, current_user, start_date, end_date, class_id=None, format_type='summary'):
    """Generate comprehensive attendance report"""
    from app import Attendance, Student, Class, ExcuseRequest
    
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
    trends = calculate_attendance_trends(db, current_user, days_diff, class_id)
    
    # Get student summaries
    student_summaries = get_student_attendance_summary(db, current_user, class_id, days_diff)
    
    # Get time-based analytics
    time_analytics = get_time_based_analytics(db, current_user, class_id, days_diff)
    
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

def get_predictive_insights(db, current_user, class_id=None):
    """Generate predictive insights based on attendance patterns"""
    from app import Attendance, Student, Class
    
    # Get recent 60 days of data for analysis
    end_date = date.today()
    start_date = end_date - timedelta(days=60)
    
    student_summaries = get_student_attendance_summary(db, current_user, class_id, 60)
    
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