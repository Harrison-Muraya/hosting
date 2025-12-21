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
from rest_framework.routers import DefaultRouter
from core.views import *
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Hosting Automation API",
        default_version='v1',
        description="API for hosting automation platform",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/register/', register, name='register'),
    path('api/login/', login, name='login'),
    path('api/webhooks/mpesa/', mpesa_callback, name='mpesa_callback'),
    path('api/webhooks/paypal/', paypal_webhook, name='paypal_webhook'),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api_docs'),
    path('', include('dashboard.urls')),
]
