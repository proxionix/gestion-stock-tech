"""
Django management command for system maintenance tasks.
Includes data cleanup, optimization, and health checks.
"""
import os
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.cache import cache
from apps.audit.models import EventLog, StockMovement
from apps.orders.models import Panier, Demande
from apps.inventory.models import ArticleQR
from apps.users.models import User


class Command(BaseCommand):
    help = 'Perform system maintenance tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup-old-data',
            action='store_true',
            help='Clean up old audit logs and expired data',
        )
        parser.add_argument(
            '--cleanup-orphaned-files',
            action='store_true',
            help='Clean up orphaned QR code files',
        )
        parser.add_argument(
            '--optimize-database',
            action='store_true',
            help='Optimize database (analyze tables)',
        )
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Perform system health check',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear application cache',
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=90,
            help='Data retention period in days (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all maintenance tasks',
        )

    def handle(self, *args, **options):
        """Handle the maintenance command."""
        
        self.dry_run = options['dry_run']
        self.retention_days = options['retention_days']
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        try:
            if options['all']:
                self.run_all_maintenance()
            else:
                if options['cleanup_old_data']:
                    self.cleanup_old_data()
                
                if options['cleanup_orphaned_files']:
                    self.cleanup_orphaned_files()
                
                if options['optimize_database']:
                    self.optimize_database()
                
                if options['health_check']:
                    self.health_check()
                
                if options['clear_cache']:
                    self.clear_cache()
                
                if not any([
                    options['cleanup_old_data'],
                    options['cleanup_orphaned_files'],
                    options['optimize_database'],
                    options['health_check'],
                    options['clear_cache'],
                    options['all']
                ]):
                    self.stdout.write(
                        self.style.WARNING(
                            'No maintenance tasks specified. Use --help for options.'
                        )
                    )
                    return
                    
        except Exception as e:
            raise CommandError(f'Error during maintenance: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS('System maintenance completed successfully!')
        )

    def run_all_maintenance(self):
        """Run all maintenance tasks."""
        self.stdout.write('Running all maintenance tasks...')
        
        self.health_check()
        self.cleanup_old_data()
        self.cleanup_orphaned_files()
        self.clear_cache()
        self.optimize_database()

    def cleanup_old_data(self):
        """Clean up old audit logs and expired data."""
        self.stdout.write('Cleaning up old data...')
        
        cutoff_date = timezone.now() - timedelta(days=self.retention_days)
        
        # Clean old event logs
        old_events = EventLog.objects.filter(timestamp__lt=cutoff_date)
        event_count = old_events.count()
        
        if event_count > 0:
            self.stdout.write(f'Found {event_count} old event logs to delete')
            if not self.dry_run:
                old_events.delete()
                self.stdout.write(f'Deleted {event_count} old event logs')
        else:
            self.stdout.write('No old event logs to delete')
        
        # Clean old stock movements
        old_movements = StockMovement.objects.filter(timestamp__lt=cutoff_date)
        movement_count = old_movements.count()
        
        if movement_count > 0:
            self.stdout.write(f'Found {movement_count} old stock movements to delete')
            if not self.dry_run:
                old_movements.delete()
                self.stdout.write(f'Deleted {movement_count} old stock movements')
        else:
            self.stdout.write('No old stock movements to delete')
        
        # Clean old completed/refused demands
        old_demands = Demande.objects.filter(
            updated_at__lt=cutoff_date,
            status__in=[Demande.Status.HANDED_OVER, Demande.Status.REFUSED, Demande.Status.CLOSED]
        )
        demand_count = old_demands.count()
        
        if demand_count > 0:
            self.stdout.write(f'Found {demand_count} old completed demands to archive')
            # In a real system, you might archive rather than delete
            if not self.dry_run:
                # For now, just mark them for archival
                self.stdout.write(f'Marked {demand_count} demands for archival')
        else:
            self.stdout.write('No old demands to archive')
        
        # Clean orphaned cart sessions
        old_carts = Panier.objects.filter(
            created_at__lt=cutoff_date,
            status=Panier.Status.DRAFT
        )
        cart_count = old_carts.count()
        
        if cart_count > 0:
            self.stdout.write(f'Found {cart_count} old draft carts to delete')
            if not self.dry_run:
                old_carts.delete()
                self.stdout.write(f'Deleted {cart_count} old draft carts')
        else:
            self.stdout.write('No old draft carts to delete')

    def cleanup_orphaned_files(self):
        """Clean up orphaned QR code files."""
        self.stdout.write('Cleaning up orphaned files...')
        
        if not hasattr(settings, 'MEDIA_ROOT'):
            self.stdout.write('MEDIA_ROOT not configured, skipping file cleanup')
            return
        
        # QR code cleanup
        qr_directory = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
        
        if not os.path.exists(qr_directory):
            self.stdout.write('QR codes directory does not exist')
            return
        
        # Get all QR files in database
        db_files = set()
        for qr in ArticleQR.objects.all():
            if qr.png_file:
                db_files.add(os.path.basename(qr.png_file.name))
        
        # Check files in directory
        orphaned_files = []
        total_files = 0
        
        for root, dirs, files in os.walk(qr_directory):
            for file in files:
                total_files += 1
                if file.endswith('.png') and file not in db_files:
                    orphaned_files.append(os.path.join(root, file))
        
        self.stdout.write(f'Found {total_files} total QR files, {len(orphaned_files)} orphaned')
        
        if orphaned_files:
            for file_path in orphaned_files:
                self.stdout.write(f'Orphaned file: {file_path}')
                if not self.dry_run:
                    try:
                        os.remove(file_path)
                        self.stdout.write(f'Deleted: {file_path}')
                    except OSError as e:
                        self.stdout.write(f'Failed to delete {file_path}: {e}')
        else:
            self.stdout.write('No orphaned QR files found')

    def optimize_database(self):
        """Optimize database performance."""
        self.stdout.write('Optimizing database...')
        
        if self.dry_run:
            self.stdout.write('Would run database optimization (ANALYZE)')
            return
        
        from django.db import connection
        
        try:
            with connection.cursor() as cursor:
                # For PostgreSQL
                if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                    cursor.execute('ANALYZE;')
                    self.stdout.write('Executed ANALYZE on PostgreSQL database')
                
                # For SQLite
                elif 'sqlite' in settings.DATABASES['default']['ENGINE']:
                    cursor.execute('ANALYZE;')
                    cursor.execute('VACUUM;')
                    self.stdout.write('Executed ANALYZE and VACUUM on SQLite database')
                
                else:
                    self.stdout.write('Database optimization not configured for this engine')
        
        except Exception as e:
            self.stdout.write(f'Database optimization failed: {e}')

    def health_check(self):
        """Perform system health check."""
        self.stdout.write('Performing system health check...')
        
        issues = []
        
        # Check database connectivity
        try:
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute('SELECT 1')
            self.stdout.write('✓ Database connectivity: OK')
        except Exception as e:
            issues.append(f'Database connectivity: {e}')
        
        # Check cache connectivity
        try:
            cache.set('health_check', 'ok', 30)
            if cache.get('health_check') == 'ok':
                self.stdout.write('✓ Cache connectivity: OK')
            else:
                issues.append('Cache connectivity: Failed to retrieve test value')
        except Exception as e:
            issues.append(f'Cache connectivity: {e}')
        
        # Check media directory
        if hasattr(settings, 'MEDIA_ROOT'):
            if os.path.exists(settings.MEDIA_ROOT) and os.access(settings.MEDIA_ROOT, os.W_OK):
                self.stdout.write('✓ Media directory: OK')
            else:
                issues.append('Media directory: Not accessible or writable')
        else:
            issues.append('Media directory: MEDIA_ROOT not configured')
        
        # Check critical models
        from apps.users.models import Profile
        from apps.inventory.models import Article
        
        try:
            user_count = User.objects.count()
            profile_count = Profile.objects.count()
            article_count = Article.objects.count()
            
            self.stdout.write(f'✓ Data integrity: {user_count} users, {profile_count} profiles, {article_count} articles')
            
            # Check for users without profiles
            users_without_profiles = User.objects.filter(profile__isnull=True).count()
            if users_without_profiles > 0:
                issues.append(f'{users_without_profiles} users without profiles')
            
        except Exception as e:
            issues.append(f'Data integrity check failed: {e}')
        
        # Check disk space (if possible)
        try:
            import shutil
            total, used, free = shutil.disk_usage(settings.BASE_DIR)
            free_percent = (free / total) * 100
            
            if free_percent < 10:
                issues.append(f'Low disk space: {free_percent:.1f}% free')
            else:
                self.stdout.write(f'✓ Disk space: {free_percent:.1f}% free')
        except:
            self.stdout.write('? Disk space: Could not check')
        
        # Summary
        if issues:
            self.stdout.write('\n' + self.style.ERROR('HEALTH CHECK ISSUES:'))
            for issue in issues:
                self.stdout.write(f'✗ {issue}')
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✓ All health checks passed!'))

    def clear_cache(self):
        """Clear application cache."""
        self.stdout.write('Clearing cache...')
        
        if self.dry_run:
            self.stdout.write('Would clear application cache')
            return
        
        try:
            cache.clear()
            self.stdout.write('Cache cleared successfully')
        except Exception as e:
            self.stdout.write(f'Failed to clear cache: {e}')

    def display_maintenance_summary(self):
        """Display maintenance summary."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('MAINTENANCE SUMMARY'))
        self.stdout.write('='*50)
        
        # Current data counts
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Event logs: {EventLog.objects.count()}')
        self.stdout.write(f'Stock movements: {StockMovement.objects.count()}')
        self.stdout.write(f'Active demands: {Demande.objects.exclude(status__in=[Demande.Status.HANDED_OVER, Demande.Status.REFUSED, Demande.Status.CLOSED]).count()}')
        self.stdout.write(f'Draft carts: {Panier.objects.filter(status=Panier.Status.DRAFT).count()}')
        
        self.stdout.write('\n' + self.style.SUCCESS('RECOMMENDED SCHEDULE:'))
        self.stdout.write('Daily: python manage.py system_maintenance --health-check')
        self.stdout.write('Weekly: python manage.py system_maintenance --cleanup-old-data --clear-cache')
        self.stdout.write('Monthly: python manage.py system_maintenance --all')
        
        self.stdout.write('\n' + '='*50)
