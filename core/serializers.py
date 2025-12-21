from rest_framework import serializers
from core.models import User, Plan, Service
from payments.models import Transaction, Invoice

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                  'phone_number', 'balance', 'is_verified', 'created_at']
        read_only_fields = ['balance', 'is_verified', 'created_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'phone_number']
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

class ServiceSerializer(serializers.ModelSerializer):
    plan_details = PlanSerializer(source='plan', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['vm_id', 'ip_address', 'username', 'password', 
                            'created_at', 'activated_at', 'suspended_at', 'terminated_at']

class TransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['transaction_id', 'status', 'completed_at', 'created_at']

class InvoiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.plan.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['invoice_number', 'created_at', 'paid_at']