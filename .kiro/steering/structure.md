# Project Structure

## Root Directory Layout

```
├── app.py                    # Main Flask application with all routes and models
├── requirements.txt          # Python dependencies
├── package.json             # Node.js dependencies for React frontend
├── instance/                # SQLite database storage
│   └── attendance.db        # Main database file
├── templates/               # Jinja2 HTML templates
├── static/                  # Static assets (CSS, JS, images, uploads)
├── src/                     # React application source
├── migrations/              # Database migration files (Alembic)
├── test_*.py               # Test scripts
└── manage_*.html           # Standalone HTML files
```

## Key Directories

### `/templates/` - Flask Templates

- `base.html` - Main layout template with navigation
- `login_base.html` - Authentication layout
- `dashboard.html` - Main dashboard with analytics
- `*_students.html` - Student management pages
- `*_class*.html` - Class management pages
- `attendance.html` - Attendance tracking interface
- `excuse_*.html` - Excuse request handling

### `/static/` - Static Assets

- `css/` - Custom stylesheets
- `js/` - JavaScript files
- `libs/` - Third-party libraries (Bootstrap, FontAwesome)
- `photos/` - Student photo uploads
- `excuse_letters/` - Excuse documentation uploads
- `qr/` - Generated QR codes
- `fonts/` - Custom fonts

### `/src/` - React Frontend

- `App.js` - Main React application
- `index.js` - React entry point
- Components appear to be for pet adoption system (separate from attendance)

## Architecture Patterns

### Single-File Flask App

- All models, routes, and logic in `app.py`
- Monolithic structure for simplicity
- Database models defined inline with routes

### Template Inheritance

- `base.html` provides common layout
- `login_base.html` for authentication pages
- Child templates extend base layouts

### Static File Organization

- Vendor libraries in `/static/libs/`
- Custom assets in respective `/static/` subdirectories
- Upload directories auto-created by application

### Database Schema

- **Teacher**: User authentication and class ownership
- **Class**: Class definitions with time schedules
- **Student**: Student records with QR codes and photos
- **Attendance**: Daily attendance records with status tracking
- **ExcuseRequest**: Absence excuse workflow with file attachments

## File Naming Conventions

- Templates: lowercase with underscores (`add_student.html`)
- Static files: organized by type in subdirectories
- Python files: snake_case
- Test files: prefixed with `test_`
- Database utilities: descriptive names (`check_db.py`, `fix_data.py`)

## Development Workflow

1. Main application logic in `app.py`
2. Templates in `/templates/` with Bootstrap styling
3. Static assets served from `/static/`
4. Database operations through SQLAlchemy ORM
5. File uploads handled with Werkzeug security
