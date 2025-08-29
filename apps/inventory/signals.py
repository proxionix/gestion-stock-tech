"""
Signal handlers for inventory app.
"""
import io
import qrcode
from django.core.files.base import ContentFile
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Article, ArticleQR


@receiver(post_save, sender=Article)
def create_article_qr(sender, instance, created, **kwargs):
    """Create QR code when a new Article is created."""
    if created:
        # Generate QR code payload URL
        payload_url = f"/a/{instance.reference}"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payload_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to file-like object
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        # Create ArticleQR instance
        qr_filename = f"{instance.reference}_qr.png"
        article_qr = ArticleQR(
            article=instance,
            payload_url=payload_url
        )
        article_qr.png_file.save(
            qr_filename,
            ContentFile(img_io.getvalue()),
            save=True
        )


@receiver(post_delete, sender=ArticleQR)
def delete_qr_file(sender, instance, **kwargs):
    """Delete QR code file when ArticleQR is deleted."""
    if instance.png_file:
        instance.png_file.delete(save=False)
