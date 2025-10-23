# BetterBundle Admin Dashboard

⚠️ **CRITICAL REQUIREMENT**: Django should NEVER create tables!

## Important Notes

### Table Creation Policy

- **ONLY** the Python worker creates database tables
- Django models are for **READING ONLY** from existing tables
- Django should **NEVER** run migrations that create tables
- All tables are created by the Python worker using SQLAlchemy

### Configuration

- `MIGRATION_MODULES = DisableMigrations()` - Disables all migrations
- `DATABASE_ROUTERS = [NoCreateTablesRouter()]` - Prevents table creation
- Django only creates auth tables (user, session, etc.)

### Commands

- `python manage.py verify_no_tables` - Verify Django won't create tables
- `python manage.py check_db` - Check database connection and existing tables
- `python manage.py create_admin_user` - Create admin user

### Environment Variables

- `PORT` - Server port (default: 8001)
- `HOST` - Server host (default: 127.0.0.1)
- Database credentials from `.env.dev`

### Usage

1. Ensure Python worker has created all tables first
2. Run Django admin dashboard
3. Django will only read from existing tables
4. Never run `python manage.py migrate` or `python manage.py makemigrations`

## Architecture

- **Python Worker**: Creates all business tables using SQLAlchemy
- **Django Admin**: Reads from existing tables, provides admin interface
- **Separation**: No coupling between services
