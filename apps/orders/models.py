"""
Orders models for Stock Management System.
"""
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.core.models import BaseModel, TimestampedModel
from apps.users.models import Profile
from apps.inventory.models import Article
from django.utils import timezone


class PanierStatus(models.TextChoices):
    """Cart status choices."""
    DRAFT = 'DRAFT', _('Draft')
    SUBMITTED = 'SUBMITTED', _('Submitted')


class DemandeStatus(models.TextChoices):
    """Demand status choices."""
    SUBMITTED = 'SUBMITTED', _('Submitted')
    APPROVED = 'APPROVED', _('Approved')
    PARTIAL = 'PARTIAL', _('Partially Approved')
    REFUSED = 'REFUSED', _('Refused')
    PREPARED = 'PREPARED', _('Prepared')
    HANDED_OVER = 'HANDED_OVER', _('Handed Over')
    CLOSED = 'CLOSED', _('Closed')


class HandoverMethod(models.TextChoices):
    """Handover confirmation method choices."""
    SIGNATURE = 'SIGNATURE', _('Digital Signature')
    PIN = 'PIN', _('PIN Code')


class Panier(BaseModel):
    """
    Shopping cart for technicians.
    Only one DRAFT cart per technician allowed.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='paniers',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    status = models.CharField(
        max_length=20,
        choices=PanierStatus.choices,
        default=PanierStatus.DRAFT,
        verbose_name=_('Status')
    )
    
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Submitted at')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes for this cart')
    )
    
    class Meta:
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        db_table = 'orders_panier'
        constraints = [
            models.UniqueConstraint(
                fields=['technician'],
                condition=models.Q(status=PanierStatus.DRAFT),
                name='unique_draft_cart_per_technician'
            )
        ]
        indexes = [
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Cart {self.id} - {self.technician.display_name} ({self.status})"
    
    @property
    def total_items(self):
        """Get total number of items in cart."""
        return self.lines.count()
    
    @property
    def total_quantity(self):
        """Get total quantity of all items in cart."""
        return sum(line.quantity for line in self.lines.all())
    
    def can_be_submitted(self):
        """Check if cart can be submitted."""
        return (
            self.status == PanierStatus.DRAFT and
            self.lines.exists() and
            all(line.article.is_active for line in self.lines.all())
        )
    
    def submit(self):
        """Submit cart and create demand."""
        if not self.can_be_submitted():
            raise ValueError("Cart cannot be submitted")
        
        with transaction.atomic():
            # Update cart status
            self.status = PanierStatus.SUBMITTED
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at', 'updated_at'])
            
            # Create demand
            demande = Demande.objects.create(
                technician=self.technician,
                status=DemandeStatus.SUBMITTED,
                panier=self,
                notes=self.notes
            )
            
            # Create demand lines from cart lines
            for line in self.lines.all():
                DemandeLine.objects.create(
                    demande=demande,
                    article=line.article,
                    qty_requested=line.quantity
                )
            
            return demande


class PanierLine(TimestampedModel):
    """
    Line item in a shopping cart.
    """
    panier = models.ForeignKey(
        Panier,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Cart')
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='panier_lines',
        verbose_name=_('Article')
    )
    
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Quantity')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    
    class Meta:
        verbose_name = _('Cart Line')
        verbose_name_plural = _('Cart Lines')
        db_table = 'orders_panier_line'
        unique_together = [('panier', 'article')]
        indexes = [
            models.Index(fields=['panier']),
            models.Index(fields=['article']),
        ]
    
    def __str__(self):
        return f"{self.panier} - {self.article.reference}: {self.quantity}"


class Demande(BaseModel):
    """
    Demand/Request for materials.
    Created from submitted cart.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='demandes',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    status = models.CharField(
        max_length=20,
        choices=DemandeStatus.choices,
        default=DemandeStatus.SUBMITTED,
        verbose_name=_('Status')
    )
    
    panier = models.OneToOneField(
        Panier,
        on_delete=models.PROTECT,
        related_name='demande',
        verbose_name=_('Original cart')
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_demandes',
        verbose_name=_('Approved by')
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved at')
    )
    
    prepared_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='prepared_demandes',
        verbose_name=_('Prepared by')
    )
    
    prepared_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Prepared at')
    )
    
    handover_method = models.CharField(
        max_length=20,
        choices=HandoverMethod.choices,
        null=True,
        blank=True,
        verbose_name=_('Handover method')
    )
    
    handover_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Handover data'),
        help_text=_('Signature or PIN confirmation data')
    )
    
    handed_over_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Handed over at')
    )
    
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Closed at')
    )
    
    refusal_reason = models.TextField(
        blank=True,
        verbose_name=_('Refusal reason')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    
    priority = models.CharField(
        max_length=20,
        choices=[
            ('LOW', _('Low')),
            ('NORMAL', _('Normal')),
            ('HIGH', _('High')),
            ('URGENT', _('Urgent')),
        ],
        default='NORMAL',
        verbose_name=_('Priority')
    )
    
    class Meta:
        verbose_name = _('Demand')
        verbose_name_plural = _('Demands')
        db_table = 'orders_demande'
        indexes = [
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['priority']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Demand {self.id} - {self.technician.display_name} ({self.status})"
    
    @property
    def total_requested_items(self):
        """Get total number of different items requested."""
        return self.lines.count()
    
    @property
    def total_requested_quantity(self):
        """Get total requested quantity."""
        return sum(line.qty_requested for line in self.lines.all())
    
    @property
    def total_approved_quantity(self):
        """Get total approved quantity."""
        return sum(line.qty_approved for line in self.lines.all())
    
    @property
    def is_fully_approved(self):
        """Check if all requested quantities are approved."""
        return all(
            line.qty_approved == line.qty_requested
            for line in self.lines.all()
        )
    
    @property
    def is_partially_approved(self):
        """Check if only some quantities are approved."""
        return any(
            0 < line.qty_approved < line.qty_requested
            for line in self.lines.all()
        )
    
    def can_be_prepared(self):
        """Check if demand can be prepared."""
        return (
            self.status in [DemandeStatus.APPROVED, DemandeStatus.PARTIAL] and
            self.total_approved_quantity > 0
        )
    
    def can_be_handed_over(self):
        """Check if demand can be handed over."""
        return self.status == DemandeStatus.PREPARED


class DemandeLine(TimestampedModel):
    """
    Line item in a demand.
    """
    demande = models.ForeignKey(
        Demande,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Demand')
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='demande_lines',
        verbose_name=_('Article')
    )
    
    qty_requested = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Requested quantity')
    )
    
    qty_approved = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Approved quantity')
    )
    
    qty_prepared = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Prepared quantity')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    
    class Meta:
        verbose_name = _('Demand Line')
        verbose_name_plural = _('Demand Lines')
        db_table = 'orders_demande_line'
        unique_together = [('demande', 'article')]
        indexes = [
            models.Index(fields=['demande']),
            models.Index(fields=['article']),
        ]
    
    def __str__(self):
        return f"{self.demande} - {self.article.reference}: {self.qty_requested}"
    
    @property
    def is_fully_approved(self):
        """Check if requested quantity is fully approved."""
        return self.qty_approved == self.qty_requested
    
    @property
    def is_partially_approved(self):
        """Check if quantity is partially approved."""
        return 0 < self.qty_approved < self.qty_requested


