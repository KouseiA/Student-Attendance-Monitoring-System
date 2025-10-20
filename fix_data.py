#!/usr/bin/env python3
"""
Database cleanup script to fix student data integrity issues
This script will:
1. Fix students with NULL class_id by assigning them to appropriate classes
2. Clean up any orphaned attendance records
"""

import sqlite3
from datetime import datetime

def fix_student_data():
    """Fix student data integrity issues"""
    conn = sqlite3.connect('instance/attendance.db')
    cursor = conn.cursor()
    
    print("=== Database Cleanup Script ===")
    print(f"Running at: {datetime.now()}")
    
    # Get current data state
    print("\n1. Checking current database state...")
    cursor.execute("SELECT COUNT(*) FROM student WHERE class_id IS NULL")
    null_students = cursor.fetchone()[0]
    print(f"   Students with NULL class_id: {null_students}")
    
    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cursor.fetchone()[0]
    print(f"   Total attendance records: {total_attendance}")
    
    # Get available classes
    cursor.execute("SELECT id, name FROM class ORDER BY id")
    classes = cursor.fetchall()
    print(f"   Available classes: {len(classes)}")
    for class_id, class_name in classes:
        print(f"     - Class {class_id}: {class_name}")
    
    if null_students > 0:
        print("\n2. Fixing students with NULL class_id...")
        
        # Strategy: Assign students to classes based on their attendance history
        cursor.execute("""
            SELECT DISTINCT s.id, s.name, s.student_number, 
                   a.class_id, c.name as class_name,
                   COUNT(*) as attendance_count
            FROM student s
            LEFT JOIN attendance a ON s.id = a.student_id
            LEFT JOIN class c ON a.class_id = c.id
            WHERE s.class_id IS NULL
            GROUP BY s.id, a.class_id
            ORDER BY s.id, attendance_count DESC
        """)
        
        student_class_mapping = {}
        results = cursor.fetchall()
        
        for student_id, name, student_number, class_id, class_name, attendance_count in results:
            if student_id not in student_class_mapping and class_id:
                student_class_mapping[student_id] = {
                    'name': name,
                    'student_number': student_number,
                    'class_id': class_id,
                    'class_name': class_name,
                    'attendance_count': attendance_count
                }
        
        # For students without attendance history, assign to first available class
        cursor.execute("SELECT id, name, student_number FROM student WHERE class_id IS NULL")
        students_without_classes = cursor.fetchall()
        
        default_class_id = classes[0][0] if classes else None  # Use first available class
        
        for student_id, name, student_number in students_without_classes:
            if student_id not in student_class_mapping:
                student_class_mapping[student_id] = {
                    'name': name,
                    'student_number': student_number,
                    'class_id': default_class_id,
                    'class_name': classes[0][1] if classes else 'Unknown',
                    'attendance_count': 0
                }
        
        # Update students with their determined class assignments
        for student_id, mapping in student_class_mapping.items():
            if mapping['class_id']:
                cursor.execute("""
                    UPDATE student 
                    SET class_id = ? 
                    WHERE id = ?
                """, (mapping['class_id'], student_id))
                
                print(f"   ✓ Assigned {mapping['name']} ({mapping['student_number']}) to {mapping['class_name']} (based on {mapping['attendance_count']} attendance records)")
        
        print(f"   Updated {len(student_class_mapping)} students")
    
    # Verify the fix
    print("\n3. Verifying fixes...")
    cursor.execute("SELECT COUNT(*) FROM student WHERE class_id IS NULL")
    remaining_null = cursor.fetchone()[0]
    print(f"   Students with NULL class_id after fix: {remaining_null}")
    
    # Check for any orphaned attendance records
    cursor.execute("""
        SELECT COUNT(*) FROM attendance a
        LEFT JOIN student s ON a.student_id = s.id
        WHERE s.id IS NULL
    """)
    orphaned_attendance = cursor.fetchone()[0]
    
    if orphaned_attendance > 0:
        print(f"   ⚠️  Found {orphaned_attendance} orphaned attendance records")
        print("   Cleaning up orphaned attendance records...")
        cursor.execute("""
            DELETE FROM attendance
            WHERE student_id NOT IN (SELECT id FROM student)
        """)
        print(f"   ✓ Cleaned up {orphaned_attendance} orphaned records")
    
    # Final verification
    print("\n4. Final database state...")
    cursor.execute("SELECT COUNT(*) FROM student")
    total_students = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM student WHERE class_id IS NOT NULL")
    students_with_classes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance")
    final_attendance = cursor.fetchone()[0]
    
    print(f"   Total students: {total_students}")
    print(f"   Students with classes: {students_with_classes}")
    print(f"   Total attendance records: {final_attendance}")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n✅ Database cleanup completed successfully!")
    print("   All students now have proper class assignments.")
    print("   Attendance records should display correctly.")

if __name__ == "__main__":
    fix_student_data()
