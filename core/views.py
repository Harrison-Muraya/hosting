from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login as django_login, logout as django_logout, get_user_model
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from core.models import Plan, Service
from payments.models import Transaction, Invoice
from core.serializers import *
from payments.mpesa import MPesaClient
from payments.paypal import PayPalClient
from core.tasks import create_vm_task, reactivate_service_task, send_welcome_email
import uuid

User = get_user_model()

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_exempt
def register(request):
    """
    Register a new user with automatic login
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        
        # Log the user in with Django session
        django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Send welcome email (async)
        send_welcome_email.delay(user.id)
        
        return Response({
            'success': True,
            'message': 'Registration successful! Welcome to our platform.',
            'token': token.key,
            'user': UserSerializer(user).data,
            'redirect_url': '/dashboard/'
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_exempt
def login(request):
    """
    Login user with Django session
    """
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    
    user = authenticate(request, username=username, password=password)
    
    if user:
        # Log the user in with Django session
        django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'success': True,
            'message': 'Login successful!',
            'token': token.key,
            'user': UserSerializer(user).data,
            'redirect_url': '/dashboard/'
        })
    
    return Response({
        'success': False,
        'message': 'Invalid credentials. Please check your username and password.'
    }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST', 'GET'])
@permission_classes([permissions.AllowAny])
def logout(request):
    """
    Logout user by deleting token and clearing session
    """
    try:
        if request.user.is_authenticated:
            # Delete token if exists
            if hasattr(request.user, 'auth_token'):
                request.user.auth_token.delete()
            
            # Django logout (clears session)
            django_logout(request)
        
        return Response({
            'success': True,
            'message': 'Successfully logged out.',
            'redirect_url': '/'
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    """Get current user profile"""
    serializer = UserSerializer(request.user)
    return Response({
        'success': True,
        'user': serializer.data
    })

@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_profile(request):
    """Update user profile"""
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'success': True,
            'message': 'Profile updated successfully!',
            'user': serializer.data
        })
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    """Change user password"""
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    if not user.check_password(serializer.validated_data['old_password']):
        return Response({
            'success': False,
            'message': 'Old password is incorrect.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.set_password(serializer.validated_data['new_password'])
    user.save()
    
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    
    return Response({
        'success': True,
        'message': 'Password changed successfully!',
        'token': token.key
    })

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing hosting plans
    GET /api/plans/ - List all active plans
    GET /api/plans/{id}/ - Get specific plan details
    """
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]  # Public endpoint

class ServiceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing services
    1. List user's services
    2. Create new service order
    3. Reactivate suspended service
    4. Get service credentials
    """
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see their own services, staff can see all"""
        if self.request.user.is_staff:
            return Service.objects.all()
        return Service.objects.filter(user=self.request.user)
    
    def create(self, request):
        """
        Create a new service order
        
        POST /api/services/
        {
            "plan_id": 1,
            "billing_cycle": "monthly",
            "domain": "example.com"  // optional
        }
        """
        plan_id = request.data.get('plan_id')
        billing_cycle = request.data.get('billing_cycle', 'monthly')
        domain = request.data.get('domain', '')
        
        # Validate plan
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({
                'error': 'Plan not found or is no longer available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate billing cycle
        if billing_cycle not in ['monthly', 'quarterly', 'annually']:
            return Response({
                'error': 'Invalid billing cycle. Choose: monthly, quarterly, or annually'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate price based on billing cycle
        if billing_cycle == 'quarterly':
            price = plan.price_quarterly if plan.price_quarterly else plan.price_monthly * 3
        elif billing_cycle == 'annually':
            price = plan.price_annually if plan.price_annually else plan.price_monthly * 12
        else:
            price = plan.price_monthly
        
        # Calculate next due date
        if billing_cycle == 'monthly':
            next_due = timezone.now() + timedelta(days=30)
        elif billing_cycle == 'quarterly':
            next_due = timezone.now() + timedelta(days=90)
        else:
            next_due = timezone.now() + timedelta(days=365)
        
        # Create service
        service = Service.objects.create(
            user=request.user,
            plan=plan,
            billing_cycle=billing_cycle,
            price=price,
            next_due_date=next_due,
            domain=domain,
            status='pending'
        )
        
        # Create invoice
        invoice = Invoice.objects.create(
            user=request.user,
            service=service,
            invoice_number=f'INV-{uuid.uuid4().hex[:8].upper()}',
            amount=price,
            due_date=timezone.now() + timedelta(days=7),
            description=f'New {plan.name} service - {billing_cycle} billing'
        )
        
        return Response({
            'success': True,
            'message': 'Service created successfully! Please proceed to payment.',
            'service': ServiceSerializer(service).data,
            'invoice': {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount': str(invoice.amount),
                'due_date': invoice.due_date.isoformat(),
                'status': invoice.status
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """
        Reactivate a suspended service
        
        POST /api/services/{id}/reactivate/
        """
        service = self.get_object()
        
        if service.status != 'suspended':
            return Response({
                'error': 'Service is not suspended'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for unpaid invoices
        unpaid_invoices = Invoice.objects.filter(
            service=service,
            status='unpaid'
        ).count()
        
        if unpaid_invoices > 0:
            return Response({
                'error': f'Please pay {unpaid_invoices} outstanding invoice(s) first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Trigger reactivation task
        from core.tasks import reactivate_service_task
        reactivate_service_task.delay(service.id)
        
        return Response({
            'success': True,
            'message': 'Service reactivation initiated. Your VM will be started shortly.'
        })
    
    @action(detail=True, methods=['get'])
    def credentials(self, request, pk=None):
        """
        Get service credentials (IP, username, password)
        
        GET /api/services/{id}/credentials/
        """
        service = self.get_object()
        
        if service.status != 'active':
            return Response({
                'error': 'Service must be active to view credentials'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'credentials': {
                'ip_address': service.ip_address,
                'username': service.username,
                'password': service.password,
                'ssh_command': f'ssh {service.username}@{service.ip_address}' if service.ip_address else None
            }
        })

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Transaction.objects.all()
        return Transaction.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def mpesa_payment(self, request):
        phone_number = request.data.get('phone_number')
        amount = request.data.get('amount')
        invoice_id = request.data.get('invoice_id')
        
        try:
            invoice = Invoice.objects.get(id=invoice_id, user=request.user)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, 
                            status=status.HTTP_404_NOT_FOUND)
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            service=invoice.service,
            transaction_id=f'MPESA-{uuid.uuid4().hex[:12].upper()}',
            payment_method='mpesa',
            amount=amount,
            description=f'Payment for {invoice.invoice_number}'
        )
        
        # Initiate M-Pesa STK push
        mpesa = MPesaClient()
        result = mpesa.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=invoice.invoice_number,
            transaction_desc=f'Payment for invoice {invoice.invoice_number}'
        )
        
        transaction.external_reference = result.get('CheckoutRequestID', '')
        transaction.metadata = result
        transaction.save()
        
        return Response({
            'transaction': TransactionSerializer(transaction).data,
            'mpesa_response': result
        })
    
    @action(detail=False, methods=['post'])
    def paypal_payment(self, request):
        amount = request.data.get('amount')
        invoice_id = request.data.get('invoice_id')
        return_url = request.data.get('return_url', '')
        cancel_url = request.data.get('cancel_url', '')
        
        try:
            invoice = Invoice.objects.get(id=invoice_id, user=request.user)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, 
                            status=status.HTTP_404_NOT_FOUND)
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            service=invoice.service,
            transaction_id=f'PAYPAL-{uuid.uuid4().hex[:12].upper()}',
            payment_method='paypal',
            amount=amount,
            description=f'Payment for {invoice.invoice_number}'
        )
        
        # Create PayPal order
        paypal = PayPalClient()
        result = paypal.create_order(
            amount=amount,
            return_url=return_url,
            cancel_url=cancel_url
        )
        
        transaction.external_reference = result.get('id', '')
        transaction.metadata = result
        transaction.save()
        
        return Response({
            'transaction': TransactionSerializer(transaction).data,
            'paypal_response': result
        })

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Invoice.objects.all()
        return Invoice.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def pay_with_balance(self, request, pk=None):
        invoice = self.get_object()
        
        if invoice.status == 'paid':
            return Response({'error': 'Invoice already paid'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        if request.user.balance < invoice.amount:
            return Response({'error': 'Insufficient balance'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Deduct from balance
        request.user.balance -= invoice.amount
        request.user.save()
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            service=invoice.service,
            transaction_id=f'BAL-{uuid.uuid4().hex[:12].upper()}',
            payment_method='balance',
            amount=invoice.amount,
            status='completed',
            description=f'Payment for {invoice.invoice_number}',
            completed_at=timezone.now()
        )
        
        # Update invoice
        invoice.status = 'paid'
        invoice.paid_at = timezone.now()
        invoice.transaction = transaction
        invoice.save()
        
        # If service is pending, create VM
        if invoice.service and invoice.service.status == 'pending':
            create_vm_task.delay(invoice.service.id)
        
        # If service is suspended, reactivate
        elif invoice.service and invoice.service.status == 'suspended':
            reactivate_service_task.delay(invoice.service.id)
        
        return Response({
            'message': 'Payment successful',
            'transaction': TransactionSerializer(transaction).data
        })
    
# Webhook handlers
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def mpesa_callback(request):
    """M-Pesa payment callback"""
    data = request.data
    checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
    
    try:
        transaction = Transaction.objects.get(external_reference=checkout_request_id)
        
        if result_code == 0:  # Success
            transaction.status = 'completed'
            transaction.completed_at = timezone.now()
            transaction.save()
            
            # Update invoice if exists
            if transaction.service:
                invoices = Invoice.objects.filter(
                    service=transaction.service,
                    status='unpaid',
                    amount=transaction.amount
                ).first()
                
                if invoices:
                    invoices.status = 'paid'
                    invoices.paid_at = timezone.now()
                    invoices.transaction = transaction
                    invoices.save()
                    
                    # Create or reactivate service
                    if transaction.service.status == 'pending':
                        create_vm_task.delay(transaction.service.id)
                    elif transaction.service.status == 'suspended':
                        reactivate_service_task.delay(transaction.service.id)
        else:
            transaction.status = 'failed'
            transaction.save()
    except Transaction.DoesNotExist:
        pass
    
    return Response({'ResultCode': 0, 'ResultDesc': 'Success'})

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def paypal_webhook(request):
    """PayPal payment webhook"""
    # In production, verify webhook signature
    event_type = request.data.get('event_type')
    resource = request.data.get('resource', {})
    
    if event_type == 'CHECKOUT.ORDER.APPROVED':
        order_id = resource.get('id')
        
        try:
            transaction = Transaction.objects.get(external_reference=order_id)
            
            # Capture payment
            paypal = PayPalClient()
            result = paypal.capture_order(order_id)
            
            if result.get('status') == 'COMPLETED':
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.metadata = result
                transaction.save()
                
                # Update invoice
                if transaction.service:
                    invoices = Invoice.objects.filter(
                        service=transaction.service,
                        status='unpaid',
                        amount=transaction.amount
                    ).first()
                    
                    if invoices:
                        invoices.status = 'paid'
                        invoices.paid_at = timezone.now()
                        invoices.transaction = transaction
                        invoices.save()
                        
                        # Create or reactivate service
                        if transaction.service.status == 'pending':
                            create_vm_task.delay(transaction.service.id)
                        elif transaction.service.status == 'suspended':
                            reactivate_service_task.delay(transaction.service.id)
        except Transaction.DoesNotExist:
            pass
    
    return Response({'status': 'success'})
