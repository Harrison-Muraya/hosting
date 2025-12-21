# Django Hosting Automation Platform

Complete hosting automation platform with VM management, automated billing, M-Pesa and PayPal integration.

## Features

- ✅ Complete REST API with Django REST Framework
- ✅ Automated VM creation with Proxmox integration
- ✅ M-Pesa and PayPal payment integration
- ✅ Celery tasks for background processing
- ✅ Daily renewal checks and automatic suspension
- ✅ Email notifications for all events
- ✅ User dashboard with TailwindCSS
- ✅ Admin dashboard with analytics
- ✅ Service lifecycle management (create, suspend, reactivate, terminate)

## Setup Instructions

### 1. Clone and Install

```bash
git clone <your-repo>
cd hosting-platform
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run Development Server

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A hosting worker -l info

# Terminal 3: Celery Beat (for scheduled tasks)
celery -A hosting beat -l info
```

### 5. Docker Setup (Alternative)

```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## API Endpoints

### Authentication
- POST `/api/register/` - Register new user
- POST `/api/login/` - Login and get token

### Plans
- GET `/api/plans/` - List all plans

### Services
- GET `/api/services/` - List user's services
- POST `/api/services/` - Create new service
- POST `/api/services/{id}/reactivate/` - Reactivate suspended service

### Transactions
- GET `/api/transactions/` - List transactions
- POST `/api/transactions/mpesa_payment/` - Initiate M-Pesa payment
- POST `/api/transactions/paypal_payment/` - Create PayPal order

### Invoices
- GET `/api/invoices/` - List invoices
- POST `/api/invoices/{id}/pay_with_balance/` - Pay with account balance

### Webhooks
- POST `/api/webhooks/mpesa/` - M-Pesa callback
- POST `/api/webhooks/paypal/` - PayPal webhook

## Celery Tasks

- `create_vm_task` - Create VM for new service
- `check_service_renewals` - Daily check for renewals (runs at midnight)
- `suspend_service_task` - Suspend service for non-payment
- `reactivate_service_task` - Reactivate paid service
- `terminate_service_task` - Permanently delete service
- `check_suspended_services` - Auto-terminate services suspended >7 days (every 6 hours)

## Dashboard URLs

- `/` - Home page with plans
- `/dashboard/` - User dashboard
- `/admin-dashboard/` - Admin dashboard (staff only)
- `/api/docs/` - Swagger API documentation

## Payment Integration

### M-Pesa Setup
1. Get API credentials from Safaricom Daraja
2. Configure callback URL
3. Set environment variables

### PayPal Setup
1. Create PayPal developer account
2. Get client ID and secret
3. Configure webhook URL

## Proxmox Integration

The system integrates with Proxmox VE for VM management:
- Automatic VM creation with specified resources
- VM start/stop operations
- VM deletion on termination
- IP address retrieval

## Security Notes

- Always use HTTPS in production
- Keep SECRET_KEY secure
- Use environment variables for sensitive data
- Implement rate limiting for APIs
- Verify webhook signatures
- Use strong passwords for Proxmox

## License

MIT License