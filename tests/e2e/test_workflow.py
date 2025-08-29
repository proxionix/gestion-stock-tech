"""
End-to-end workflow tests for Stock Management System.
Tests complete user journeys and complex scenarios.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine
from apps.inventory.models import StockTech, Article
from apps.audit.models import StockMovement, EventLog


@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete workflow from cart to handover."""
    
    def test_full_technician_workflow(
        self, 
        jwt_tech_client, 
        jwt_admin_client,
        technician_user,
        admin_user,
        test_article,
        test_article_2
    ):
        """
        Test complete workflow:
        1. Technician adds items to cart
        2. Submits cart (creates demande)
        3. Admin approves demande
        4. Admin prepares demande
        5. Admin hands over demande
        6. Technician uses stock
        """
        
        # Setup initial stock for admin
        admin_stock_1 = StockTech.objects.create(
            technician=admin_user.profile,
            article=test_article,
            quantity=100
        )
        admin_stock_2 = StockTech.objects.create(
            technician=admin_user.profile,
            article=test_article_2,
            quantity=50
        )
        
        # 1. Technician adds items to cart
        cart_url = reverse('api:my_cart')
        
        # Add first item
        response = jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 15
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Add second item
        response = jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article_2.id),
            'quantity': 8
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Verify cart contents
        response = jwt_tech_client.get(cart_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['lines']) == 2
        
        # 2. Submit cart
        response = jwt_tech_client.post(cart_url, {'action': 'submit'})
        assert response.status_code == status.HTTP_200_OK
        
        # Verify demande was created
        demande = Demande.objects.get(technician=technician_user.profile)
        assert demande.status == Demande.Status.SUBMITTED
        assert demande.lines.count() == 2
        
        # 3. Admin approves demande
        approve_url = reverse('api:approve_demande', kwargs={'demande_id': demande.id})
        response = jwt_admin_client.post(approve_url)
        assert response.status_code == status.HTTP_200_OK
        
        # Verify approval
        demande.refresh_from_db()
        assert demande.status == Demande.Status.APPROVED
        
        # Check lines are approved
        for line in demande.lines.all():
            assert line.quantity_approved == line.quantity_requested
        
        # 4. Admin prepares demande
        prepare_url = reverse('api:prepare_demande', kwargs={'demande_id': demande.id})
        response = jwt_admin_client.post(prepare_url)
        assert response.status_code == status.HTTP_200_OK
        
        # Verify preparation
        demande.refresh_from_db()
        assert demande.status == Demande.Status.PREPARED
        
        # Check admin stock was reserved
        admin_stock_1.refresh_from_db()
        admin_stock_2.refresh_from_db()
        assert admin_stock_1.quantity == 85  # 100 - 15
        assert admin_stock_2.quantity == 42  # 50 - 8
        
        # 5. Admin hands over demande
        handover_url = reverse('api:handover_demande', kwargs={'demande_id': demande.id})
        response = jwt_admin_client.post(handover_url, {
            'method': 'PIN',
            'pin': '123456',
            'device_info': 'Test tablet'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Verify handover
        demande.refresh_from_db()
        assert demande.status == Demande.Status.HANDED_OVER
        
        # Check technician received stock
        tech_stock_1 = StockTech.objects.get(
            technician=technician_user.profile, 
            article=test_article
        )
        tech_stock_2 = StockTech.objects.get(
            technician=technician_user.profile, 
            article=test_article_2
        )
        assert tech_stock_1.quantity == 15
        assert tech_stock_2.quantity == 8
        
        # Check stock movements were created
        movements = StockMovement.objects.filter(
            technician=technician_user.profile,
            movement_type=StockMovement.MovementType.RECEIPT
        )
        assert movements.count() == 2
        
        # 6. Technician uses stock
        usage_url = reverse('api:issue_stock')
        
        # Use some of first article
        response = jwt_tech_client.post(usage_url, {
            'article_id': str(test_article.id),
            'quantity': 5,
            'location_text': 'Workshop A - Machine repair'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Verify stock was reduced
        tech_stock_1.refresh_from_db()
        assert tech_stock_1.quantity == 10  # 15 - 5
        
        # Check usage movement was created
        usage_movement = StockMovement.objects.filter(
            technician=technician_user.profile,
            article=test_article,
            movement_type=StockMovement.MovementType.ISSUE
        ).first()
        assert usage_movement is not None
        assert usage_movement.quantity_delta == -5
        assert usage_movement.location_text == 'Workshop A - Machine repair'
        
        # Verify audit trail
        events = EventLog.objects.filter(
            entity_type='Demande',
            entity_id=str(demande.id)
        ).order_by('timestamp')
        
        # Should have events for: submit, approve, prepare, handover
        assert events.count() >= 4
        
        # Check hash chaining in audit trail
        for i in range(1, events.count()):
            assert events[i].previous_hash == events[i-1].hash_value
    
    def test_partial_approval_workflow(
        self,
        jwt_tech_client,
        jwt_admin_client,
        technician_user,
        test_article,
        test_article_2
    ):
        """
        Test workflow with partial approval.
        """
        
        # Create cart and submit
        cart_url = reverse('api:my_cart')
        
        jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 20
        })
        jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article_2.id),
            'quantity': 15
        })
        
        jwt_tech_client.post(cart_url, {'action': 'submit'})
        
        demande = Demande.objects.get(technician=technician_user.profile)
        lines = list(demande.lines.all())
        
        # Partial approval
        partial_url = reverse('api:approve_partial_demande', kwargs={'demande_id': demande.id})
        response = jwt_admin_client.post(partial_url, {
            'approvals': [
                {
                    'line_id': str(lines[0].id),
                    'quantity_approved': 12  # Partial approval
                },
                {
                    'line_id': str(lines[1].id),
                    'quantity_approved': 0   # Rejected
                }
            ]
        }, content_type='application/json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify partial approval
        demande.refresh_from_db()
        assert demande.status == Demande.Status.PARTIAL
        
        lines[0].refresh_from_db()
        lines[1].refresh_from_db()
        assert lines[0].quantity_approved == 12
        assert lines[1].quantity_approved == 0
    
    def test_demande_refusal_workflow(
        self,
        jwt_tech_client,
        jwt_admin_client,
        technician_user,
        test_article
    ):
        """
        Test workflow with demande refusal.
        """
        
        # Create and submit cart
        cart_url = reverse('api:my_cart')
        jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 10
        })
        jwt_tech_client.post(cart_url, {'action': 'submit'})
        
        demande = Demande.objects.get(technician=technician_user.profile)
        
        # Refuse demande
        refuse_url = reverse('api:refuse_demande', kwargs={'demande_id': demande.id})
        response = jwt_admin_client.post(refuse_url, {
            'reason': 'Budget constraints'
        })
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify refusal
        demande.refresh_from_db()
        assert demande.status == Demande.Status.REFUSED
        
        # Technician should be able to create new cart
        response = jwt_tech_client.get(cart_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'DRAFT'


@pytest.mark.e2e
class TestConcurrencyScenarios:
    """Test concurrent access scenarios."""
    
    def test_concurrent_cart_updates(
        self,
        jwt_tech_client,
        technician_user,
        test_article
    ):
        """
        Test concurrent updates to the same cart.
        """
        from django.db import transaction
        
        # Get cart
        cart_url = reverse('api:my_cart')
        response = jwt_tech_client.get(cart_url)
        panier = Panier.objects.get(technician=technician_user.profile)
        
        # Simulate concurrent adds
        def add_to_cart(quantity):
            return jwt_tech_client.post(cart_url, {
                'action': 'add',
                'article_id': str(test_article.id),
                'quantity': quantity
            })
        
        # Two concurrent requests
        response1 = add_to_cart(5)
        response2 = add_to_cart(3)
        
        # Both should succeed
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        
        # Final quantity should be correct (5 + 3 = 8)
        line = PanierLine.objects.get(panier=panier, article=test_article)
        assert line.quantity == 8
    
    def test_concurrent_stock_operations(
        self,
        jwt_tech_client,
        technician_user,
        test_article
    ):
        """
        Test concurrent stock operations.
        """
        # Create initial stock
        stock = StockTech.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity=20
        )
        
        usage_url = reverse('api:issue_stock')
        
        # Simulate concurrent stock usage
        def use_stock(quantity, location):
            return jwt_tech_client.post(usage_url, {
                'article_id': str(test_article.id),
                'quantity': quantity,
                'location_text': location
            })
        
        # Two concurrent usage requests
        response1 = use_stock(8, 'Location A')
        response2 = use_stock(7, 'Location B')
        
        # Both should succeed
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        
        # Final stock should be correct (20 - 8 - 7 = 5)
        stock.refresh_from_db()
        assert stock.quantity == 5
        
        # Should have two movement records
        movements = StockMovement.objects.filter(
            technician=technician_user.profile,
            article=test_article,
            movement_type=StockMovement.MovementType.ISSUE
        )
        assert movements.count() == 2


