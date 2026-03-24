#!/usr/bin/env python3
"""
Quick Verification Script for Activity Logging Fix
Run this after applying all fixes to verify data consistency
"""

import sqlite3
from datetime import datetime

DB_PATH = 'studycoach.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def verify_teacher_mapping():
    """Check if new students have proper teacher mappings"""
    print("\n" + "="*80)
    print("VERIFICATION STEP 1: Check Teacher Mappings for New Students")
    print("="*80)
    
    conn = get_db_connection()
    
    # Get last 5 created students
    students = conn.execute('''
        SELECT id, username, standard, section 
        FROM users 
        WHERE role IN ('student', 'college_student')
        ORDER BY id DESC 
        LIMIT 5
    ''').fetchall()
    
    print(f"\n📋 Found {len(students)} recent students\n")
    
    for student in students:
        sid = student['id']
        username = student['username']
        standard = student['standard']
        section = student['section']
        
        # Check students table
        student_row = conn.execute(
            'SELECT class_id, teacher_id FROM students WHERE student_id = ? LIMIT 1',
            (sid,)
        ).fetchone()
        
        # Check teacher_students assignment
        assignment = conn.execute(
            'SELECT teacher_id, assigned_at FROM teacher_students WHERE student_id = ? LIMIT 1',
            (sid,)
        ).fetchone()
        
        status = "✅ OK" if (student_row and student_row['teacher_id']) or assignment else "❌ MISSING"
        print(f"{status} {username:20s} | {standard:5s} | {section:5s} | teacher_id={student_row['teacher_id'] if student_row else 'NULL'}")
    
    conn.close()

def verify_activity_logging():
    """Check if activities have proper teacher_id"""
    print("\n" + "="*80)
    print("VERIFICATION STEP 2: Check Activity Records Have teacher_id")
    print("="*80)
    
    conn = get_db_connection()
    
    # Check recent activities
    activities = conn.execute('''
        SELECT a.id, a.student_id, a.action, a.teacher_id, a.timestamp,
               u.username, CASE WHEN a.teacher_id IS NULL THEN 'NULL' ELSE 'OK' END as status
        FROM activities a
        JOIN users u ON u.id = a.student_id
        ORDER BY a.timestamp DESC 
        LIMIT 10
    ''').fetchall()
    
    null_count = sum(1 for a in activities if a['teacher_id'] is None)
    
    print(f"\n📋 Found {len(activities)} recent activities | NULL teacher_id: {null_count}\n")
    
    for act in activities:
        status = "❌ NULL" if act['teacher_id'] is None else "✅ OK"
        print(f"{status} | {act['username']:20s} | {act['action']:20s} | teacher_id={act['teacher_id']} | {act['timestamp']}")
    
    conn.close()

def verify_exam_attempts():
    """Check if exam_attempts have proper teacher_id"""
    print("\n" + "="*80)
    print("VERIFICATION STEP 3: Check Exam Attempts Have teacher_id")
    print("="*80)
    
    conn = get_db_connection()
    
    exam_attempts = conn.execute('''
        SELECT ea.id, ea.student_id, ea.subject, ea.score, ea.teacher_id, 
               COALESCE(ea.timestamp, ea.submitted_at) as timestamp,
               u.username
        FROM exam_attempts ea
        JOIN users u ON u.id = ea.student_id
        ORDER BY COALESCE(ea.timestamp, ea.submitted_at) DESC 
        LIMIT 10
    ''').fetchall()
    
    null_count = sum(1 for e in exam_attempts if e['teacher_id'] is None)
    
    print(f"\n📋 Found {len(exam_attempts)} exam attempts | NULL teacher_id: {null_count}\n")
    
    for exam in exam_attempts:
        status = "❌ NULL" if exam['teacher_id'] is None else "✅ OK"
        print(f"{status} | {exam['username']:20s} | {exam['subject']:20s} | {exam['score']} | teacher_id={exam['teacher_id']}")
    
    conn.close()

