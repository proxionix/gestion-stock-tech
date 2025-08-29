"""
Django management command to generate QR codes for articles.
Useful for batch QR code generation and regeneration.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.inventory.models import Article, ArticleQR
from apps.inventory.services.qr_service import QRService


class Command(BaseCommand):
    help = 'Generate QR codes for articles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate QR codes for all articles',
        )
        parser.add_argument(
            '--missing',
            action='store_true',
            help='Generate QR codes only for articles without QR codes',
        )
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Regenerate QR codes for all articles (overwrite existing)',
        )
        parser.add_argument(
            '--reference',
            type=str,
            help='Generate QR code for specific article reference',
        )
        parser.add_argument(
            '--size',
            type=int,
            default=10,
            help='QR code size (default: 10)',
        )
        parser.add_argument(
            '--border',
            type=int,
            default=4,
            help='QR code border size (default: 4)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['PNG', 'JPEG'],
            default='PNG',
            help='QR code image format (default: PNG)',
        )

    def handle(self, *args, **options):
        """Handle the QR generation command."""
        
        size = options['size']
        border = options['border']
        format_type = options['format']
        
        try:
            if options['reference']:
                self.generate_for_reference(options['reference'], size, border)
            elif options['all']:
                self.generate_for_all_articles(size, border)
            elif options['missing']:
                self.generate_for_missing_articles(size, border)
            elif options['regenerate']:
                self.regenerate_all_articles(size, border)
            else:
                raise CommandError(
                    'Please specify one of: --all, --missing, --regenerate, or --reference'
                )
                
        except Exception as e:
            raise CommandError(f'Error generating QR codes: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS('QR code generation completed successfully!')
        )

    def generate_for_reference(self, reference, size, border):
        """Generate QR code for specific article reference."""
        self.stdout.write(f'Generating QR code for article: {reference}')
        
        try:
            article = Article.objects.get(reference=reference)
        except Article.DoesNotExist:
            raise CommandError(f'Article with reference "{reference}" not found')
        
        qr_code = QRService.generate_qr_code(article, size=size, border=border)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generated QR code for {article.reference}: {qr_code.payload_url}'
            )
        )

    def generate_for_all_articles(self, size, border):
        """Generate QR codes for all active articles."""
        self.stdout.write('Generating QR codes for all active articles...')
        
        articles = Article.objects.filter(is_active=True)
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No active articles found.'))
            return
        
        generated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for i, article in enumerate(articles, 1):
                # Check if QR already exists
                if hasattr(article, 'qr_code'):
                    self.stdout.write(f'Skipping {article.reference} (QR already exists)')
                    skipped_count += 1
                else:
                    QRService.generate_qr_code(article, size=size, border=border)
                    generated_count += 1
                    self.stdout.write(f'Generated QR for {article.reference}')
                
                # Progress indicator
                if i % 10 == 0 or i == total_count:
                    self.stdout.write(f'Progress: {i}/{total_count} articles processed')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generated: {generated_count}, Skipped: {skipped_count}, Total: {total_count}'
            )
        )

    def generate_for_missing_articles(self, size, border):
        """Generate QR codes only for articles without QR codes."""
        self.stdout.write('Generating QR codes for articles without QR codes...')
        
        # Find articles without QR codes
        articles_without_qr = Article.objects.filter(
            is_active=True,
            qr_code__isnull=True
        )
        
        total_count = articles_without_qr.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('All active articles already have QR codes.'))
            return
        
        self.stdout.write(f'Found {total_count} articles without QR codes.')
        
        generated_count = 0
        
        with transaction.atomic():
            for i, article in enumerate(articles_without_qr, 1):
                QRService.generate_qr_code(article, size=size, border=border)
                generated_count += 1
                self.stdout.write(f'Generated QR for {article.reference}')
                
                # Progress indicator
                if i % 10 == 0 or i == total_count:
                    self.stdout.write(f'Progress: {i}/{total_count} articles processed')
        
        self.stdout.write(
            self.style.SUCCESS(f'Generated QR codes for {generated_count} articles')
        )

    def regenerate_all_articles(self, size, border):
        """Regenerate QR codes for all articles (overwrite existing)."""
        self.stdout.write('Regenerating QR codes for all active articles...')
        
        articles = Article.objects.filter(is_active=True)
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No active articles found.'))
            return
        
        # Confirm regeneration
        self.stdout.write(
            self.style.WARNING(
                f'This will regenerate QR codes for {total_count} articles.'
            )
        )
        
        regenerated_count = 0
        
        with transaction.atomic():
            for i, article in enumerate(articles, 1):
                QRService.generate_qr_code(article, size=size, border=border)
                regenerated_count += 1
                self.stdout.write(f'Regenerated QR for {article.reference}')
                
                # Progress indicator
                if i % 10 == 0 or i == total_count:
                    self.stdout.write(f'Progress: {i}/{total_count} articles processed')
        
        self.stdout.write(
            self.style.SUCCESS(f'Regenerated QR codes for {regenerated_count} articles')
        )

    def display_qr_summary(self):
        """Display summary of QR code status."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('QR CODE SUMMARY'))
        self.stdout.write('='*50)
        
        total_articles = Article.objects.filter(is_active=True).count()
        articles_with_qr = Article.objects.filter(
            is_active=True,
            qr_code__isnull=False
        ).count()
        articles_without_qr = total_articles - articles_with_qr
        
        self.stdout.write(f'Total active articles: {total_articles}')
        self.stdout.write(f'Articles with QR codes: {articles_with_qr}')
        self.stdout.write(f'Articles without QR codes: {articles_without_qr}')
        
        if articles_without_qr > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\nRun: python manage.py generate_qr_codes --missing'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('\nAll articles have QR codes!'))
        
        self.stdout.write('\n' + '='*50)
