## Automatic Reminders - Setup & Troubleshooting Guide

### Issues Fixed:
1. **Missing Imports** - Added `smtplib` and `EmailMessage` imports that are required for sending email reminders
2. **Improved Logging** - Added better logging to help troubleshoot scheduler issues

### How Automatic Reminders Work:
- The scheduler runs in the background and checks for users who need reminders
- It sends reminders every X hours (configurable via `REMINDER_INTERVAL_HOURS` env var, default: 1 hour)
- Reminders are only sent to users who have NOT logged in today
- Each user's reminder is sent at most once per configured interval

### Requirements for Reminders to Work:

1. **Environment Variables** (in .env file):
   ```
   AUTO_REMINDERS_ENABLED=true
   REMINDER_INTERVAL_HOURS=1
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

2. **User Setup**:
   - User must have a valid email address in their profile
   - User must have enabled reminders (is_enabled = 1 in reminders table)
   - User must have a student profile created
   - User must NOT have logged in today

3. **Email Configuration**:
   - For Gmail: Use an App Password (2FA must be enabled)
   - For other providers: Use SMTP credentials
   - SMTP_USER and SMTP_PASSWORD must be set

### Verification Steps:

1. Check if scheduler is running:
   ```
   python test_scheduler.py
   ```

2. Ensure .env file has:
   - AUTO_REMINDERS_ENABLED=true
   - Valid SMTP_USER and SMTP_PASSWORD

3. Check database for users with reminders:
   ```sql
   SELECT * FROM users;
   SELECT * FROM reminders WHERE is_enabled = 1;
   ```

4. Monitor logs in console/terminal when app is running
   - You should see "Scheduler: Started successfully" on startup
   - You should see "Running automatic background reminders..." every X hours
   - You should see "Sent automatic reminder to..." if emails are sent

### Common Issues & Solutions:

**Issue**: "Scheduler: AUTO_REMINDERS_ENABLED is disabled"
- Solution: Set AUTO_REMINDERS_ENABLED=true in .env file

**Issue**: No reminders being sent
- Check if SMTP_USER and SMTP_PASSWORD are configured
- Ensure users have valid email addresses
- Ensure users haven't logged in today
- Check if is_enabled = 1 for reminders in database

**Issue**: "Error sending email"
- Verify SMTP credentials are correct
- Ensure Gmail 2FA is enabled and using App Password
- Check firewall/network isn't blocking SMTP

### Test Sending a Manual Reminder:

You can test email sending by creating a test script:
```python
from study import send_email_reminder
success = send_email_reminder(
    user_id=1,
    recipient='test@example.com',
    subject='Test Subject',
    topic='Test topic',
    minutes=60,
    full_name='Test User'
)
print(f"Email sent: {success}")
```