# Reservations for planned interventions
class ReservationStatus(models.TextChoices):
    """Reservation status choices."""
    PENDING = 'PENDING', _('Pending')
    APPROVED = 'APPROVED', _('Approved')
    CANCELLED = 'CANCELLED', _('Cancelled')


class Reservation(BaseModel):
    """
    Planned reservation that deducts availability when approved.
    Created by Technician or Admin, approved by Admin.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name=_('Article')
    )
    qty_reserved = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Reserved quantity')
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Scheduled for')
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
        verbose_name=_('Status')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_reservations',
        verbose_name=_('Created by')
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_reservations',
        verbose_name=_('Approved by')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved at')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )

    class Meta:
        verbose_name = _('Reservation')
        verbose_name_plural = _('Reservations')
        db_table = 'orders_reservation'
        indexes = [
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['article']),
            models.Index(fields=['scheduled_for']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Reservation {self.id} - {self.technician.display_name} {self.article.reference} ({self.status})"

    def can_approve(self) -> bool:
        return self.status == ReservationStatus.PENDING and self.qty_reserved > 0

    def approve(self, approved_by: User):
        """Approve and reserve stock for technician. Transaction handled at service/view layer."""
        if not self.can_approve():
            raise ValueError('Reservation cannot be approved')
        from apps.inventory.models import StockTech
        # Lock and reserve
        stock, _ = StockTech.objects.select_for_update().get_or_create(
            technician=self.technician,
            article=self.article,
            defaults={'quantity': Decimal('0')}
        )
        stock.reserve_quantity(self.qty_reserved)
        self.status = ReservationStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