def verify_teacher_dashboard_visibility():
    """Check if activities are visible via JOIN queries (dashboard's new logic)"""
    print("\n" + "="*80)
    print("VERIFICATION STEP 4: Test Teacher Dashboard Query (JOIN Method)")
    print("="*80)
    
    conn = get_db_connection()
    
    # Get a teacher with students
    teacher = conn.execute('''
        SELECT u.id, u.username, u.assigned_standard, u.assigned_section
        FROM users u
        WHERE u.role = 'teacher'
        LIMIT 1
    ''').fetchone()
    
    if not teacher:
        print("\n⚠️  No teacher found in database. Cannot test dashboard visibility.")
        conn.close()
        return
    
    teacher_id = teacher['id']
    print(f"\n🏫 Testing teacher: {teacher['username']} (ID: {teacher_id})")
    
    # New query method (with JOINs)
    activities = conn.execute('''
        SELECT a.id, a.student_id, a.action, a.subject, a.timestamp,
               u.username AS student_name
        FROM activities a
        JOIN users u ON u.id = a.student_id
        JOIN students s ON s.student_id = a.student_id
        JOIN teacher_students ts ON ts.student_id = s.student_id AND ts.teacher_id = ?
        WHERE ts.teacher_id = ?
        ORDER BY a.timestamp DESC 
        LIMIT 10
    ''', (teacher_id, teacher_id)).fetchall()
    
    print(f"\n📊 Activities visible to this teacher via JOIN query: {len(activities)}")
    
    if activities:
        print("\nVisible activities:\n")
        for act in activities:
            print(f"  ✅ {act['student_name']:20s} | {act['action']:20s} | {act['timestamp']}")
    else:
        print("\n⚠️  No activities visible (teacher may have no assigned students)")
    
    # Also show exam attempts
    exams = conn.execute('''
        SELECT ea.id, ea.student_id, ea.subject, ea.score, 
               COALESCE(ea.timestamp, ea.submitted_at) as timestamp,
               u.username AS student_name
        FROM exam_attempts ea
        JOIN users u ON u.id = ea.student_id
        JOIN students s ON s.student_id = ea.student_id
        JOIN teacher_students ts ON ts.student_id = s.student_id AND ts.teacher_id = ?
        WHERE ts.teacher_id = ?
        ORDER BY COALESCE(ea.timestamp, ea.submitted_at) DESC 
        LIMIT 10
    ''', (teacher_id, teacher_id)).fetchall()
    
    print(f"\n📊 Exam attempts visible to this teacher via JOIN query: {len(exams)}")
    
    if exams:
        print("\nVisible exam attempts:\n")
        for exam in exams:
            print(f"  ✅ {exam['student_name']:20s} | {exam['subject']:20s} | Score: {exam['score']}")
    
    conn.close()

def generate_summary():
    """Generate a summary report"""
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    conn = get_db_connection()
    
    total_activities = conn.execute('SELECT COUNT(*) as cnt FROM activities').fetchone()['cnt']
    null_activities = conn.execute('SELECT COUNT(*) as cnt FROM activities WHERE teacher_id IS NULL').fetchone()['cnt']
    
    total_exams = conn.execute('SELECT COUNT(*) as cnt FROM exam_attempts').fetchone()['cnt']
    null_exams = conn.execute('SELECT COUNT(*) as cnt FROM exam_attempts WHERE teacher_id IS NULL').fetchone()['cnt']
    
    total_students = conn.execute('SELECT COUNT(*) as cnt FROM users WHERE role IN ("student", "college_student")').fetchone()['cnt']
    mapped_students = conn.execute('SELECT COUNT(DISTINCT student_id) as cnt FROM teacher_students').fetchone()['cnt']
    
    conn.close()
    
    print(f"\n📊 Database Statistics:\n")
    print(f"  Students: {total_students} total | {mapped_students} assigned to teachers")
    print(f"  Activities: {total_activities} total | {null_activities} with NULL teacher_id ({100*null_activities//max(1,total_activities)}%)")
    print(f"  Exams: {total_exams} total | {null_exams} with NULL teacher_id ({100*null_exams//max(1,total_exams)}%)")
    
    if null_activities == 0 and null_exams == 0:
        print(f"\n✅ ALL DATA INTEGRITY CHECKS PASSED!")
        print(f"   No records with NULL teacher_id - new student activities WILL be visible in dashboard")
    else:
        print(f"\n⚠️  WARNING: Found {null_activities + null_exams} records with NULL teacher_id")
        print(f"   These records may not be visible in teacher dashboard")
        print(f"   Run the fix again or check teacher assignment for affected students")

if __name__ == '__main__':
    print("\n🔍 ACTIVITY LOGGING FIX - VERIFICATION SCRIPT")
    print("This script verifies that all fixes have been applied correctly\n")
    
    try:
        verify_teacher_mapping()
        verify_activity_logging()
        verify_exam_attempts()
        verify_teacher_dashboard_visibility()
        generate_summary()
        
        print("\n" + "="*80)
        print("✅ VERIFICATION COMPLETE")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\n❌ Error during verification: {e}\n")
        import traceback
        traceback.print_exc()

"""
HOW TO RUN:
  python3 verify_fixes.py

EXPECTED OUTPUT FOR FIXED SYSTEM:
  ✅ OK  | newstudent1              | 11    | A     | teacher_id=2
  ✅ OK  | student1                 | login               | teacher_id=2
  ✅ OK  | newstudent1              | Mathematics         | 15    | teacher_id=2
  ✅ ALL DATA INTEGRITY CHECKS PASSED!

RED FLAGS (if you see these, more debugging needed):
  ❌ NULL | newstudent1              | 11    | A     | teacher_id=NULL  <- Teacher not assigned
  ❌ NULL | student1                 | login               | teacher_id=NULL  <- Activity not logged
  ⚠️  WARNING: Found 5 records with NULL teacher_id  <- Old records need backfill
"""
