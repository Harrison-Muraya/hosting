"""
URL configuration for hosting project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core import views as core_views
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from core.admin_views import AdminPlanViewSet, bulk_activate_plans, bulk_deactivate_plans, duplicate_plan


# Swagger/API Documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Hosting Automation API",
        default_version='v1',
        description="Complete API for hosting automation platform",
        contact=openapi.Contact(email="support@hostpro.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# REST Framework Router for public APIs
router = DefaultRouter()
router.register(r'plans', core_views.PlanViewSet, basename='plan')
router.register(r'services', core_views.ServiceViewSet, basename='service')
router.register(r'transactions', core_views.TransactionViewSet, basename='transaction')
router.register(r'invoices', core_views.InvoiceViewSet, basename='invoice')

# Admin Router
admin_router = DefaultRouter()
admin_router.register(r'plans', AdminPlanViewSet, basename='admin-plan')

urlpatterns = [
    # Django Admin - This should come AFTER your custom admin routes
    path('admin/', admin.site.urls),
    
    # API Routes
    path('api/', include(router.urls)),
    
    # Authentication API
    path('api/register/', core_views.register, name='api_register'),
    path('api/login/', core_views.login, name='api_login'),
    path('api/logout/', core_views.logout, name='api_logout'),
    path('api/profile/', core_views.user_profile, name='api_user_profile'),
    path('api/profile/update/', core_views.update_profile, name='api_update_profile'),
    path('api/change-password/', core_views.change_password, name='api_change_password'),
    
    # Admin API Routes
    path('api/admin/', include(admin_router.urls)),
    path('api/admin/plans/bulk-activate/', bulk_activate_plans, name='bulk_activate_plans'),
    path('api/admin/plans/bulk-deactivate/', bulk_deactivate_plans, name='bulk_deactivate_plans'),
    path('api/admin/plans/<int:plan_id>/duplicate/', duplicate_plan, name='duplicate_plan'),
    
    # Webhooks
    path('api/webhooks/mpesa/', core_views.mpesa_callback, name='mpesa_callback'),
    path('api/webhooks/paypal/', core_views.paypal_webhook, name='paypal_webhook'),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api_docs'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='api_redoc'),
    
    # Dashboard/Frontend Views - This should come LAST
    path('', include('dashboard.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)