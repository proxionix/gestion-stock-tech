"""
Django management command to seed the database with initial data.
Provides demo data for Stock Management System.
"""
import random
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.users.models import Profile
from apps.inventory.models import Article, StockTech, Threshold
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine
from apps.audit.models import StockMovement
from apps.inventory.services.qr_service import QRService

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with initial demo data for Stock Management System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--users-only',
            action='store_true',
            help='Create only users and profiles',
        )
        parser.add_argument(
            '--articles-only',
            action='store_true',
            help='Create only articles',
        )
        parser.add_argument(
            '--stock-only',
            action='store_true',
            help='Create only stock data',
        )
        parser.add_argument(
            '--demo-data',
            action='store_true',
            help='Create comprehensive demo data including orders',
        )

    def handle(self, *args, **options):
        """Handle the seed command."""
        
        if options['clear']:
            self.clear_data()
        
        try:
            with transaction.atomic():
                if options['users_only']:
                    self.create_users()
                elif options['articles_only']:
                    self.create_articles()
                elif options['stock_only']:
                    self.create_stock_data()
                elif options['demo_data']:
                    self.create_demo_data()
                else:
                    self.create_basic_data()
                    
        except Exception as e:
            raise CommandError(f'Error seeding data: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully seeded database with initial data!')
        )

    def clear_data(self):
        """Clear existing data."""
        self.stdout.write('Clearing existing data...')
        
        # Clear in reverse dependency order
        DemandeLine.objects.all().delete()
        Demande.objects.all().delete()
        PanierLine.objects.all().delete()
        Panier.objects.all().delete()
        StockMovement.objects.all().delete()
        Threshold.objects.all().delete()
        StockTech.objects.all().delete()
        Article.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.WARNING('Existing data cleared.'))

    def create_basic_data(self):
        """Create basic data for system setup."""
        self.stdout.write('Creating basic data...')
        
        users = self.create_users()
        articles = self.create_articles()
        self.create_stock_data(users, articles)
        
        self.stdout.write(self.style.SUCCESS('Basic data created.'))

    def create_demo_data(self):
        """Create comprehensive demo data."""
        self.stdout.write('Creating comprehensive demo data...')
        
        users = self.create_users()
        articles = self.create_articles()
        self.create_stock_data(users, articles)
        self.create_demo_orders(users, articles)
        
        self.stdout.write(self.style.SUCCESS('Demo data created.'))

    def create_users(self):
        """Create demo users and profiles."""
        self.stdout.write('Creating users and profiles...')
        
        users = {}
        
        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@stock-system.local',
                'first_name': 'System',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_active': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
        
        admin_profile, created = Profile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': Profile.Role.ADMIN,
                'language_pref': 'en'
            }
        )
        users['admin'] = admin_user
        
        # Create technician users
        technicians_data = [
            {
                'username': 'tech_alice',
                'email': 'alice@stock-system.local',
                'first_name': 'Alice',
                'last_name': 'Dupont',
                'language': 'fr',
            },
            {
                'username': 'tech_bob',
                'email': 'bob@stock-system.local',
                'first_name': 'Bob',
                'last_name': 'Johnson',
                'language': 'en',
            },
            {
                'username': 'tech_charlie',
                'email': 'charlie@stock-system.local',
                'first_name': 'Charlie',
                'last_name': 'Van Der Berg',
                'language': 'nl',
            },
        ]
        
        for tech_data in technicians_data:
            tech_user, created = User.objects.get_or_create(
                username=tech_data['username'],
                defaults={
                    'email': tech_data['email'],
                    'first_name': tech_data['first_name'],
                    'last_name': tech_data['last_name'],
                    'is_active': True,
                }
            )
            if created:
                tech_user.set_password('tech123')
                tech_user.save()
            
            tech_profile, created = Profile.objects.get_or_create(
                user=tech_user,
                defaults={
                    'role': Profile.Role.TECH,
                    'language_pref': tech_data['language']
                }
            )
            users[tech_data['username']] = tech_user
        
        self.stdout.write(f'Created {len(users)} users with profiles.')
        return users

    def create_articles(self):
        """Create demo articles."""
        self.stdout.write('Creating articles...')
        
        articles_data = [
            # Mechanical parts
            {
                'reference': 'SCREW-M6-20',
                'name': 'M6x20 Hex Screw',
                'description': 'M6 x 20mm hex head screw, stainless steel A2',
                'unit': 'PCS',
            },
            {
                'reference': 'SCREW-M8-25',
                'name': 'M8x25 Hex Screw',
                'description': 'M8 x 25mm hex head screw, stainless steel A2',
                'unit': 'PCS',
            },
            {
                'reference': 'WASHER-M6',
                'name': 'M6 Flat Washer',
                'description': 'M6 flat washer, stainless steel',
                'unit': 'PCS',
            },
            {
                'reference': 'WASHER-M8',
                'name': 'M8 Flat Washer',
                'description': 'M8 flat washer, stainless steel',
                'unit': 'PCS',
            },
            {
                'reference': 'NUT-M6',
                'name': 'M6 Hex Nut',
                'description': 'M6 hex nut, stainless steel A2',
                'unit': 'PCS',
            },
            
            # Tools and equipment
            {
                'reference': 'WRENCH-ADJ-10',
                'name': 'Adjustable Wrench 10"',
                'description': '10-inch adjustable wrench, chrome vanadium steel',
                'unit': 'PCS',
            },
            {
                'reference': 'DRILL-BIT-6',
                'name': 'HSS Drill Bit 6mm',
                'description': 'High-speed steel drill bit, 6mm diameter',
                'unit': 'PCS',
            },
            {
                'reference': 'DRILL-BIT-8',
                'name': 'HSS Drill Bit 8mm',
                'description': 'High-speed steel drill bit, 8mm diameter',
                'unit': 'PCS',
            },
            
            # Lubrication and maintenance
            {
                'reference': 'GREASE-BEARING',
                'name': 'Bearing Grease',
                'description': 'High-performance bearing grease, 400g cartridge',
                'unit': 'KG',
            },
            {
                'reference': 'OIL-HYDRAULIC',
                'name': 'Hydraulic Oil ISO 32',
                'description': 'Hydraulic oil ISO VG 32, 5L container',
                'unit': 'L',
            },
            {
                'reference': 'CLEANER-PARTS',
                'name': 'Parts Cleaner',
                'description': 'Industrial parts cleaner, 1L spray bottle',
                'unit': 'L',
            },
            
            # Electrical components
            {
                'reference': 'CABLE-ETH-2M',
                'name': 'Ethernet Cable 2m',
                'description': 'Cat6 Ethernet cable, 2 meters, blue',
                'unit': 'M',
            },
            {
                'reference': 'CABLE-ETH-5M',
                'name': 'Ethernet Cable 5m',
                'description': 'Cat6 Ethernet cable, 5 meters, blue',
                'unit': 'M',
            },
            {
                'reference': 'FUSE-10A',
                'name': 'Fuse 10A',
                'description': '10 Amp fast-blow fuse, 5x20mm',
                'unit': 'PCS',
            },
            {
                'reference': 'RELAY-24V',
                'name': '24V Relay',
                'description': '24V DC relay, SPDT, 10A contacts',
                'unit': 'PCS',
            },
            
            # Safety equipment
            {
                'reference': 'GLOVES-NITRILE',
                'name': 'Nitrile Gloves',
                'description': 'Disposable nitrile gloves, size L, box of 100',
                'unit': 'BOX',
            },
            {
                'reference': 'GLASSES-SAFETY',
                'name': 'Safety Glasses',
                'description': 'Clear safety glasses, anti-fog coating',
                'unit': 'PCS',
            },
            
            # Consumables
            {
                'reference': 'TAPE-DUCT',
                'name': 'Duct Tape',
                'description': 'Heavy-duty duct tape, 50mm x 25m, silver',
                'unit': 'ROLL',
            },
            {
                'reference': 'TAPE-ELECTRICAL',
                'name': 'Electrical Tape',
                'description': 'PVC electrical tape, 19mm x 20m, black',
                'unit': 'ROLL',
            },
            {
                'reference': 'RAGS-SHOP',
                'name': 'Shop Rags',
                'description': 'Cotton shop rags, pack of 25',
                'unit': 'PACK',
            },
        ]
        
        articles = {}
        for article_data in articles_data:
            article, created = Article.objects.get_or_create(
                reference=article_data['reference'],
                defaults=article_data
            )
            articles[article_data['reference']] = article
            
            # Generate QR code for each article
            if created:
                QRService.generate_qr_code(article)
        
        self.stdout.write(f'Created {len(articles)} articles with QR codes.')
        return articles

    def create_stock_data(self, users=None, articles=None):
        """Create stock data for technicians."""
        self.stdout.write('Creating stock data...')
        
        if users is None:
            users = {user.username: user for user in User.objects.all()}
        if articles is None:
            articles = {article.reference: article for article in Article.objects.all()}
        
        # Stock distribution for technicians
        stock_data = {
            'tech_alice': {
                'SCREW-M6-20': {'quantity': 150, 'threshold': 20},
                'SCREW-M8-25': {'quantity': 100, 'threshold': 15},
                'WASHER-M6': {'quantity': 200, 'threshold': 30},
                'WASHER-M8': {'quantity': 150, 'threshold': 25},
                'NUT-M6': {'quantity': 120, 'threshold': 20},
                'GREASE-BEARING': {'quantity': 5, 'threshold': 2},
                'CLEANER-PARTS': {'quantity': 3, 'threshold': 1},
                'GLOVES-NITRILE': {'quantity': 8, 'threshold': 2},
                'TAPE-DUCT': {'quantity': 6, 'threshold': 2},
            },
            'tech_bob': {
                'DRILL-BIT-6': {'quantity': 12, 'threshold': 3},
                'DRILL-BIT-8': {'quantity': 10, 'threshold': 3},
                'CABLE-ETH-2M': {'quantity': 25, 'threshold': 5},
                'CABLE-ETH-5M': {'quantity': 15, 'threshold': 3},
                'FUSE-10A': {'quantity': 50, 'threshold': 10},
                'RELAY-24V': {'quantity': 20, 'threshold': 5},
                'GLASSES-SAFETY': {'quantity': 15, 'threshold': 3},
                'TAPE-ELECTRICAL': {'quantity': 12, 'threshold': 3},
            },
            'tech_charlie': {
                'WRENCH-ADJ-10': {'quantity': 3, 'threshold': 1},
                'OIL-HYDRAULIC': {'quantity': 8, 'threshold': 2},
                'SCREW-M6-20': {'quantity': 80, 'threshold': 15},
                'WASHER-M6': {'quantity': 100, 'threshold': 20},
                'GLOVES-NITRILE': {'quantity': 5, 'threshold': 2},
                'RAGS-SHOP': {'quantity': 10, 'threshold': 3},
                'CLEANER-PARTS': {'quantity': 4, 'threshold': 1},
            }
        }
        
        stock_count = 0
        threshold_count = 0
        
        for username, stock_items in stock_data.items():
            if username not in users:
                continue
                
            technician = users[username].profile
            
            for reference, data in stock_items.items():
                if reference not in articles:
                    continue
                    
                article = articles[reference]
                
                # Create stock
                stock, created = StockTech.objects.get_or_create(
                    technician=technician,
                    article=article,
                    defaults={'quantity': data['quantity']}
                )
                if created:
                    stock_count += 1
                
                # Create threshold
                threshold, created = Threshold.objects.get_or_create(
                    technician=technician,
                    article=article,
                    defaults={'min_quantity': data['threshold']}
                )
                if created:
                    threshold_count += 1
        
        self.stdout.write(f'Created {stock_count} stock entries and {threshold_count} thresholds.')

    def create_demo_orders(self, users, articles):
        """Create demo orders and demands for testing."""
        self.stdout.write('Creating demo orders...')
        
        # Create some historical demands
        tech_alice = users['tech_alice'].profile
        tech_bob = users['tech_bob'].profile
        
        # Historical completed demand for Alice
        completed_demand = Demande.objects.create(
            technician=tech_alice,
            status=Demande.Status.HANDED_OVER,
            created_at=timezone.now() - timezone.timedelta(days=5),
            updated_at=timezone.now() - timezone.timedelta(days=3)
        )
        
        DemandeLine.objects.create(
            demande=completed_demand,
            article=articles['SCREW-M6-20'],
            quantity_requested=50,
            quantity_approved=50,
            quantity_prepared=50
        )
        
        DemandeLine.objects.create(
            demande=completed_demand,
            article=articles['WASHER-M6'],
            quantity_requested=50,
            quantity_approved=45,
            quantity_prepared=45
        )
        
        # Pending demand for Bob
        pending_demand = Demande.objects.create(
            technician=tech_bob,
            status=Demande.Status.SUBMITTED,
            created_at=timezone.now() - timezone.timedelta(hours=2)
        )
        
        DemandeLine.objects.create(
            demande=pending_demand,
            article=articles['CABLE-ETH-2M'],
            quantity_requested=10,
            quantity_approved=0,
            quantity_prepared=0
        )
        
        DemandeLine.objects.create(
            demande=pending_demand,
            article=articles['FUSE-10A'],
            quantity_requested=20,
            quantity_approved=0,
            quantity_prepared=0
        )
        
        # Active cart for Alice
        active_cart = Panier.objects.create(
            technician=tech_alice,
            status=Panier.Status.DRAFT
        )
        
        PanierLine.objects.create(
            panier=active_cart,
            article=articles['GREASE-BEARING'],
            quantity=2
        )
        
        # Create some stock movements for history
        movements_data = [
            {
                'technician': tech_alice,
                'article': articles['SCREW-M6-20'],
                'quantity_delta': -25,
                'movement_type': StockMovement.MovementType.ISSUE,
                'location_text': 'Production Line A - Conveyor repair',
                'timestamp': timezone.now() - timezone.timedelta(days=2)
            },
            {
                'technician': tech_alice,
                'article': articles['WASHER-M6'],
                'quantity_delta': -15,
                'movement_type': StockMovement.MovementType.ISSUE,
                'location_text': 'Production Line A - Conveyor repair',
                'timestamp': timezone.now() - timezone.timedelta(days=2)
            },
            {
                'technician': tech_bob,
                'article': articles['CABLE-ETH-2M'],
                'quantity_delta': -5,
                'movement_type': StockMovement.MovementType.ISSUE,
                'location_text': 'Server Room - Network expansion',
                'timestamp': timezone.now() - timezone.timedelta(days=1)
            },
            {
                'technician': tech_alice,
                'article': articles['GREASE-BEARING'],
                'quantity_delta': +2,
                'movement_type': StockMovement.MovementType.RECEIPT,
                'location_text': 'Stock replenishment',
                'timestamp': timezone.now() - timezone.timedelta(days=3),
                'linked_demande_id': str(completed_demand.id)
            }
        ]
        
        for movement_data in movements_data:
            StockMovement.objects.create(**movement_data)
        
        self.stdout.write(f'Created demo orders: 1 completed, 1 pending, 1 active cart, {len(movements_data)} movements.')

    def display_summary(self):
        """Display summary of created data."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('SEED DATA SUMMARY'))
        self.stdout.write('='*50)
        
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Profiles: {Profile.objects.count()}')
        self.stdout.write(f'Articles: {Article.objects.count()}')
        self.stdout.write(f'Stock entries: {StockTech.objects.count()}')
        self.stdout.write(f'Thresholds: {Threshold.objects.count()}')
        self.stdout.write(f'Carts: {Panier.objects.count()}')
        self.stdout.write(f'Cart lines: {PanierLine.objects.count()}')
        self.stdout.write(f'Demands: {Demande.objects.count()}')
        self.stdout.write(f'Demand lines: {DemandeLine.objects.count()}')
        self.stdout.write(f'Stock movements: {StockMovement.objects.count()}')
        
        self.stdout.write('\n' + self.style.SUCCESS('DEMO ACCOUNTS:'))
        self.stdout.write('Admin: admin / admin123')
        self.stdout.write('Technicians: tech_alice, tech_bob, tech_charlie / tech123')
        
        self.stdout.write('\n' + '='*50)
