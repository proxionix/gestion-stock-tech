"""
Unit tests for Stock Management System services.
"""
import pytest
from unittest.mock import patch, Mock
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.orders.services.panier_service import PanierService
from apps.orders.services.admin_workflow import AdminWorkflow
from apps.inventory.services.stock_service import StockService
from apps.inventory.services.threshold_service import ThresholdService
from apps.inventory.services.qr_service import QRService
from apps.audit.services.audit_service import AuditService
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine
from apps.inventory.models import StockTech, ArticleQR
from apps.audit.models import StockMovement, EventLog


class TestPanierService:
    """Test PanierService business logic."""
    
    def test_get_or_create_active_panier_new(self, technician_user):
        """Test getting or creating active panier when none exists."""
        panier = PanierService.get_or_create_active(technician_user.profile)
        
        assert panier.technician == technician_user.profile
        assert panier.status == Panier.Status.DRAFT
        assert Panier.objects.filter(technician=technician_user.profile).count() == 1
    
    def test_get_or_create_active_panier_existing(self, draft_panier):
        """Test getting existing active panier."""
        panier = PanierService.get_or_create_active(draft_panier.technician)
        
        assert panier.id == draft_panier.id
        assert Panier.objects.filter(technician=draft_panier.technician).count() == 1
    
    def test_add_line_new_article(self, draft_panier, test_article):
        """Test adding new article to panier."""
        line = PanierService.add_line(draft_panier, test_article, 5)
        
        assert line.article == test_article
        assert line.quantity == 5
        assert line.panier == draft_panier
    
    def test_add_line_existing_article(self, draft_panier, test_article):
        """Test adding existing article to panier (should update quantity)."""
        # Add initial line
        PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=3)
        
        # Add more
        line = PanierService.add_line(draft_panier, test_article, 2)
        
        assert line.quantity == 5  # 3 + 2
        assert PanierLine.objects.filter(panier=draft_panier, article=test_article).count() == 1
    
    def test_update_line_quantity(self, draft_panier, test_article):
        """Test updating line quantity."""
        line = PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=3)
        
        updated_line = PanierService.update_line_quantity(line, 8)
        
        assert updated_line.quantity == 8
        assert updated_line.id == line.id
    
    def test_update_line_quantity_zero_removes(self, draft_panier, test_article):
        """Test that updating quantity to zero removes the line."""
        line = PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=3)
        
        result = PanierService.update_line_quantity(line, 0)
        
        assert result is None
        assert not PanierLine.objects.filter(id=line.id).exists()
    
    def test_remove_line(self, draft_panier, test_article):
        """Test removing line from panier."""
        line = PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=3)
        
        PanierService.remove_line(line)
        
        assert not PanierLine.objects.filter(id=line.id).exists()
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_submit_panier_creates_demande(self, mock_audit, draft_panier, test_article, test_article_2):
        """Test submitting panier creates demande with lines."""
        # Add lines to panier
        PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=5)
        PanierLine.objects.create(panier=draft_panier, article=test_article_2, quantity=3)
        
        demande = PanierService.submit_panier(draft_panier)
        
        # Check demande creation
        assert demande.technician == draft_panier.technician
        assert demande.status == Demande.Status.SUBMITTED
        
        # Check demande lines
        lines = demande.lines.all()
        assert lines.count() == 2
        assert lines.filter(article=test_article, quantity_requested=5).exists()
        assert lines.filter(article=test_article_2, quantity_requested=3).exists()
        
        # Check panier status
        draft_panier.refresh_from_db()
        assert draft_panier.status == Panier.Status.SUBMITTED
        
        # Check audit logging
        mock_audit.assert_called()
    
    def test_submit_empty_panier_raises_error(self, draft_panier):
        """Test that submitting empty panier raises error."""
        with pytest.raises(ValidationError, match="Cannot submit empty cart"):
            PanierService.submit_panier(draft_panier)
    
    def test_submit_already_submitted_panier_raises_error(self, submitted_panier):
        """Test that submitting already submitted panier raises error."""
        with pytest.raises(ValidationError, match="Cart is already submitted"):
            PanierService.submit_panier(submitted_panier)


