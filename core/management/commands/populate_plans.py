from django.core.management.base import BaseCommand
from core.models import Plan

class Command(BaseCommand):
    help = 'Populate sample hosting plans'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'Starter VPS',
                'plan_type': 'vps',
                'cpu_cores': 1,
                'ram_mb': 1024,
                'disk_gb': 25,
                'bandwidth_gb': 1000,
                'price_monthly': 5.00,
                'price_quarterly': 13.50,
                'price_annually': 50.00,
                'description': 'Perfect for beginners and small projects. Includes 1 CPU core, 1GB RAM, and 25GB SSD storage.',
                'is_active': True
            },
            {
                'name': 'Business VPS',
                'plan_type': 'vps',
                'cpu_cores': 2,
                'ram_mb': 4096,
                'disk_gb': 80,
                'bandwidth_gb': 2000,
                'price_monthly': 15.00,
                'price_quarterly': 40.50,
                'price_annually': 150.00,
                'description': 'Ideal for growing businesses. Features 2 CPU cores, 4GB RAM, and 80GB SSD storage.',
                'is_active': True
            },
            {
                'name': 'Enterprise VPS',
                'plan_type': 'vps',
                'cpu_cores': 4,
                'ram_mb': 8192,
                'disk_gb': 160,
                'bandwidth_gb': 4000,
                'price_monthly': 30.00,
                'price_quarterly': 81.00,
                'price_annually': 300.00,
                'description': 'For demanding applications. Powered by 4 CPU cores, 8GB RAM, and 160GB SSD storage.',
                'is_active': True
            },
            {
                'name': 'Pro VPS',
                'plan_type': 'vps',
                'cpu_cores': 8,
                'ram_mb': 16384,
                'disk_gb': 320,
                'bandwidth_gb': 8000,
                'price_monthly': 60.00,
                'price_quarterly': 162.00,
                'price_annually': 600.00,
                'description': 'Maximum performance with 8 CPU cores, 16GB RAM, and 320GB SSD storage.',
                'is_active': True
            }
        ]
        
        for plan_data in plans_data:
            plan, created = Plan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created plan: {plan.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'📝 Updated plan: {plan.name}'))
        
        total = Plan.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f'\n🎉 Total active plans: {total}'))