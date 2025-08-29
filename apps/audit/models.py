"""
Audit models for Stock Management System.
Immutable audit trail with hash chaining for integrity.
"""
import hashlib
import json
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.core.models import BaseModel, TimestampedModel
from apps.users.models import Profile
from apps.inventory.models import Article
from apps.orders.models import Demande


class MovementReason(models.TextChoices):
    """Stock movement reason choices."""
    ISSUE = 'ISSUE', _('Issue/Usage')
    RECEIPT = 'RECEIPT', _('Receipt from demand')
    ADJUST = 'ADJUST', _('Manual adjustment')
    TRANSFER = 'TRANSFER', _('Transfer between technicians')
    INITIAL = 'INITIAL', _('Initial stock')


class StockMovement(BaseModel):
    """
    Immutable stock movement records.
    All stock changes must be recorded here.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name=_('Article')
    )
    
    delta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Quantity change'),
        help_text=_('Positive for increase, negative for decrease')
    )
    
    reason = models.CharField(
        max_length=20,
        choices=MovementReason.choices,
        verbose_name=_('Reason')
    )
    
    linked_demande = models.ForeignKey(
        Demande,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name=_('Related demand')
    )
    
    location_text = models.TextField(
        blank=True,
        verbose_name=_('Location/Usage description'),
        help_text=_('Where the material was used or stored')
    )
    
    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='performed_movements',
        verbose_name=_('Performed by')
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Timestamp')
    )
    
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_('Balance after movement')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    
    # Audit integrity fields
    record_hash = models.CharField(
        max_length=64,
        editable=False,
        verbose_name=_('Record hash'),
        help_text=_('SHA-256 hash of this record')
    )
    
    class Meta:
        verbose_name = _('Stock Movement')
        verbose_name_plural = _('Stock Movements')
        db_table = 'audit_stock_movement'
        indexes = [
            models.Index(fields=['technician', 'article']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['reason']),
            models.Index(fields=['linked_demande']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.technician.display_name} - {self.article.reference}: {self.delta} ({self.reason})"
    
    def save(self, *args, **kwargs):
        """Override save to calculate record hash."""
        if not self.record_hash:
            self.record_hash = self._calculate_hash()
        super().save(*args, **kwargs)
    
    def _calculate_hash(self):
        """Calculate SHA-256 hash of record data."""
        data = {
            'technician_id': str(self.technician_id),
            'article_id': str(self.article_id),
            'delta': str(self.delta),
            'reason': self.reason,
            'linked_demande_id': str(self.linked_demande_id) if self.linked_demande_id else None,
            'location_text': self.location_text,
            'performed_by_id': str(self.performed_by_id),
            'timestamp': self.timestamp.isoformat(),
            'balance_after': str(self.balance_after),
            'notes': self.notes,
        }
        json_data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_data.encode()).hexdigest()
    
    def verify_hash(self):
        """Verify record integrity by recalculating hash."""
        calculated_hash = self._calculate_hash()
        return calculated_hash == self.record_hash


class EventLog(BaseModel):
    """
    Immutable audit log for all significant events.
    Uses hash chaining for tamper detection.
    """
    actor_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='audit_events',
        verbose_name=_('Actor user')
    )
    
    entity_type = models.CharField(
        max_length=50,
        verbose_name=_('Entity type'),
        help_text=_('Model name of the affected entity')
    )
    
    entity_id = models.CharField(
        max_length=36,
        verbose_name=_('Entity ID'),
        help_text=_('Primary key of the affected entity')
    )
    
    action = models.CharField(
        max_length=50,
        verbose_name=_('Action'),
        help_text=_('What action was performed')
    )
    
    before_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Before data'),
        help_text=_('Entity state before the change')
    )
    
    after_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('After data'),
        help_text=_('Entity state after the change')
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Timestamp')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP address')
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User agent')
    )
    
    request_id = models.CharField(
        max_length=36,
        blank=True,
        verbose_name=_('Request ID'),
        help_text=_('Unique request identifier for correlation')
    )
    
    # Hash chaining for integrity
    prev_hash = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Previous record hash'),
        help_text=_('Hash of the previous audit record')
    )
    
    record_hash = models.CharField(
        max_length=64,
        editable=False,
        unique=True,
        verbose_name=_('Record hash'),
        help_text=_('SHA-256 hash of this record')
    )
    
    class Meta:
        verbose_name = _('Event Log')
        verbose_name_plural = _('Event Logs')
        db_table = 'audit_event_log'
        indexes = [
            models.Index(fields=['actor_user']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['request_id']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.actor_user.username} - {self.action} on {self.entity_type}:{self.entity_id}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate hashes and maintain chain."""
        if not self.record_hash:
            # Get the previous record's hash
            last_record = EventLog.objects.order_by('-timestamp').first()
            self.prev_hash = last_record.record_hash if last_record else ''
            
            # Calculate this record's hash
            self.record_hash = self._calculate_hash()
        
        super().save(*args, **kwargs)
    
    def _calculate_hash(self):
        """Calculate SHA-256 hash of record data."""
        data = {
            'actor_user_id': str(self.actor_user_id),
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'before_data': self.before_data,
            'after_data': self.after_data,
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent[:200] if self.user_agent else '',  # Truncate
            'request_id': self.request_id,
            'prev_hash': self.prev_hash,
        }
        json_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_data.encode()).hexdigest()
    
    def verify_hash(self):
        """Verify record integrity by recalculating hash."""
        calculated_hash = self._calculate_hash()
        return calculated_hash == self.record_hash
    
    def verify_chain(self):
        """Verify hash chain integrity with previous record."""
        if not self.prev_hash:
            # First record, check if it's actually the first
            earlier_records = EventLog.objects.filter(timestamp__lt=self.timestamp)
            return not earlier_records.exists()
        
        try:
            prev_record = EventLog.objects.filter(
                record_hash=self.prev_hash
            ).first()
            return prev_record is not None
        except EventLog.DoesNotExist:
            return False


class ThresholdAlert(BaseModel):
    """
    Records of threshold alerts sent.
    """
    technician = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name='threshold_alerts',
        verbose_name=_('Technician'),
        limit_choices_to={'role': 'TECH'}
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='threshold_alerts',
        verbose_name=_('Article')
    )
    
    current_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_('Current stock level')
    )
    
    threshold_level = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_('Threshold level')
    )
    
    alert_sent_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Alert sent at')
    )
    
    alert_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', _('Email')),
            ('SYSTEM', _('System notification')),
            ('SMS', _('SMS')),
        ],
        default='SYSTEM',
        verbose_name=_('Alert method')
    )
    
    acknowledged = models.BooleanField(
        default=False,
        verbose_name=_('Acknowledged')
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Acknowledged at')
    )
    
    class Meta:
        verbose_name = _('Threshold Alert')
        verbose_name_plural = _('Threshold Alerts')
        db_table = 'audit_threshold_alert'
        indexes = [
            models.Index(fields=['technician', 'article']),
            models.Index(fields=['alert_sent_at']),
            models.Index(fields=['acknowledged']),
        ]
        ordering = ['-alert_sent_at']
    
    def __str__(self):
        return f"Alert: {self.technician.display_name} - {self.article.reference} below {self.threshold_level}"
