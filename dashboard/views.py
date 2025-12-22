from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Sum
from django.db import models
from core.models import Service, Plan, User
from payments.models import Invoice, Transaction

def home(request):
    plans = Plan.objects.filter(is_active=True)
    return render(request, 'home.html', {'plans': plans})

def register_page(request):
    """Registration page"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    return render(request, 'auth/register.html')

def login_page(request):
    """Login page"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    return render(request, 'auth/login.html')


@login_required
def user_dashboard(request):
    services = Service.objects.filter(user=request.user)
    all_invoices = Invoice.objects.filter(user=request.user)
    invoices = all_invoices.order_by('-created_at')[:5]
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'services': services,
        'invoices': invoices,
        'transactions': transactions,
        'active_services': services.filter(status='active').count(),
        'pending_invoices': all_invoices.filter(status='unpaid').count(),
    }
    return render(request, 'dashboard/user_dashboard.html', context)

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    total_services = Service.objects.count()
    active_services = Service.objects.filter(status='active').count()
    total_revenue = Transaction.objects.filter(status='completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    pending_invoices = Invoice.objects.filter(status='unpaid').count()
    
    recent_services = Service.objects.order_by('-created_at')[:10]
    recent_transactions = Transaction.objects.order_by('-created_at')[:10]
    
    context = {
        'total_services': total_services,
        'active_services': active_services,
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'recent_services': recent_services,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
def services_list(request):
    """List all services"""
    services = Service.objects.filter(user=request.user).select_related('plan')
    return render(request, 'dashboard/services.html', {'services': services})

@login_required
def invoices_list(request):
    """List all invoices"""
    invoices = Invoice.objects.filter(user=request.user).select_related('service').order_by('-created_at')
    return render(request, 'dashboard/invoices.html', {'invoices': invoices})

@login_required
def transactions_list(request):
    """List all transactions"""
    transactions = Transaction.objects.filter(user=request.user).select_related('service').order_by('-created_at')
    return render(request, 'dashboard/transactions.html', {'transactions': transactions})

@login_required
def profile(request):
    """User profile page"""
    return render(request, 'dashboard/profile.html')


def plans_page(request):
    """Plans listing page"""
    plans = Plan.objects.filter(is_active=True)
    return render(request, 'plans.html', {'plans': plans})