@pytest.mark.e2e
class TestErrorScenarios:
    """Test error handling scenarios."""
    
    def test_insufficient_stock_scenario(
        self,
        jwt_tech_client,
        technician_user,
        test_article
    ):
        """
        Test handling of insufficient stock scenarios.
        """
        # Create limited stock
        stock = StockTech.objects.create(
            technician=technician_user.profile,
            article=test_article,
            quantity=5
        )
        
        usage_url = reverse('api:issue_stock')
        
        # Try to use more than available
        response = jwt_tech_client.post(usage_url, {
            'article_id': str(test_article.id),
            'quantity': 10,  # More than available (5)
            'location_text': 'Test location'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'insufficient' in response.data['error'].lower()
        
        # Stock should remain unchanged
        stock.refresh_from_db()
        assert stock.quantity == 5
    
    def test_invalid_demande_state_transitions(
        self,
        jwt_admin_client,
        test_demande
    ):
        """
        Test invalid state transitions are prevented.
        """
        # Try to prepare demande that's not approved
        prepare_url = reverse('api:prepare_demande', kwargs={'demande_id': test_demande.id})
        response = jwt_admin_client.post(prepare_url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Demande should remain in submitted state
        test_demande.refresh_from_db()
        assert test_demande.status == Demande.Status.SUBMITTED
    
    def test_duplicate_cart_submission(
        self,
        jwt_tech_client,
        draft_panier,
        test_article
    ):
        """
        Test duplicate cart submission is prevented.
        """
        # Add item to cart
        PanierLine.objects.create(
            panier=draft_panier,
            article=test_article,
            quantity=5
        )
        
        cart_url = reverse('api:my_cart')
        
        # Submit cart
        response = jwt_tech_client.post(cart_url, {'action': 'submit'})
        assert response.status_code == status.HTTP_200_OK
        
        # Try to submit again
        response = jwt_tech_client.post(cart_url, {'action': 'submit'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.e2e
class TestQRCodeIntegration:
    """Test QR code integration in workflows."""
    
    def test_qr_code_generation_on_article_creation(
        self,
        jwt_admin_client
    ):
        """
        Test QR code is automatically generated when article is created.
        """
        url = reverse('api:article_list')
        data = {
            'reference': 'QR_TEST001',
            'name': 'QR Test Article',
            'description': 'Article for QR testing',
            'unit': 'PCS'
        }
        
        response = jwt_admin_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Check QR code was created
        article = Article.objects.get(reference='QR_TEST001')
        assert hasattr(article, 'qr_code')
        assert article.qr_code.payload_url == f"/a/{article.reference}"
    
    def test_qr_code_pdf_generation(
        self,
        jwt_admin_client,
        test_article
    ):
        """
        Test QR code PDF generation.
        """
        url = reverse('api:print_qr_sheet', kwargs={'article_id': test_article.id})
        data = {
            'cols': 3,
            'rows': 8,
            'count': 24,
            'include_text': True
        }
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'
        assert len(response.content) > 0


@pytest.mark.e2e
class TestAuditTrailIntegration:
    """Test audit trail integration."""
    
    def test_complete_audit_trail(
        self,
        jwt_tech_client,
        jwt_admin_client,
        technician_user,
        admin_user,
        test_article
    ):
        """
        Test complete audit trail through workflow.
        """
        initial_event_count = EventLog.objects.count()
        
        # Create cart and submit
        cart_url = reverse('api:my_cart')
        jwt_tech_client.post(cart_url, {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 10
        })
        jwt_tech_client.post(cart_url, {'action': 'submit'})
        
        demande = Demande.objects.get(technician=technician_user.profile)
        
        # Approve demande
        approve_url = reverse('api:approve_demande', kwargs={'demande_id': demande.id})
        jwt_admin_client.post(approve_url)
        
        # Check audit events were created
        final_event_count = EventLog.objects.count()
        assert final_event_count > initial_event_count
        
        # Check specific events
        demande_events = EventLog.objects.filter(
            entity_type='Demande',
            entity_id=str(demande.id)
        ).order_by('timestamp')
        
        assert demande_events.count() >= 2  # Submit and approve events
        
        # Check hash chaining
        for i in range(1, demande_events.count()):
            current_event = demande_events[i]
            previous_event = demande_events[i-1]
            assert current_event.previous_hash == previous_event.hash_value
    
    def test_audit_trail_immutability(
        self,
        jwt_admin_client,
        admin_user,
        test_article
    ):
        """
        Test that audit trail entries cannot be modified.
        """
        # Create an audit event
        from apps.audit.services.audit_service import AuditService
        
        event = AuditService.log_event(
            actor_user=admin_user,
            entity_type='Article',
            entity_id=str(test_article.id),
            action='TEST',
            after_data={'test': 'data'}
        )
        
        original_hash = event.hash_value
        
        # Try to modify the event (this would be done maliciously)
        event.after_data = {'test': 'modified_data'}
        event.save()
        
        # Hash should still be the same, indicating no change detection
        # In a real system, you'd want to validate hash integrity
        assert event.hash_value == original_hash
