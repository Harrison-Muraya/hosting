from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from core.models import Plan, Service
from core.serializers import PlanSerializer

def is_staff(user):
    return user.is_staff

# Admin Plan Management Views (HTML Pages)
@login_required
@user_passes_test(is_staff)
def admin_plans_page(request):
    """Admin page for managing plans"""
    plans = Plan.objects.all().annotate(
        services_count=Count('service')
    ).order_by('-created_at')
    
    context = {
        'plans': plans,
        'total_plans': plans.count(),
        'active_plans': plans.filter(is_active=True).count(),
        'inactive_plans': plans.filter(is_active=False).count(),
        'active_services': Service.objects.filter(status='active').count(),
    }
    return render(request, 'dashboard/admin_plans.html', context)

# Admin Plans API ViewSet
class AdminPlanViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing plans
    - GET /api/admin/plans/ - List all plans
    - POST /api/admin/plans/ - Create new plan
    - GET /api/admin/plans/{id}/ - Get plan details
    - PUT /api/admin/plans/{id}/ - Update plan
    - DELETE /api/admin/plans/{id}/ - Delete plan
    """
    queryset = Plan.objects.all().order_by('-created_at')
    serializer_class = PlanSerializer
    permission_classes = [IsAdminUser]
    
    def create(self, request):
        """Create a new plan"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Check if plan with same name exists
            if Plan.objects.filter(name=serializer.validated_data['name']).exists():
                return Response({
                    'error': 'A plan with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            plan = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Plan created successfully',
                'plan': PlanSerializer(plan).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, pk=None):
        """Update an existing plan"""
        try:
            plan = self.get_object()
        except Plan.DoesNotExist:
            return Response({
                'error': 'Plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(plan, data=request.data, partial=False)
        
        if serializer.is_valid():
            # Check if another plan with same name exists
            existing = Plan.objects.filter(
                name=serializer.validated_data['name']
            ).exclude(id=plan.id).exists()
            
            if existing:
                return Response({
                    'error': 'A plan with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            updated_plan = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Plan updated successfully',
                'plan': PlanSerializer(updated_plan).data
            })
        
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, pk=None):
        """Delete a plan"""
        try:
            plan = self.get_object()
        except Plan.DoesNotExist:
            return Response({
                'error': 'Plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if plan has active services
        active_services = Service.objects.filter(
            plan=plan,
            status__in=['pending', 'active']
        ).count()
        
        if active_services > 0:
            return Response({
                'error': f'Cannot delete plan with {active_services} active service(s). Please deactivate it instead.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        plan_name = plan.name
        plan.delete()
        
        return Response({
            'success': True,
            'message': f'Plan "{plan_name}" deleted successfully'
        })
    
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle plan active status"""
        try:
            plan = self.get_object()
        except Plan.DoesNotExist:
            return Response({
                'error': 'Plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        plan.is_active = not plan.is_active
        plan.save()
        
        return Response({
            'success': True,
            'message': f'Plan {"activated" if plan.is_active else "deactivated"} successfully',
            'is_active': plan.is_active
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get plan statistics"""
        try:
            plan = self.get_object()
        except Plan.DoesNotExist:
            return Response({
                'error': 'Plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        services = Service.objects.filter(plan=plan)
        
        stats = {
            'total_services': services.count(),
            'active_services': services.filter(status='active').count(),
            'pending_services': services.filter(status='pending').count(),
            'suspended_services': services.filter(status='suspended').count(),
            'terminated_services': services.filter(status='terminated').count(),
            'monthly_revenue': float(services.filter(
                status='active',
                billing_cycle='monthly'
            ).count() * plan.price_monthly),
        }
        
        return Response({
            'success': True,
            'plan': PlanSerializer(plan).data,
            'statistics': stats
        })
    
# Bulk Operations API
@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_activate_plans(request):
    """Bulk activate multiple plans"""
    plan_ids = request.data.get('plan_ids', [])
    
    if not plan_ids:
        return Response({
            'error': 'No plan IDs provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    updated = Plan.objects.filter(id__in=plan_ids).update(is_active=True)
    
    return Response({
        'success': True,
        'message': f'{updated} plan(s) activated successfully',
        'updated_count': updated
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_deactivate_plans(request):
    """Bulk deactivate multiple plans"""
    plan_ids = request.data.get('plan_ids', [])
    
    if not plan_ids:
        return Response({
            'error': 'No plan IDs provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    updated = Plan.objects.filter(id__in=plan_ids).update(is_active=False)
    
    return Response({
        'success': True,
        'message': f'{updated} plan(s) deactivated successfully',
        'updated_count': updated
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def duplicate_plan(request, plan_id):
    """Duplicate an existing plan"""
    try:
        original_plan = Plan.objects.get(id=plan_id)
    except Plan.DoesNotExist:
        return Response({
            'error': 'Plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Create duplicate with modified name
    duplicate = Plan.objects.create(
        name=f"{original_plan.name} (Copy)",
        plan_type=original_plan.plan_type,
        cpu_cores=original_plan.cpu_cores,
        ram_mb=original_plan.ram_mb,
        disk_gb=original_plan.disk_gb,
        bandwidth_gb=original_plan.bandwidth_gb,
        price_monthly=original_plan.price_monthly,
        price_quarterly=original_plan.price_quarterly,
        price_annually=original_plan.price_annually,
        description=original_plan.description,
        is_active=False  # Set to inactive by default
    )
    
    return Response({
        'success': True,
        'message': 'Plan duplicated successfully',
        'plan': PlanSerializer(duplicate).data
    }, status=status.HTTP_201_CREATED)