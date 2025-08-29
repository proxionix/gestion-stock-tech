"""
Inventory models for Stock Management System.
"""
import os
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimestampedModel, BaseModel
from apps.users.models import Profile


class UnitChoice(models.TextChoices):
    """Unit of measurement choices."""
    PIECE = 'PCS', _('Piece')
    METER = 'M', _('Meter')
    KILOGRAM = 'KG', _('Kilogram')
    LITER = 'L', _('Liter')
    BOX = 'BOX', _('Box')
    ROLL = 'ROLL', _('Roll')
    SET = 'SET', _('Set')


class Article(TimestampedModel):
    """
    Article/Product model with unique reference.
    """
    reference = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Reference'),
        help_text=_('Unique product reference')
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Name')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    unit = models.CharField(
        max_length=10,
        choices=UnitChoice.choices,
        default=UnitChoice.PIECE,
        verbose_name=_('Unit of measurement')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Inactive articles cannot be ordered')
    )
    
    category = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Category')
    )
    
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Manufacturer')
    )
    
    model_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Model number')
    )
    
    safety_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Safety stock'),
        help_text=_('Minimum stock level recommended')
    )
    
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_('Cost price')
    )
    
    class Meta:
        verbose_name = _('Article')
        verbose_name_plural = _('Articles')
        db_table = 'inventory_article'
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['reference']
    
    def __str__(self):
        return f"{self.reference} - {self.name}"
    
    @property
    def qr_code_url(self):
        """Get QR code URL for this article."""
        return f"/a/{self.reference}"


def qr_upload_path(instance, filename):
    """Generate upload path for QR code images."""
    return f'qr_codes/{instance.article.reference}/{filename}'


class ArticleQR(TimestampedModel):
    """
    QR code data for articles.
    Auto-generated when article is created.
    """
    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
        related_name='qr_code',
        verbose_name=_('Article')
    )
    
    payload_url = models.CharField(
        max_length=200,
        verbose_name=_('QR payload URL'),
        help_text=_('URL encoded in QR code')
    )
    
    png_file = models.ImageField(
        upload_to=qr_upload_path,
        verbose_name=_('QR code image'),
        help_text=_('Generated QR code PNG file')
    )
    
    class Meta:
        verbose_name = _('Article QR Code')
        verbose_name_plural = _('Article QR Codes')
        db_table = 'inventory_article_qr'
    
    def __str__(self):
        return f"QR Code for {self.article.reference}"
    
    def delete(self, *args, **kwargs):
        """Delete QR code file when object is deleted."""
        if self.png_file:
            if os.path.isfile(self.png_file.path):
                os.remove(self.png_file.path)
        super().delete(*args, **kwargs)


class StockTech(TimestampedModel):
    """
    Stock level per technician per article.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='stock_items',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='tech_stocks',
        verbose_name=_('Article')
    )
    
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Quantity')
    )
    
    reserved_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Reserved quantity'),
        help_text=_('Quantity reserved for approved demands')
    )
    
    class Meta:
        verbose_name = _('Technician Stock')
        verbose_name_plural = _('Technician Stocks')
        db_table = 'inventory_stock_tech'
        unique_together = [('technician', 'article')]
        indexes = [
            models.Index(fields=['technician']),
            models.Index(fields=['article']),
            models.Index(fields=['quantity']),
        ]
    
    def __str__(self):
        return f"{self.technician.display_name} - {self.article.reference}: {self.quantity}"
    
    @property
    def available_quantity(self):
        """Calculate available quantity (total - reserved)."""
        return self.quantity - self.reserved_qty
    
    def reserve_quantity(self, qty):
        """Reserve quantity for a demand."""
        if qty > self.available_quantity:
            raise ValueError("Not enough available quantity to reserve")
        self.reserved_qty += qty
        self.save(update_fields=['reserved_qty', 'updated_at'])
    
    def release_reservation(self, qty):
        """Release reserved quantity."""
        if qty > self.reserved_qty:
            raise ValueError("Cannot release more than reserved")
        self.reserved_qty -= qty
        self.save(update_fields=['reserved_qty', 'updated_at'])
    
    def consume_stock(self, qty):
        """Consume stock (reduce both quantity and reserved)."""
        if qty > self.quantity:
            raise ValueError("Not enough stock to consume")
        self.quantity -= qty
        if self.reserved_qty > 0:
            consumed_from_reserved = min(qty, self.reserved_qty)
            self.reserved_qty -= consumed_from_reserved
        self.save(update_fields=['quantity', 'reserved_qty', 'updated_at'])


class Threshold(TimestampedModel):
    """
    Stock threshold alerts per technician per article.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='thresholds',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='thresholds',
        verbose_name=_('Article')
    )
    
    min_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_('Minimum quantity'),
        help_text=_('Alert when stock falls below this level')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    
    last_alert_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last alert sent')
    )
    
    class Meta:
        verbose_name = _('Stock Threshold')
        verbose_name_plural = _('Stock Thresholds')
        db_table = 'inventory_threshold'
        unique_together = [('technician', 'article')]
        indexes = [
            models.Index(fields=['technician']),
            models.Index(fields=['article']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.technician.display_name} - {self.article.reference}: min {self.min_qty}"
    
    def check_threshold(self):
        """Check if current stock is below threshold."""
        try:
            stock = StockTech.objects.get(
                technician=self.technician,
                article=self.article
            )
            return stock.available_quantity <= self.min_qty
        except StockTech.DoesNotExist:
            return True  # No stock = below threshold
