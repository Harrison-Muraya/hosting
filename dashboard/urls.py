from django.urls import path
from dashboard import views
from core import admin_views

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('plans/', views.plans_page, name='plans'),
    
    # Authentication pages
    path('auth/register/', views.register_page, name='register_page'),
    path('auth/login/', views.login_page, name='login_page'),
    
    # Dashboard pages (require authentication)
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('dashboard/services/', views.services_list, name='services_list'),
    path('dashboard/invoices/', views.invoices_list, name='invoices_list'),
    path('dashboard/transactions/', views.transactions_list, name='transactions_list'),
    path('dashboard/profile/', views.profile, name='profile'),
    
    # Admin dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Admin Plans Management - Use different path to avoid conflict
    path('admin-dashboard/plans/', admin_views.admin_plans_page, name='admin_plans'),
]
