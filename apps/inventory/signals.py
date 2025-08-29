"""
Signal handlers for inventory app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Article, ArticleQR
from .services.qr_service import QRService


@receiver(post_save, sender=Article)
def create_article_qr(sender, instance, created, **kwargs):
    """Create QR code when a new Article is created."""
    if created:
        # Use QRService to generate QR code
        QRService.generate_qr_code(instance)


@receiver(post_delete, sender=ArticleQR)
def delete_qr_file(sender, instance, **kwargs):
    """Delete QR code file when ArticleQR is deleted."""
    if instance.png_file:
        instance.png_file.delete(save=False)