class TestAdminWorkflow:
    """Test AdminWorkflow business logic."""
    
    def test_get_demands_queue_for_technician(self, test_demande, technician_user):
        """Test getting demands queue for specific technician."""
        queue = AdminWorkflow.get_demands_queue(technician_user.profile)
        
        assert test_demande in queue
        assert queue.count() == 1
    
    def test_get_demands_queue_all(self, test_demande, second_technician_user):
        """Test getting all demands queue."""
        # Create another demande
        Demande.objects.create(
            technician=second_technician_user.profile,
            status=Demande.Status.SUBMITTED
        )
        
        queue = AdminWorkflow.get_demands_queue()
        
        assert queue.count() == 2
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_approve_demand_all(self, mock_audit, test_demande, test_article, admin_user):
        """Test approving entire demand."""
        # Add demande line
        DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=10
        )
        
        approved_demande = AdminWorkflow.approve_demand(test_demande, admin_user)
        
        assert approved_demande.status == Demande.Status.APPROVED
        
        # Check line approval
        line = approved_demande.lines.first()
        assert line.quantity_approved == line.quantity_requested
        
        mock_audit.assert_called()
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_approve_demand_partial(self, mock_audit, test_demande, test_article, admin_user):
        """Test partially approving demand."""
        # Add demande line
        line = DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=10
        )
        
        # Partial approval data
        partial_data = [{'line_id': str(line.id), 'quantity_approved': 7}]
        
        approved_demande = AdminWorkflow.approve_partial_demand(
            test_demande, partial_data, admin_user
        )
        
        assert approved_demande.status == Demande.Status.PARTIAL
        
        # Check line approval
        line.refresh_from_db()
        assert line.quantity_approved == 7
        
        mock_audit.assert_called()
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_refuse_demand(self, mock_audit, test_demande, admin_user):
        """Test refusing demand."""
        reason = "Insufficient budget"
        
        refused_demande = AdminWorkflow.refuse_demand(test_demande, reason, admin_user)
        
        assert refused_demande.status == Demande.Status.REFUSED
        mock_audit.assert_called()
    
    @patch('apps.inventory.services.stock_service.StockService.reserve_stock')
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_prepare_demand(self, mock_audit, mock_reserve, approved_demande, test_article, admin_user):
        """Test preparing approved demand."""
        # Add approved line
        DemandeLine.objects.create(
            demande=approved_demande,
            article=test_article,
            quantity_requested=10,
            quantity_approved=8
        )
        
        prepared_demande = AdminWorkflow.prepare_demand(approved_demande, admin_user)
        
        assert prepared_demande.status == Demande.Status.PREPARED
        mock_reserve.assert_called()
        mock_audit.assert_called()
    
    @patch('apps.inventory.services.stock_service.StockService.receive_stock')
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_handover_demand_pin(self, mock_audit, mock_receive, prepared_demande, test_article, admin_user):
        """Test handing over prepared demand with PIN."""
        # Add prepared line
        DemandeLine.objects.create(
            demande=prepared_demande,
            article=test_article,
            quantity_requested=10,
            quantity_approved=8,
            quantity_prepared=8
        )
        
        handover_data = {
            'method': 'PIN',
            'pin': '123456',
            'device_info': 'Test device'
        }
        
        handed_demande = AdminWorkflow.handover_demand(
            prepared_demande, handover_data, admin_user
        )
        
        assert handed_demande.status == Demande.Status.HANDED_OVER
        mock_receive.assert_called()
        mock_audit.assert_called()


class TestStockService:
    """Test StockService business logic."""
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_issue_stock_sufficient(self, mock_audit, technician_stock):
        """Test issuing stock when sufficient quantity available."""
        location = "Workshop A"
        quantity = 10
        
        StockService.issue_stock(
            technician_stock.technician,
            technician_stock.article,
            quantity,
            location
        )
        
        # Check stock reduction
        technician_stock.refresh_from_db()
        assert technician_stock.quantity == 40  # 50 - 10
        
        # Check stock movement creation
        movement = StockMovement.objects.filter(
            technician=technician_stock.technician,
            article=technician_stock.article,
            movement_type=StockMovement.MovementType.ISSUE
        ).first()
        
        assert movement is not None
        assert movement.quantity_delta == -quantity
        assert movement.location_text == location
        
        mock_audit.assert_called()
    
    def test_issue_stock_insufficient(self, technician_stock):
        """Test issuing stock when insufficient quantity available."""
        with pytest.raises(ValidationError, match="Insufficient stock"):
            StockService.issue_stock(
                technician_stock.technician,
                technician_stock.article,
                100,  # More than available (50)
                "Workshop A"
            )
    
    @patch('apps.audit.services.audit_service.AuditService.log_event')
    def test_receive_stock(self, mock_audit, technician_user, test_article):
        """Test receiving stock."""
        quantity = 20
        
        # Create initial stock
        stock = StockTech.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity=30
        )
        
        StockService.receive_stock(
            technician_user.profile,
            test_article,
            quantity,
            demande_id="test-demande-id"
        )
        
        # Check stock increase
        stock.refresh_from_db()
        assert stock.quantity == 50  # 30 + 20
        
        # Check stock movement creation
        movement = StockMovement.objects.filter(
            technician=technician_user.profile,
            article=test_article,
            movement_type=StockMovement.MovementType.RECEIPT
        ).first()
        
        assert movement is not None
        assert movement.quantity_delta == quantity
        assert movement.linked_demande_id == "test-demande-id"
        
        mock_audit.assert_called()
    
    def test_receive_stock_creates_new_record(self, technician_user, test_article):
        """Test receiving stock creates new stock record if none exists."""
        quantity = 15
        
        StockService.receive_stock(
            technician_user.profile,
            test_article,
            quantity
        )
        
        # Check new stock creation
        stock = StockTech.objects.get(
            technician=technician_user.profile,
            article=test_article
        )
        assert stock.quantity == quantity


