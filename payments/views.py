from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from payments.models import Transaction, Invoice
from core.models import Service
from payments.mpesa import MPesaClient
from payments.paypal import PayPalClient
from core.serializers import TransactionSerializer, InvoiceSerializer
from core.tasks import create_vm_task, send_service_credentials_email
import uuid

# Invoice Payment Page View
@login_required
def invoice_payment_page(request, invoice_id):
    """Render invoice payment page"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    context = {
        'invoice': invoice,
        'now': timezone.now()
    }
    return render(request, 'dashboard/invoice_payment.html', context)

# Account Balance Payment

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_invoice_with_balance(request, invoice_id):
    """
    Pay invoice using account balance
    
    POST /api/invoices/{invoice_id}/pay_with_balance/
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Invoice not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if already paid
    if invoice.status == 'paid':
        return Response({
            'success': False,
            'message': 'Invoice already paid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check balance
    if request.user.balance < invoice.amount:
        return Response({
            'success': False,
            'message': f'Insufficient balance. You need ${invoice.amount - request.user.balance} more.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Process payment
    try:
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
            description=f'Payment for invoice {invoice.invoice_number}',
            completed_at=timezone.now()
        )
        
        # Update invoice
        invoice.status = 'paid'
        invoice.paid_at = timezone.now()
        invoice.transaction = transaction
        invoice.save()
        
        # Process service activation
        process_service_after_payment(invoice.service, transaction)
        
        return Response({
            'success': True,
            'message': 'Payment successful! Your service is being deployed.',
            'transaction': TransactionSerializer(transaction).data,
            'new_balance': float(request.user.balance)
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Payment failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# M-Pesa Payment
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_mpesa_payment(request):
    """
    Initiate M-Pesa STK Push payment
    
    POST /api/transactions/mpesa_payment/
    {
        "phone_number": "254700000000",
        "amount": 15.00,
        "invoice_id": 1
    }
    """
    phone_number = request.data.get('phone_number')
    amount = request.data.get('amount')
    invoice_id = request.data.get('invoice_id')
    
    if not all([phone_number, amount, invoice_id]):
        return Response({
            'error': 'Missing required fields'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate invoice
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user, status='unpaid')
    except Invoice.DoesNotExist:
        return Response({
            'error': 'Invoice not found or already paid'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Create transaction
    transaction = Transaction.objects.create(
        user=request.user,
        service=invoice.service,
        transaction_id=f'MPESA-{uuid.uuid4().hex[:12].upper()}',
        payment_method='mpesa',
        amount=amount,
        status='pending',
        description=f'M-Pesa payment for invoice {invoice.invoice_number}',
        metadata={'invoice_id': invoice_id, 'phone_number': phone_number}
    )
    
    # Initiate M-Pesa STK push
    mpesa = MPesaClient()
    result = mpesa.stk_push(
        phone_number=phone_number,
        amount=amount,
        account_reference=invoice.invoice_number,
        transaction_desc=f'Payment for {invoice.service.plan.name if invoice.service else "service"}'
    )
    
    # Update transaction with M-Pesa response
    transaction.external_reference = result.get('CheckoutRequestID', '')
    transaction.metadata.update(result)
    transaction.save()
    
    return Response({
        'success': True,
        'message': 'STK push sent. Please check your phone.',
        'transaction': TransactionSerializer(transaction).data,
        'mpesa_response': result
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """
    M-Pesa payment callback handler
    
    POST /api/webhooks/mpesa/
    """
    data = request.data
    
    try:
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        
        # Find transaction
        transaction = Transaction.objects.get(external_reference=checkout_request_id)
        
        if result_code == 0:  # Success
            # Update transaction
            transaction.status = 'completed'
            transaction.completed_at = timezone.now()
            transaction.metadata.update(stk_callback)
            transaction.save()
            
            # Find and update invoice
            invoice_id = transaction.metadata.get('invoice_id')
            if invoice_id:
                invoice = Invoice.objects.filter(id=invoice_id).first()
                if invoice and invoice.status == 'unpaid':
                    invoice.status = 'paid'
                    invoice.paid_at = timezone.now()
                    invoice.transaction = transaction
                    invoice.save()
                    
                    # Process service activation
                    if invoice.service:
                        process_service_after_payment(invoice.service, transaction)
        else:
            # Payment failed
            transaction.status = 'failed'
            transaction.metadata.update(stk_callback)
            transaction.save()
        
        return Response({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Transaction.DoesNotExist:
        return Response({'ResultCode': 1, 'ResultDesc': 'Transaction not found'})
    except Exception as e:
        return Response({'ResultCode': 1, 'ResultDesc': str(e)})

# PayPal Payment
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_paypal_payment(request):
    """
    Create PayPal payment order
    
    POST /api/transactions/paypal_payment/
    {
        "amount": 15.00,
        "invoice_id": 1,
        "return_url": "http://...",
        "cancel_url": "http://..."
    }
    """
    amount = request.data.get('amount')
    invoice_id = request.data.get('invoice_id')
    return_url = request.data.get('return_url', '')
    cancel_url = request.data.get('cancel_url', '')
    
    if not all([amount, invoice_id]):
        return Response({
            'error': 'Missing required fields'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate invoice
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user, status='unpaid')
    except Invoice.DoesNotExist:
        return Response({
            'error': 'Invoice not found or already paid'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if PayPal is configured
    from django.conf import settings
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        return Response({
            'success': False,
            'error': 'PayPal is not configured. Please contact administrator or use another payment method.',
            'paypal_configured': False
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    # Create transaction
    transaction = Transaction.objects.create(
        user=request.user,
        service=invoice.service,
        transaction_id=f'PAYPAL-{uuid.uuid4().hex[:12].upper()}',
        payment_method='paypal',
        amount=amount,
        status='pending',
        description=f'PayPal payment for invoice {invoice.invoice_number}',
        metadata={'invoice_id': invoice_id}
    )
    
    try:
        # Create PayPal order
        paypal = PayPalClient()
        result = paypal.create_order(
            amount=amount,
            currency='USD',
            return_url=return_url,
            cancel_url=cancel_url
        )
        
        # Update transaction
        transaction.external_reference = result.get('id', '')
        transaction.metadata.update(result)
        transaction.save()
        
        return Response({
            'success': True,
            'message': 'PayPal order created',
            'transaction': TransactionSerializer(transaction).data,
            'paypal_response': result,
            'paypal_configured': True
        })
    except Exception as e:
        # Update transaction as failed
        transaction.status = 'failed'
        transaction.metadata['error'] = str(e)
        transaction.save()
        
        return Response({
            'success': False,
            'error': f'Failed to create PayPal order: {str(e)}',
            'paypal_configured': True
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def paypal_webhook(request):
    """
    PayPal webhook handler
    
    POST /api/webhooks/paypal/
    """
    event_type = request.data.get('event_type')
    resource = request.data.get('resource', {})
    
    try:
        if event_type == 'CHECKOUT.ORDER.APPROVED':
            order_id = resource.get('id')
            
            # Find transaction
            transaction = Transaction.objects.get(external_reference=order_id)
            
            # Capture payment
            paypal = PayPalClient()
            result = paypal.capture_order(order_id)
            
            if result.get('status') == 'COMPLETED':
                # Update transaction
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.metadata.update(result)
                transaction.save()
                
                # Update invoice
                invoice_id = transaction.metadata.get('invoice_id')
                if invoice_id:
                    invoice = Invoice.objects.filter(id=invoice_id).first()
                    if invoice and invoice.status == 'unpaid':
                        invoice.status = 'paid'
                        invoice.paid_at = timezone.now()
                        invoice.transaction = transaction
                        invoice.save()
                        
                        # Process service activation
                        if invoice.service:
                            process_service_after_payment(invoice.service, transaction)
        
        return Response({'status': 'success'})
        
    except Transaction.DoesNotExist:
        return Response({'status': 'error', 'message': 'Transaction not found'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})

# Service Activation After Payment

def process_service_after_payment(service, transaction):
    """
    Process service activation after successful payment
    
    - If service is pending: Deploy VM
    - If service is suspended: Reactivate VM
    - Update service next due date
    """
    if not service:
        return
    
    if service.status == 'pending':
        # New service - deploy VM
        create_vm_task.delay(service.id)
        
    elif service.status == 'suspended':
        # Suspended service - reactivate
        from core.tasks import reactivate_service_task
        reactivate_service_task.delay(service.id)
    
    elif service.status == 'active':
        # Renewal - extend due date
        service.next_due_date = service.calculate_next_due_date()
        service.save()