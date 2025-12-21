from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.utils import timezone
from core.models import User, Plan, Service
from payments.models import Transaction, Invoice
from core.serializers import *
from payments.mpesa import MPesaClient
from payments.paypal import PayPalClient
from core.tasks import create_vm_task, reactivate_service_task
import uuid

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Service.objects.all()
        return Service.objects.filter(user=self.request.user)
    
    def create(self, request):
        plan_id = request.data.get('plan_id')
        billing_cycle = request.data.get('billing_cycle', 'monthly')
        
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate price based on billing cycle
        if billing_cycle == 'quarterly':
            price = plan.price_quarterly or plan.price_monthly * 3
        elif billing_cycle == 'annually':
            price = plan.price_annually or plan.price_monthly * 12
        else:
            price = plan.price_monthly
        
        # Create service
        service = Service.objects.create(
            user=request.user,
            plan=plan,
            billing_cycle=billing_cycle,
            price=price,
            next_due_date=timezone.now() + timezone.timedelta(days=30),
            status='pending'
        )
        
        # Create invoice
        invoice = Invoice.objects.create(
            user=request.user,
            service=service,
            invoice_number=f'INV-{uuid.uuid4().hex[:8].upper()}',
            amount=price,
            due_date=timezone.now() + timezone.timedelta(days=7),
            description=f'New {plan.name} service'
        )
        
        return Response({
            'service': ServiceSerializer(service).data,
            'invoice': InvoiceSerializer(invoice).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        service = self.get_object()
        
        if service.status != 'suspended':
            return Response({'error': 'Service is not suspended'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user has paid
        unpaid_invoices = Invoice.objects.filter(
            service=service,
            status='unpaid'
        ).count()
        
        if unpaid_invoices > 0:
            return Response({'error': 'Please pay outstanding invoices first'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        reactivate_service_task.delay(service.id)
        return Response({'message': 'Service reactivation initiated'})

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