class TestThresholdService:
    """Test ThresholdService business logic."""
    
    @patch('apps.inventory.services.threshold_service.logger')
    def test_check_and_notify_below_threshold(self, mock_logger, threshold, technician_stock):
        """Test threshold check when stock is below threshold."""
        # Set stock below threshold (10)
        technician_stock.quantity = 5
        technician_stock.save()
        
        ThresholdService.check_and_notify()
        
        # Check that warning was logged
        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args[0][0]
        assert "below threshold" in call_args
    
    @patch('apps.inventory.services.threshold_service.logger')
    def test_check_and_notify_above_threshold(self, mock_logger, threshold, technician_stock):
        """Test threshold check when stock is above threshold."""
        # Stock is already at 50, threshold is 10
        
        ThresholdService.check_and_notify()
        
        # Check that no warning was logged
        mock_logger.warning.assert_not_called()


class TestQRService:
    """Test QRService business logic."""
    
    def test_generate_qr_code(self, test_article):
        """Test QR code generation for article."""
        qr_code = QRService.generate_qr_code(test_article)
        
        assert qr_code.article == test_article
        assert qr_code.payload_url == f"/a/{test_article.reference}"
        assert qr_code.png_file is not None
    
    def test_generate_qr_code_existing_updates(self, test_article):
        """Test that generating QR for existing article updates it."""
        # Create initial QR
        initial_qr = QRService.generate_qr_code(test_article)
        
        # Generate again
        updated_qr = QRService.generate_qr_code(test_article, size=15)
        
        assert initial_qr.id == updated_qr.id
        assert ArticleQR.objects.filter(article=test_article).count() == 1
    
    def test_regenerate_all_qr_codes(self, test_article, test_article_2):
        """Test regenerating all QR codes."""
        count = QRService.regenerate_all_qr_codes()
        
        assert count == 2  # Both test articles
        assert ArticleQR.objects.count() == 2
    
    @patch('apps.inventory.services.qr_service.QRService._create_qr_cell_content')
    def test_create_qr_labels_pdf(self, mock_content, test_article):
        """Test PDF labels creation."""
        mock_content.return_value = "Mock QR Content"
        
        pdf_content = QRService.create_qr_labels_pdf(
            test_article,
            cols=2,
            rows=3,
            count=6
        )
        
        assert isinstance(pdf_content, bytes)
        assert len(pdf_content) > 0
    
    def test_get_qr_print_templates(self):
        """Test getting QR print templates."""
        templates = QRService.get_qr_print_templates()
        
        assert isinstance(templates, list)
        assert len(templates) > 0
        assert all('name' in template for template in templates)
        assert all('layout' in template for template in templates)


class TestAuditService:
    """Test AuditService business logic."""
    
    def test_log_event_creates_event_log(self, admin_user):
        """Test that log_event creates EventLog entry."""
        before_data = {'name': 'Old Name'}
        after_data = {'name': 'New Name'}
        
        event_log = AuditService.log_event(
            actor_user=admin_user,
            entity_type='Article',
            entity_id='test-id',
            action='UPDATE',
            before_data=before_data,
            after_data=after_data
        )
        
        assert event_log.actor_user == admin_user
        assert event_log.entity_type == 'Article'
        assert event_log.entity_id == 'test-id'
        assert event_log.action == 'UPDATE'
        assert event_log.before_data == before_data
        assert event_log.after_data == after_data
        assert event_log.hash_value is not None
    
    def test_log_event_hash_chaining(self, admin_user):
        """Test that event logs are properly chained with hashes."""
        # Create first event
        event1 = AuditService.log_event(
            actor_user=admin_user,
            entity_type='Test',
            entity_id='1',
            action='CREATE',
            after_data={'test': 'data1'}
        )
        
        # Create second event
        event2 = AuditService.log_event(
            actor_user=admin_user,
            entity_type='Test',
            entity_id='2',
            action='CREATE',
            after_data={'test': 'data2'}
        )
        
        # Check that second event references first event's hash
        assert event2.previous_hash == event1.hash_value
        assert event1.hash_value != event2.hash_value
    
    def test_log_event_hash_generation(self, admin_user):
        """Test that hash is properly generated."""
        event = AuditService.log_event(
            actor_user=admin_user,
            entity_type='Test',
            entity_id='test',
            action='CREATE',
            after_data={'test': 'data'}
        )
        
        # Hash should be 64 characters (SHA-256 hex)
        assert len(event.hash_value) == 64
        assert all(c in '0123456789abcdef' for c in event.hash_value)
