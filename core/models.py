from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta

class User(AbstractUser):
    phone_number = models.CharField(max_length=20, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Fix the groups and user_permissions clash
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    
    class Meta:
        db_table = 'users'

class Plan(models.Model):
    PLAN_TYPES = [
        ('vps', 'VPS'),
        ('shared', 'Shared Hosting'),
        ('dedicated', 'Dedicated Server'),
    ]
    
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    cpu_cores = models.IntegerField()
    ram_mb = models.IntegerField()
    disk_gb = models.IntegerField()
    bandwidth_gb = models.IntegerField()
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_quarterly = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_annually = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def ram_display(self):
        """Display RAM in GB or MB"""
        if self.ram_mb >= 1024:
            gb = self.ram_mb / 1024
            # Remove .0 if it's a whole number
            return f"{gb:.0f} GB" if gb == int(gb) else f"{gb:.1f} GB"
        return f"{self.ram_mb} MB"
    
    class Meta:
        db_table = 'plans'
    
    def __str__(self):
        return f"{self.name} - ${self.price_monthly}/mo"

class Service(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ]
    
    BILLING_CYCLES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='services')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLES, default='monthly')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    next_due_date = models.DateTimeField()
    domain = models.CharField(max_length=255, blank=True)
    vm_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'services'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
    def calculate_next_due_date(self):
        if self.billing_cycle == 'monthly':
            return timezone.now() + timedelta(days=30)
        elif self.billing_cycle == 'quarterly':
            return timezone.now() + timedelta(days=90)
        elif self.billing_cycle == 'annually':
            return timezone.now() + timedelta(days=365)
        return timezone.now() + timedelta(days=30)