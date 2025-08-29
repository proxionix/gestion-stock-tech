"""
Unit tests for Stock Management System models.
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.contrib.auth import get_user_model
from apps.users.models import Profile
from apps.inventory.models import Article, ArticleQR, StockTech, Threshold
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine
from apps.audit.models import StockMovement, EventLog

User = get_user_model()


class TestProfileModel:
    """Test Profile model."""
    
    def test_profile_creation(self, db):
        """Test profile creation."""
        user = User.objects.create_user(username='test', email='test@test.com')
        profile = Profile.objects.create(
            user=user,
            role=Profile.Role.TECH,
            language_pref='fr'
        )
        
        assert profile.user == user
        assert profile.role == Profile.Role.TECH
        assert profile.language_pref == 'fr'
        assert profile.is_technician is True
        assert profile.is_admin is False
    
    def test_profile_unique_user(self, db):
        """Test that profile has unique user constraint."""
        user = User.objects.create_user(username='test', email='test@test.com')
        Profile.objects.create(user=user, role=Profile.Role.TECH)
        
        with pytest.raises(IntegrityError):
            Profile.objects.create(user=user, role=Profile.Role.ADMIN)
    
    def test_profile_str_representation(self, technician_user):
        """Test profile string representation."""
        assert str(technician_user.profile) == f"tech_test (TECH)"
    
    def test_is_admin_property(self, admin_user):
        """Test is_admin property."""
        assert admin_user.profile.is_admin is True
        assert admin_user.profile.is_technician is False
    
    def test_is_technician_property(self, technician_user):
        """Test is_technician property."""
        assert technician_user.profile.is_technician is True
        assert technician_user.profile.is_admin is False


class TestArticleModel:
    """Test Article model."""
    
    def test_article_creation(self, test_article):
        """Test article creation."""
        assert test_article.reference == 'TEST001'
        assert test_article.name == 'Test Article'
        assert test_article.is_active is True
        assert test_article.created_at is not None
    
    def test_article_unique_reference(self, db):
        """Test that article reference is unique."""
        Article.objects.create(reference='UNIQUE001', name='Test')
        
        with pytest.raises(IntegrityError):
            Article.objects.create(reference='UNIQUE001', name='Test 2')
    
    def test_article_str_representation(self, test_article):
        """Test article string representation."""
        assert str(test_article) == "TEST001 - Test Article"
    
    def test_article_qr_creation_signal(self, db):
        """Test that QR code is created when article is saved."""
        article = Article.objects.create(
            reference='QR001',
            name='QR Test Article',
            unit='PCS'
        )
        
        # Check that ArticleQR is created
        assert hasattr(article, 'qr_code')
        assert article.qr_code.payload_url == f"/a/{article.reference}"
    
    def test_article_slug_generation(self, test_article):
        """Test article slug generation if implemented."""
        # This would test slug generation if we implemented it
        pass


class TestStockTechModel:
    """Test StockTech model."""
    
    def test_stock_creation(self, technician_stock):
        """Test stock creation."""
        assert technician_stock.quantity == 50
        assert technician_stock.technician.user.username == 'tech_test'
        assert technician_stock.article.reference == 'TEST001'
    
    def test_stock_unique_constraint(self, technician_user, test_article):
        """Test unique constraint on technician + article."""
        StockTech.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity=30
        )
        
        with pytest.raises(IntegrityError):
            StockTech.objects.create(
                technician=technician_user.profile,
                article=test_article,
                quantity=40
            )
    
    def test_stock_negative_quantity_validation(self, technician_user, test_article):
        """Test that negative quantity raises validation error."""
        stock = StockTech(
            technician=technician_user.profile,
            article=test_article,
            quantity=-10
        )
        
        with pytest.raises(ValidationError):
            stock.full_clean()
    
    def test_stock_str_representation(self, technician_stock):
        """Test stock string representation."""
        expected = f"tech_test - TEST001: 50 PCS"
        assert str(technician_stock) == expected


class TestThresholdModel:
    """Test Threshold model."""
    
    def test_threshold_creation(self, threshold):
        """Test threshold creation."""
        assert threshold.min_quantity == 10
        assert threshold.technician.user.username == 'tech_test'
        assert threshold.article.reference == 'TEST001'
    
    def test_threshold_unique_constraint(self, technician_user, test_article):
        """Test unique constraint on technician + article."""
        Threshold.objects.create(
            technician=technician_user.profile,
            article=test_article,
            min_quantity=5
        )
        
        with pytest.raises(IntegrityError):
            Threshold.objects.create(
                technician=technician_user.profile,
                article=test_article,
                min_quantity=15
            )
    
    def test_threshold_negative_validation(self, technician_user, test_article):
        """Test that negative threshold raises validation error."""
        threshold = Threshold(
            technician=technician_user.profile,
            article=test_article,
            min_quantity=-5
        )
        
        with pytest.raises(ValidationError):
            threshold.full_clean()


class TestPanierModel:
    """Test Panier model."""
    
    def test_panier_creation(self, draft_panier):
        """Test panier creation."""
        assert draft_panier.status == Panier.Status.DRAFT
        assert draft_panier.technician.user.username == 'tech_test'
        assert draft_panier.created_at is not None
    
    def test_panier_unique_draft_constraint(self, technician_user):
        """Test that only one draft panier per technician is allowed."""
        Panier.objects.create(
            technician=technician_user.profile,
            status=Panier.Status.DRAFT
        )
        
        with pytest.raises(IntegrityError):
            Panier.objects.create(
                technician=technician_user.profile,
                status=Panier.Status.DRAFT
            )
    
    def test_panier_multiple_submitted_allowed(self, technician_user):
        """Test that multiple submitted paniers are allowed."""
        Panier.objects.create(
            technician=technician_user.profile,
            status=Panier.Status.SUBMITTED
        )
        Panier.objects.create(
            technician=technician_user.profile,
            status=Panier.Status.SUBMITTED
        )
        
        # Should not raise exception
        assert Panier.objects.filter(technician=technician_user.profile).count() == 2
    
    def test_panier_str_representation(self, draft_panier):
        """Test panier string representation."""
        expected = f"Panier tech_test - DRAFT"
        assert str(draft_panier) == expected


class TestPanierLineModel:
    """Test PanierLine model."""
    
    def test_panier_line_creation(self, draft_panier, test_article):
        """Test panier line creation."""
        line = PanierLine.objects.create(
            panier=draft_panier,
            article=test_article,
            quantity=5
        )
        
        assert line.quantity == 5
        assert line.article == test_article
        assert line.panier == draft_panier
    
    def test_panier_line_unique_constraint(self, draft_panier, test_article):
        """Test unique constraint on panier + article."""
        PanierLine.objects.create(
            panier=draft_panier,
            article=test_article,
            quantity=3
        )
        
        with pytest.raises(IntegrityError):
            PanierLine.objects.create(
                panier=draft_panier,
                article=test_article,
                quantity=7
            )
    
    def test_panier_line_positive_quantity_validation(self, draft_panier, test_article):
        """Test that zero or negative quantity raises validation error."""
        line_zero = PanierLine(
            panier=draft_panier,
            article=test_article,
            quantity=0
        )
        
        with pytest.raises(ValidationError):
            line_zero.full_clean()
        
        line_negative = PanierLine(
            panier=draft_panier,
            article=test_article,
            quantity=-1
        )
        
        with pytest.raises(ValidationError):
            line_negative.full_clean()


class TestDemandeModel:
    """Test Demande model."""
    
    def test_demande_creation(self, test_demande):
        """Test demande creation."""
        assert test_demande.status == Demande.Status.SUBMITTED
        assert test_demande.technician.user.username == 'tech_test'
        assert test_demande.created_at is not None
        assert test_demande.updated_at is not None
    
    def test_demande_str_representation(self, test_demande):
        """Test demande string representation."""
        expected = f"Demande {test_demande.id} - tech_test (SUBMITTED)"
        assert str(test_demande) == expected
    
    def test_demande_status_choices(self, technician_user):
        """Test all demande status choices."""
        for status, _ in Demande.Status.choices:
            demande = Demande.objects.create(
                technician=technician_user.profile,
                status=status
            )
            assert demande.status == status


class TestDemandeLineModel:
    """Test DemandeLine model."""
    
    def test_demande_line_creation(self, test_demande, test_article):
        """Test demande line creation."""
        line = DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=10,
            quantity_approved=8,
            quantity_prepared=8
        )
        
        assert line.quantity_requested == 10
        assert line.quantity_approved == 8
        assert line.quantity_prepared == 8
    
    def test_demande_line_unique_constraint(self, test_demande, test_article):
        """Test unique constraint on demande + article."""
        DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=5
        )
        
        with pytest.raises(IntegrityError):
            DemandeLine.objects.create(
                demande=test_demande,
                article=test_article,
                quantity_requested=10
            )
    
    def test_demande_line_quantity_validations(self, test_demande, test_article):
        """Test quantity validations."""
        # Negative requested quantity
        with pytest.raises(ValidationError):
            line = DemandeLine(
                demande=test_demande,
                article=test_article,
                quantity_requested=-1
            )
            line.full_clean()
        
        # Negative approved quantity
        with pytest.raises(ValidationError):
            line = DemandeLine(
                demande=test_demande,
                article=test_article,
                quantity_requested=10,
                quantity_approved=-1
            )
            line.full_clean()


class TestStockMovementModel:
    """Test StockMovement model."""
    
    def test_stock_movement_creation(self, technician_user, test_article):
        """Test stock movement creation."""
        movement = StockMovement.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity_delta=10,
            movement_type=StockMovement.MovementType.RECEIPT,
            location_text='Test location'
        )
        
        assert movement.quantity_delta == 10
        assert movement.movement_type == StockMovement.MovementType.RECEIPT
        assert movement.location_text == 'Test location'
        assert movement.timestamp is not None
    
    def test_stock_movement_str_representation(self, technician_user, test_article):
        """Test stock movement string representation."""
        movement = StockMovement.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity_delta=-5,
            movement_type=StockMovement.MovementType.ISSUE
        )
        
        expected = f"tech_test - TEST001: -5 (ISSUE)"
        assert str(movement) == expected


class TestEventLogModel:
    """Test EventLog model."""
    
    def test_event_log_creation(self, event_log_sample):
        """Test event log creation."""
        assert event_log_sample.entity_type == 'Article'
        assert event_log_sample.action == 'CREATE'
        assert event_log_sample.after_data == {'name': 'Test Article'}
        assert event_log_sample.hash_value == 'sample_hash'
        assert event_log_sample.timestamp is not None
    
    def test_event_log_str_representation(self, event_log_sample):
        """Test event log string representation."""
        expected = f"Article test-id CREATE by admin_test"
        assert str(event_log_sample) == expected
    
    def test_event_log_hash_chaining(self, admin_user):
        """Test event log hash chaining."""
        # Create first event
        event1 = EventLog.objects.create(
            actor_user=admin_user,
            entity_type='Test',
            entity_id='1',
            action='CREATE',
            after_data={'test': 'data'},
            hash_value='hash1'
        )
        
        # Create second event
        event2 = EventLog.objects.create(
            actor_user=admin_user,
            entity_type='Test',
            entity_id='2',
            action='UPDATE',
            before_data={'test': 'data'},
            after_data={'test': 'new_data'},
            previous_hash=event1.hash_value,
            hash_value='hash2'
        )
        
        assert event2.previous_hash == event1.hash_value
