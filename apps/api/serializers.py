"""
Serializers for Stock Management System API.
"""
from decimal import Decimal
from typing import Dict, Any
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from apps.users.models import Profile, UserRole, LanguageChoice
from apps.inventory.models import Article, StockTech, Threshold
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine, HandoverMethod
from apps.audit.models import StockMovement, EventLog, ThresholdAlert


# User and Authentication Serializers

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile model."""
    user = UserSerializer(read_only=True)
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'user', 'role', 'language_pref', 'is_active',
            'employee_id', 'department', 'phone', 'display_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if user:
                if user.is_active:
                    attrs['user'] = user
                    return attrs
                else:
                    raise serializers.ValidationError(_('User account is disabled.'))
            else:
                raise serializers.ValidationError(_('Invalid username or password.'))
        else:
            raise serializers.ValidationError(_('Must include username and password.'))


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for token refresh."""
    refresh_token = serializers.CharField()


# Inventory Serializers

class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model."""
    qr_code_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id', 'reference', 'name', 'description', 'unit', 'is_active',
            'category', 'manufacturer', 'model_number', 'safety_stock',
            'cost_price', 'qr_code_url', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_reference(self, value):
        """Validate article reference uniqueness."""
        if self.instance:
            # Updating existing article
            if Article.objects.exclude(id=self.instance.id).filter(reference=value).exists():
                raise serializers.ValidationError(_('Article with this reference already exists.'))
        else:
            # Creating new article
            if Article.objects.filter(reference=value).exists():
                raise serializers.ValidationError(_('Article with this reference already exists.'))
        return value


class StockTechSerializer(serializers.ModelSerializer):
    """Serializer for StockTech model."""
    technician = ProfileSerializer(read_only=True)
    article = ArticleSerializer(read_only=True)
    available_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = StockTech
        fields = [
            'technician', 'article', 'quantity', 'reserved_qty',
            'available_quantity', 'updated_at'
        ]
        read_only_fields = ['updated_at']


class ThresholdSerializer(serializers.ModelSerializer):
    """Serializer for Threshold model."""
    technician = ProfileSerializer(read_only=True)
    article = ArticleSerializer(read_only=True)
    
    class Meta:
        model = Threshold
        fields = [
            'id', 'technician', 'article', 'min_qty', 'is_active',
            'last_alert_sent', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# Orders Serializers

class PanierLineSerializer(serializers.ModelSerializer):
    """Serializer for PanierLine model."""
    article = ArticleSerializer(read_only=True)
    article_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = PanierLine
        fields = [
            'id', 'article', 'article_id', 'quantity', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value <= 0:
            raise serializers.ValidationError(_('Quantity must be positive.'))
        return value


class PanierSerializer(serializers.ModelSerializer):
    """Serializer for Panier model."""
    technician = ProfileSerializer(read_only=True)
    lines = PanierLineSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_be_submitted = serializers.SerializerMethodField()
    
    class Meta:
        model = Panier
        fields = [
            'id', 'technician', 'status', 'submitted_at', 'notes',
            'lines', 'total_items', 'total_quantity', 'can_be_submitted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'submitted_at', 'created_at', 'updated_at']
    
    def get_can_be_submitted(self, obj):
        """Check if cart can be submitted."""
        return obj.can_be_submitted()


class AddToCartSerializer(serializers.Serializer):
    """Serializer for adding items to cart."""
    article_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value <= 0:
            raise serializers.ValidationError(_('Quantity must be positive.'))
        return value
    
    def validate_article_id(self, value):
        """Validate article exists and is active."""
        try:
            article = Article.objects.get(id=value)
            if not article.is_active:
                raise serializers.ValidationError(_('Article is not active.'))
            return value
        except Article.DoesNotExist:
            raise serializers.ValidationError(_('Article not found.'))


class UpdateCartLineSerializer(serializers.Serializer):
    """Serializer for updating cart line quantity."""
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def validate_quantity(self, value):
        """Validate quantity is positive or zero (zero means remove)."""
        if value < 0:
            raise serializers.ValidationError(_('Quantity cannot be negative.'))
        return value


class DemandeLineSerializer(serializers.ModelSerializer):
    """Serializer for DemandeLine model."""
    article = ArticleSerializer(read_only=True)
    is_fully_approved = serializers.BooleanField(read_only=True)
    is_partially_approved = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = DemandeLine
        fields = [
            'id', 'article', 'qty_requested', 'qty_approved', 'qty_prepared',
            'notes', 'is_fully_approved', 'is_partially_approved',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DemandeSerializer(serializers.ModelSerializer):
    """Serializer for Demande model."""
    technician = ProfileSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    prepared_by = UserSerializer(read_only=True)
    lines = DemandeLineSerializer(many=True, read_only=True)
    total_requested_items = serializers.IntegerField(read_only=True)
    total_requested_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_approved_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_fully_approved = serializers.BooleanField(read_only=True)
    is_partially_approved = serializers.BooleanField(read_only=True)
    can_be_prepared = serializers.SerializerMethodField()
    can_be_handed_over = serializers.SerializerMethodField()
    
    class Meta:
        model = Demande
        fields = [
            'id', 'technician', 'status', 'panier', 'approved_by', 'approved_at',
            'prepared_by', 'prepared_at', 'handover_method', 'handover_data',
            'handed_over_at', 'closed_at', 'refusal_reason', 'notes', 'priority',
            'lines', 'total_requested_items', 'total_requested_quantity',
            'total_approved_quantity', 'is_fully_approved', 'is_partially_approved',
            'can_be_prepared', 'can_be_handed_over', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'technician', 'status', 'panier', 'approved_by', 'approved_at',
            'prepared_by', 'prepared_at', 'handover_method', 'handover_data',
            'handed_over_at', 'closed_at', 'created_at', 'updated_at'
        ]
    
    def get_can_be_prepared(self, obj):
        """Check if demand can be prepared."""
        return obj.can_be_prepared()
    
    def get_can_be_handed_over(self, obj):
        """Check if demand can be handed over."""
        return obj.can_be_handed_over()


class ApprovePartialSerializer(serializers.Serializer):
    """Serializer for partial demand approval."""
    line_approvals = serializers.ListField(
        child=serializers.DictField()
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_line_approvals(self, value):
        """Validate line approvals format."""
        for approval in value:
            if 'line_id' not in approval or 'qty_approved' not in approval:
                raise serializers.ValidationError(
                    _('Each approval must have line_id and qty_approved.')
                )
            try:
                Decimal(str(approval['qty_approved']))
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    _('qty_approved must be a valid decimal number.')
                )
        return value


class RefuseDemandeSerializer(serializers.Serializer):
    """Serializer for demand refusal."""
    reason = serializers.CharField()


class HandoverSerializer(serializers.Serializer):
    """Serializer for demand handover."""
    method = serializers.ChoiceField(choices=HandoverMethod.choices)
    device_info = serializers.DictField()
    pin = serializers.CharField(required=False, allow_blank=True)
    signature_data = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate handover data based on method."""
        method = attrs.get('method')
        
        if method == HandoverMethod.PIN:
            if not attrs.get('pin'):
                raise serializers.ValidationError({'pin': _('PIN is required for PIN handover.')})
        elif method == HandoverMethod.SIGNATURE:
            if not attrs.get('signature_data'):
                raise serializers.ValidationError({'signature_data': _('Signature is required for signature handover.')})
        
        return attrs


