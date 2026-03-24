#!/usr/bin/env python3
"""Test script to verify scheduler and reminder functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variables for testing
os.environ['AUTO_REMINDERS_ENABLED'] = 'true'
os.environ['REMINDER_INTERVAL_HOURS'] = '1'
os.environ['SMTP_USER'] = 'test@gmail.com'
os.environ['SMTP_PASSWORD'] = 'test_password'
os.environ['SECRET_KEY'] = 'test-secret-key'

print("Testing imports...")
try:
    import smtplib
    from email.message import EmailMessage
    print("✓ smtplib and EmailMessage imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

print("\nTesting Flask app and scheduler imports...")
try:
    from study import app, start_scheduler, send_all_automatic_reminders, send_email_reminder
    print("✓ Successfully imported Flask app and scheduler functions")
except Exception as e:
    print(f"✗ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nVerifying send_email_reminder function signature...")
import inspect
sig = inspect.signature(send_email_reminder)
print(f"✓ Function parameters: {list(sig.parameters.keys())}")

print("\n✓ All imports and basic checks passed!")
print("\nNote: Scheduler will only run when:")
print("  1. AUTO_REMINDERS_ENABLED env var is set to 'true'")
print("  2. SMTP_USER and SMTP_PASSWORD are configured")
print("  3. Users have email addresses and reminders enabled")
print("  4. App is running (not in debug reload mode)")
