# Stock Management System

Enterprise-grade stock management system for technicians, built with Django 5 and designed for multinational deployment.

## 🚀 Features

### Core Functionality
- **Multi-language Support**: French (Belgium), Dutch (Belgium), English
- **Role-based Access**: Administrator and Technician roles
- **Article Management**: Unique references, QR code generation, category management
- **Stock Tracking**: Per-technician stock levels with thresholds and alerts
- **Cart System**: Unique cart per technician with aggregation
- **Demand Workflow**: Submission → Approval → Preparation → Handover → Closure
- **Usage Declaration**: Real-time stock usage tracking with location data
- **QR Code Scanning**: PWA-enabled camera scanning with ZXing
- **Digital Handover**: PIN or digital signature confirmation

### Technical Features
- **Security**: OWASP ASVS Level 1/2 compliance
- **Audit Trail**: Immutable audit logging with hash chaining
- **Concurrency**: Transaction safety with select_for_update
- **PWA**: Offline-first Progressive Web Application
- **API**: RESTful API with OpenAPI documentation
- **Scalability**: Celery-based background processing
- **Monitoring**: Health checks and metrics ready

## 🏗 Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PWA Frontend  │    │   REST API      │    │   Admin Panel   │
│   (Templates)   │◄──►│   (DRF)         │◄──►│   (Django)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Django Backend                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │    Users    │ │  Inventory  │ │   Orders    │ │    Audit    ││
│  │   Service   │ │   Service   │ │   Service   │ │   Service   ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │     Celery      │
│   (Database)    │    │     (Cache)     │    │   (Workers)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠 Technology Stack

- **Backend**: Django 5.0, Django REST Framework
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7
- **Task Queue**: Celery with Redis broker
- **Frontend**: Server-side templates + Progressive Web App
- **QR Scanning**: ZXing library
- **PDF Generation**: ReportLab
- **Deployment**: Docker & Docker Compose
- **Security**: OWASP compliant middleware
- **Monitoring**: Built-in health checks

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Make (optional, for convenience commands)

### Development Setup

1. **Clone and Configure**
   ```bash
   git clone <repository-url>
   cd stock-project
   make setup-dev  # Creates .env from template
   ```

2. **Edit Environment Variables**
   ```bash
   # Edit .env file with your configuration
   vim .env
   ```

3. **Start Services**
   ```bash
   make up          # Start all services
   make migrate     # Run database migrations
   make superuser   # Create admin user
   make seed        # Load sample data (optional)
   ```

4. **Access the Application**
   - **PWA Interface**: http://localhost:8000/app/
   - **Admin Panel**: http://localhost:8000/admin/
   - **API Documentation**: http://localhost:8000/api/docs/
   - **Health Check**: http://localhost:8000/health/

### Production Deployment

1. **Setup Production Environment**
   ```bash
   make setup-prod
   # Edit .env for production settings
   ```

2. **Deploy**
   ```bash
   make prod-up
   ```

## 📱 PWA Features

The application includes a Progressive Web App with:

- **Offline Support**: Service worker for offline functionality
- **Camera Access**: QR code scanning using device camera
- **Install Prompt**: Native app-like installation
- **Responsive Design**: Works on mobile and desktop
- **Push Notifications**: Ready for push notification integration

### QR Code Scanning
- Open PWA at `/app/scan/`
- Allow camera permissions
- Point camera at QR codes on articles
- Quick actions: Add to cart or declare usage

## 🔐 Security Features

### OWASP ASVS Compliance
- **Authentication**: JWT tokens with secure headers
- **Authorization**: Role-based permissions
- **Session Management**: Secure cookies and CSRF protection
- **Input Validation**: Strict serializer validation
- **Audit Logging**: Immutable event trails
- **Rate Limiting**: API throttling
- **Security Headers**: Content Security Policy, HSTS, etc.

### Data Protection
- **GDPR Ready**: Data export and retention policies
- **Encryption**: PIN codes hashed with PBKDF2
- **Audit Chain**: SHA-256 hash chaining for integrity
- **SQL Injection**: Django ORM protection
- **XSS Protection**: Template auto-escaping

## 📊 API Documentation

### Authentication
```bash
# Login
POST /api/auth/login/
{
  "username": "your_username",
  "password": "your_password"
}

# Use returned token in headers
Authorization: Bearer <access_token>
```

### Key Endpoints
- `GET /api/articles/` - List articles
- `GET /api/my/stock/` - Get technician stock
- `POST /api/my/cart/add/` - Add to cart
- `POST /api/my/cart/submit/` - Submit cart as demand
- `GET /api/demandes/` - List demands
- `POST /api/use/` - Declare stock usage

Full API documentation available at `/api/docs/`