class IssueStockSerializer(serializers.Serializer):
    """Serializer for stock usage declaration."""
    article_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    location_text = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value <= 0:
            raise serializers.ValidationError(_('Quantity must be positive.'))
        return value
    
    def validate_article_id(self, value):
        """Validate article exists."""
        try:
            Article.objects.get(id=value)
            return value
        except Article.DoesNotExist:
            raise serializers.ValidationError(_('Article not found.'))


# Audit Serializers

class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement model."""
    technician = ProfileSerializer(read_only=True)
    article = ArticleSerializer(read_only=True)
    performed_by = UserSerializer(read_only=True)
    linked_demande = DemandeSerializer(read_only=True)
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'technician', 'article', 'delta', 'reason', 'linked_demande',
            'location_text', 'performed_by', 'timestamp', 'balance_after',
            'notes', 'record_hash'
        ]
        read_only_fields = ['id', 'record_hash']


class EventLogSerializer(serializers.ModelSerializer):
    """Serializer for EventLog model."""
    actor_user = UserSerializer(read_only=True)
    
    class Meta:
        model = EventLog
        fields = [
            'id', 'actor_user', 'entity_type', 'entity_id', 'action',
            'before_data', 'after_data', 'timestamp', 'ip_address',
            'user_agent', 'request_id', 'prev_hash', 'record_hash'
        ]
        read_only_fields = ['id', 'prev_hash', 'record_hash']


class ThresholdAlertSerializer(serializers.ModelSerializer):
    """Serializer for ThresholdAlert model."""
    technician = ProfileSerializer(read_only=True)
    article = ArticleSerializer(read_only=True)
    
    class Meta:
        model = ThresholdAlert
        fields = [
            'id', 'technician', 'article', 'current_stock', 'threshold_level',
            'alert_sent_at', 'alert_method', 'acknowledged', 'acknowledged_at'
        ]
        read_only_fields = ['id']


# Health Check Serializers

class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check response."""
    status = serializers.CharField()
    version = serializers.CharField()
    timestamp = serializers.CharField()
    checks = serializers.DictField()
