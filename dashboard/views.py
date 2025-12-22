from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from core.models import Service, Plan, User
from payments.models import Invoice, Transaction

def home(request):
    """Home page with plans"""
    plans = Plan.objects.filter(is_active=True)
    return render(request, 'home.html', {'plans': plans})

def register_page(request):
    """Registration page"""
    # If already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    return render(request, 'auth/register.html')

def login_page(request):
    """Login page"""
    # If already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    return render(request, 'auth/login.html')

@login_required(login_url='/auth/login/')
def user_dashboard(request):
    """User dashboard - requires login"""
    services = Service.objects.filter(user=request.user)
    invoices = Invoice.objects.filter(user=request.user).order_by('-created_at')[:5]
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'services': services,
        'invoices': invoices,
        'transactions': transactions,
        'active_services': services.filter(status='active').count(),
        'pending_invoices': Invoice.objects.filter(user=request.user, status='unpaid').count(),
    }
    return render(request, 'dashboard/user_dashboard.html', context)

@login_required(login_url='/auth/login/')
def admin_dashboard(request):
    """Admin dashboard - requires staff permission"""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('user_dashboard')
    
    total_services = Service.objects.count()
    active_services = Service.objects.filter(status='active').count()
    total_revenue = Transaction.objects.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    pending_invoices = Invoice.objects.filter(status='unpaid').count()
    active_users = User.objects.filter(is_active=True).count()
    
    recent_services = Service.objects.select_related('user', 'plan').order_by('-created_at')[:10]
    recent_transactions = Transaction.objects.select_related('user').order_by('-created_at')[:10]
    
    context = {
        'total_services': total_services,
        'active_services': active_services,
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'active_users': active_users,
        'recent_services': recent_services,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required(login_url='/auth/login/')
def services_list(request):
    """List all services"""
    services = Service.objects.filter(user=request.user).select_related('plan')
    return render(request, 'dashboard/services.html', {'services': services})

@login_required(login_url='/auth/login/')
def invoices_list(request):
    """List all invoices"""
    invoices = Invoice.objects.filter(user=request.user).select_related('service').order_by('-created_at')
    return render(request, 'dashboard/invoices.html', {'invoices': invoices})

@login_required(login_url='/auth/login/')
def transactions_list(request):
    """List all transactions"""
    transactions = Transaction.objects.filter(user=request.user).select_related('service').order_by('-created_at')
    return render(request, 'dashboard/transactions.html', {'transactions': transactions})

@login_required(login_url='/auth/login/')
def profile(request):
    """User profile page"""
    return render(request, 'dashboard/profile.html')

def plans_page(request):
    """Plans listing page - public"""
    plans = Plan.objects.filter(is_active=True)
    return render(request, 'plans.html', {'plans': plans})