## 🧪 Testing

```bash
# Run all tests with coverage
make test

# Run specific test categories
docker-compose exec web python -m pytest tests/unit/
docker-compose exec web python -m pytest tests/integration/
docker-compose exec web python -m pytest tests/e2e/

# Generate coverage report
make test
# View coverage: htmlcov/index.html
```

## 🔧 Development Commands

```bash
# Development
make up              # Start development environment
make down            # Stop all services
make shell           # Django shell
make logs            # View logs
make logs SERVICE=web # View specific service logs

# Database
make migrate         # Run migrations
make superuser       # Create superuser
make seed           # Load sample data
make db-shell       # PostgreSQL shell

# Code Quality
make lint           # Run linting (ruff, mypy)
make format         # Format code (black)
make test           # Run tests with coverage
make qa             # Run all quality checks

# Translations
make makemessages   # Extract translatable strings
make compilemessages # Compile translations

# Production
make prod-up        # Start production environment
make backup         # Backup database and media
make restore BACKUP_FILE=backup.sql # Restore backup
```

## 🗂 Project Structure

```
stock-project/
├── apps/
│   ├── core/           # Core functionality and middleware
│   ├── users/          # User management and profiles
│   ├── inventory/      # Articles, stock, thresholds
│   ├── orders/         # Carts, demands, workflow
│   ├── audit/          # Audit trail and logging
│   ├── pwa/            # Progressive Web App
│   └── api/            # REST API endpoints
├── config/             # Django configuration
│   ├── settings/       # Environment-specific settings
│   ├── urls.py         # URL routing
│   └── celery.py       # Celery configuration
├── templates/          # Django templates
├── static/             # Static files (CSS, JS)
├── locale/             # Translations (fr-BE, nl-BE, en)
├── tests/              # Test suites
├── infra/              # Infrastructure files
├── docker-compose.yml  # Container orchestration
├── Dockerfile          # Container definition
├── Makefile           # Development commands
└── requirements.txt    # Python dependencies
```

## 🌐 Internationalization

The application supports three languages:
- **fr-BE**: French (Belgium) - Default
- **nl-BE**: Dutch (Belgium)
- **en**: English

### Adding New Languages
1. Add language code to `settings/base.py`
2. Create translation directory: `locale/<lang_code>/LC_MESSAGES/`
3. Extract messages: `make makemessages`
4. Translate strings in `django.po` files
5. Compile: `make compilemessages`

## 🔧 Configuration

### Environment Variables

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://stock_user:password@db:5432/stock_db

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Internationalization
LANGUAGE_CODE=fr-be
TIME_ZONE=Europe/Brussels

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Email (Production)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password

# GDPR
DATA_RETENTION_DAYS=2555
```

## 📋 User Roles

### Administrator
- Manage articles and users
- Approve/refuse demands
- Prepare orders for handover
- Complete handovers with PIN/signature
- Access all system features
- View audit trails

### Technician
- Scan QR codes
- Manage personal cart
- Submit demands
- Declare stock usage
- View personal stock levels
- Track demand status

## 🚨 Monitoring & Health Checks

### Health Check Endpoints
- `/health/` - Overall system health
- `/health/ready/` - Readiness probe
- `/health/live/` - Liveness probe

### Monitoring Commands
```bash
make monitor         # Check system status
make celery-status   # Check Celery workers
docker-compose ps    # Service status
```

## 🛡 Security Considerations

### Production Checklist
- [ ] Change default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure proper ALLOWED_HOSTS
- [ ] Set up SSL certificates
- [ ] Configure email backend
- [ ] Set strong database passwords
- [ ] Enable firewall rules
- [ ] Set up backup strategy
- [ ] Configure monitoring
- [ ] Review CORS settings

### Security Headers
The application automatically sets:
- Content-Security-Policy
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- HSTS headers (production)

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
   ```bash
   make down && make up
   # Wait for database to be ready
   ```

2. **Permission Denied**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER .
   ```

3. **Port Already in Use**
   ```bash
   # Change port in docker-compose.yml or stop conflicting service
   docker-compose ps
   ```

4. **Migration Issues**
   ```bash
   # Reset database (DEV ONLY)
   make db-reset
   ```

### Logs
```bash
# View all logs
make logs

# View specific service logs
make logs SERVICE=web
make logs SERVICE=worker
make logs SERVICE=db
```

## 📄 License

This project is proprietary software. All rights reserved.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks: `make qa`
5. Submit a pull request

## 📞 Support

For technical support or questions:
- Check the troubleshooting section
- Review logs: `make logs`
- Open an issue with detailed information

---

**Stock Management System v1.0** - Enterprise-grade stock management for multinational deployment.
