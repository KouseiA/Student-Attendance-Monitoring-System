# Technology Stack

## Backend

- **Framework**: Flask (Python web framework)
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: Flask-Login with password hashing
- **File Uploads**: Werkzeug for secure file handling
- **QR Code Generation**: qrcode library with Pillow for image processing
- **Database Migrations**: Alembic (Flask-Migrate integration available but commented out)

## Frontend

- **Primary**: Jinja2 templates with Bootstrap 5.3.1
- **Secondary**: React 18.2.0 application (separate pet adoption system)
- **Styling**: Bootstrap CSS framework with FontAwesome icons
- **JavaScript**: Vanilla JS for interactive features

## Key Dependencies

```
Flask
Flask-Login
Flask-SQLAlchemy
qrcode
Pillow
Werkzeug
```

## Common Commands

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask development server
python app.py

# Run React development server (if working on frontend)
npm start

# Build React for production
npm run build
```

### Database Management

```bash
# Initialize database (run Python shell)
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Check database contents
python check_db.py
python check_db2.py

# Fix data issues
python fix_data.py
```

### Testing

```bash
# Run test files
python test_excuse.py
python test_expiration.py
python test_workflow.py
```

## Configuration Notes

- SQLite database stored in `instance/attendance.db`
- File uploads go to `static/photos/` and `static/excuse_letters/`
- Session timeout set to 15 minutes
- Max file upload size: 16MB
- Allowed image extensions: png, jpg, jpeg, gif
