"""
Integration tests for Stock Management System API.
"""
import pytest
import json
from django.urls import reverse
from rest_framework import status
from apps.orders.models import Panier, PanierLine, Demande, DemandeLine
from apps.inventory.models import StockTech, Article
from apps.audit.models import StockMovement


class TestAuthenticationAPI:
    """Test authentication API endpoints."""
    
    def test_login_success(self, api_client, technician_user):
        """Test successful login."""
        url = reverse('api:login')
        data = {
            'username': 'tech_test',
            'password': 'test_tech_123'
        }
        
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials."""
        url = reverse('api:login')
        data = {
            'username': 'invalid',
            'password': 'invalid'
        }
        
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_me_endpoint_authenticated(self, jwt_tech_client, technician_user):
        """Test /me endpoint with authenticated user."""
        url = reverse('api:me')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'tech_test'
        assert response.data['profile']['role'] == 'TECH'
    
    def test_me_endpoint_unauthenticated(self, api_client):
        """Test /me endpoint without authentication."""
        url = reverse('api:me')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestInventoryAPI:
    """Test inventory API endpoints."""
    
    def test_articles_list_technician(self, jwt_tech_client, test_article, inactive_article):
        """Test articles list for technician (only active articles)."""
        url = reverse('api:article_list')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['reference'] == 'TEST001'
    
    def test_articles_list_admin(self, jwt_admin_client, test_article, inactive_article):
        """Test articles list for admin (all articles)."""
        url = reverse('api:article_list')
        
        response = jwt_admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
    
    def test_articles_search(self, jwt_tech_client, test_article, test_article_2):
        """Test articles search functionality."""
        url = reverse('api:article_list')
        
        response = jwt_tech_client.get(url, {'search': 'TEST001'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['reference'] == 'TEST001'
    
    def test_create_article_admin(self, jwt_admin_client):
        """Test creating article as admin."""
        url = reverse('api:article_list')
        data = {
            'reference': 'NEW001',
            'name': 'New Article',
            'description': 'New test article',
            'unit': 'PCS'
        }
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['reference'] == 'NEW001'
        
        # Check article was created
        assert Article.objects.filter(reference='NEW001').exists()
    
    def test_create_article_technician_forbidden(self, jwt_tech_client):
        """Test creating article as technician is forbidden."""
        url = reverse('api:article_list')
        data = {
            'reference': 'FORBIDDEN001',
            'name': 'Forbidden Article',
            'unit': 'PCS'
        }
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_my_stock(self, jwt_tech_client, technician_stock, technician_stock_2):
        """Test getting technician's own stock."""
        url = reverse('api:my_stock')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        
        # Check stock data
        references = [item['article']['reference'] for item in response.data]
        assert 'TEST001' in references
        assert 'TEST002' in references
    
    def test_technician_stock_admin(self, jwt_admin_client, technician_user, technician_stock):
        """Test admin viewing specific technician's stock."""
        url = reverse('api:technician_stock', kwargs={'technician_id': technician_user.profile.id})
        
        response = jwt_admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['article']['reference'] == 'TEST001'
    
    def test_technician_stock_unauthorized(self, jwt_tech_client, second_technician_user):
        """Test technician cannot view other technician's stock."""
        url = reverse('api:technician_stock', kwargs={'technician_id': second_technician_user.profile.id})
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_issue_stock(self, jwt_tech_client, technician_stock):
        """Test issuing stock (usage declaration)."""
        url = reverse('api:issue_stock')
        data = {
            'article_id': str(technician_stock.article.id),
            'quantity': 10,
            'location_text': 'Workshop A'
        }
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check stock was reduced
        technician_stock.refresh_from_db()
        assert technician_stock.quantity == 40  # 50 - 10
        
        # Check stock movement was created
        assert StockMovement.objects.filter(
            technician=technician_stock.technician,
            article=technician_stock.article,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity_delta=-10
        ).exists()


class TestCartAPI:
    """Test cart (panier) API endpoints."""
    
    def test_get_cart_empty(self, jwt_tech_client):
        """Test getting empty cart."""
        url = reverse('api:my_cart')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'DRAFT'
        assert len(response.data['lines']) == 0
    
    def test_get_cart_with_items(self, jwt_tech_client, draft_panier, test_article):
        """Test getting cart with items."""
        # Add line to cart
        PanierLine.objects.create(
            panier=draft_panier,
            article=test_article,
            quantity=5
        )
        
        url = reverse('api:my_cart')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['lines']) == 1
        assert response.data['lines'][0]['quantity'] == 5
        assert response.data['lines'][0]['article']['reference'] == 'TEST001'
    
    def test_add_to_cart(self, jwt_tech_client, technician_user, test_article):
        """Test adding item to cart."""
        url = reverse('api:my_cart')
        data = {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 3
        }
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check cart was created and item added
        panier = Panier.objects.get(technician=technician_user.profile, status=Panier.Status.DRAFT)
        assert panier.lines.count() == 1
        assert panier.lines.first().quantity == 3
    
    def test_add_to_cart_existing_item(self, jwt_tech_client, draft_panier, test_article):
        """Test adding existing item to cart (should increase quantity)."""
        # Add initial line
        PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=2)
        
        url = reverse('api:my_cart')
        data = {
            'action': 'add',
            'article_id': str(test_article.id),
            'quantity': 3
        }
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check quantity was increased
        line = PanierLine.objects.get(panier=draft_panier, article=test_article)
        assert line.quantity == 5  # 2 + 3
    
    def test_update_cart_line(self, jwt_tech_client, draft_panier, test_article):
        """Test updating cart line quantity."""
        line = PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=5)
        
        url = reverse('api:my_cart')
        data = {
            'action': 'update',
            'line_id': str(line.id),
            'quantity': 8
        }
        
        response = jwt_tech_client.patch(url, data, content_type='application/json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check quantity was updated
        line.refresh_from_db()
        assert line.quantity == 8
    
    def test_remove_cart_line(self, jwt_tech_client, draft_panier, test_article):
        """Test removing cart line (set quantity to 0)."""
        line = PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=5)
        
        url = reverse('api:my_cart')
        data = {
            'action': 'update',
            'line_id': str(line.id),
            'quantity': 0
        }
        
        response = jwt_tech_client.patch(url, data, content_type='application/json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check line was removed
        assert not PanierLine.objects.filter(id=line.id).exists()
    
    def test_submit_cart(self, jwt_tech_client, draft_panier, test_article):
        """Test submitting cart creates demande."""
        # Add line to cart
        PanierLine.objects.create(panier=draft_panier, article=test_article, quantity=5)
        
        url = reverse('api:my_cart')
        data = {'action': 'submit'}
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check panier was submitted
        draft_panier.refresh_from_db()
        assert draft_panier.status == Panier.Status.SUBMITTED
        
        # Check demande was created
        demande = Demande.objects.get(technician=draft_panier.technician)
        assert demande.status == Demande.Status.SUBMITTED
        assert demande.lines.count() == 1
    
    def test_submit_empty_cart_fails(self, jwt_tech_client, draft_panier):
        """Test submitting empty cart fails."""
        url = reverse('api:my_cart')
        data = {'action': 'submit'}
        
        response = jwt_tech_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDemandesAPI:
    """Test demandes (requests) API endpoints."""
    
    def test_demandes_list_admin(self, jwt_admin_client, test_demande):
        """Test admin can see all demandes."""
        url = reverse('api:demande-list')
        
        response = jwt_admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(test_demande.id)
    
    def test_demandes_list_technician_own_only(self, jwt_tech_client, test_demande, second_technician_user):
        """Test technician can only see own demandes."""
        # Create demande for another technician
        Demande.objects.create(
            technician=second_technician_user.profile,
            status=Demande.Status.SUBMITTED
        )
        
        url = reverse('api:demande-list')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(test_demande.id)
    
    def test_demandes_filter_by_status(self, jwt_admin_client, test_demande, approved_demande):
        """Test filtering demandes by status."""
        url = reverse('api:demande-list')
        
        response = jwt_admin_client.get(url, {'status': 'APPROVED'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(approved_demande.id)
    
    def test_approve_demande_admin(self, jwt_admin_client, test_demande, test_article):
        """Test admin can approve demande."""
        # Add line to demande
        DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=10
        )
        
        url = reverse('api:approve_demande', kwargs={'demande_id': test_demande.id})
        
        response = jwt_admin_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check demande was approved
        test_demande.refresh_from_db()
        assert test_demande.status == Demande.Status.APPROVED
        
        # Check line was approved
        line = test_demande.lines.first()
        assert line.quantity_approved == line.quantity_requested
    
    def test_approve_demande_technician_forbidden(self, jwt_tech_client, test_demande):
        """Test technician cannot approve demande."""
        url = reverse('api:approve_demande', kwargs={'demande_id': test_demande.id})
        
        response = jwt_tech_client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_approve_partial_demande(self, jwt_admin_client, test_demande, test_article):
        """Test partial approval of demande."""
        # Add line to demande
        line = DemandeLine.objects.create(
            demande=test_demande,
            article=test_article,
            quantity_requested=10
        )
        
        url = reverse('api:approve_partial_demande', kwargs={'demande_id': test_demande.id})
        data = {
            'approvals': [
                {
                    'line_id': str(line.id),
                    'quantity_approved': 7
                }
            ]
        }
        
        response = jwt_admin_client.post(url, data, content_type='application/json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check demande was partially approved
        test_demande.refresh_from_db()
        assert test_demande.status == Demande.Status.PARTIAL
        
        # Check line was partially approved
        line.refresh_from_db()
        assert line.quantity_approved == 7
    
    def test_refuse_demande(self, jwt_admin_client, test_demande):
        """Test refusing demande."""
        url = reverse('api:refuse_demande', kwargs={'demande_id': test_demande.id})
        data = {'reason': 'Insufficient budget'}
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check demande was refused
        test_demande.refresh_from_db()
        assert test_demande.status == Demande.Status.REFUSED
    
    def test_prepare_demande(self, jwt_admin_client, approved_demande, test_article):
        """Test preparing approved demande."""
        # Add approved line
        DemandeLine.objects.create(
            demande=approved_demande,
            article=test_article,
            quantity_requested=10,
            quantity_approved=8
        )
        
        url = reverse('api:prepare_demande', kwargs={'demande_id': approved_demande.id})
        
        response = jwt_admin_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check demande was prepared
        approved_demande.refresh_from_db()
        assert approved_demande.status == Demande.Status.PREPARED
    
    def test_handover_demande_pin(self, jwt_admin_client, prepared_demande, test_article):
        """Test handing over demande with PIN."""
        # Add prepared line
        DemandeLine.objects.create(
            demande=prepared_demande,
            article=test_article,
            quantity_requested=10,
            quantity_approved=8,
            quantity_prepared=8
        )
        
        url = reverse('api:handover_demande', kwargs={'demande_id': prepared_demande.id})
        data = {
            'method': 'PIN',
            'pin': '123456',
            'device_info': 'Test device'
        }
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check demande was handed over
        prepared_demande.refresh_from_db()
        assert prepared_demande.status == Demande.Status.HANDED_OVER


class TestQRCodeAPI:
    """Test QR code API endpoints."""
    
    def test_get_article_qr(self, jwt_tech_client, test_article):
        """Test getting article QR code."""
        url = reverse('api:get_article_qr', kwargs={'article_id': test_article.id})
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['article_reference'] == test_article.reference
        assert response.data['qr_payload_url'] == f"/a/{test_article.reference}"
    
    def test_regenerate_article_qr_admin(self, jwt_admin_client, test_article):
        """Test regenerating article QR code as admin."""
        url = reverse('api:regenerate_article_qr', kwargs={'article_id': test_article.id})
        data = {'size': 15, 'border': 2}
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'regenerated successfully' in response.data['message']
    
    def test_print_qr_sheet(self, jwt_admin_client, test_article):
        """Test printing QR code sheet."""
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
        assert 'attachment' in response['Content-Disposition']
    
    def test_print_multiple_qr_sheet(self, jwt_admin_client, test_article, test_article_2):
        """Test printing multiple articles QR sheet."""
        url = reverse('api:print_multiple_qr_sheet')
        data = {
            'article_ids': [str(test_article.id), str(test_article_2.id)],
            'layout': {
                'cols': 2,
                'rows': 4,
                'include_text': True
            }
        }
        
        response = jwt_admin_client.post(url, data, content_type='application/json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'


class TestSecurityAPI:
    """Test security API endpoints."""
    
    def test_security_dashboard_admin(self, jwt_admin_client):
        """Test security dashboard for admin."""
        url = reverse('api:security_dashboard')
        
        response = jwt_admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'security_status' in response.data
        assert 'blocked_ips' in response.data
        assert 'recent_events' in response.data
    
    def test_security_dashboard_technician_forbidden(self, jwt_tech_client):
        """Test security dashboard forbidden for technician."""
        url = reverse('api:security_dashboard')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_block_ip_admin(self, jwt_admin_client):
        """Test blocking IP as admin."""
        url = reverse('api:block_ip')
        data = {
            'ip_address': '192.168.1.100',
            'duration': 3600,
            'reason': 'Suspicious activity'
        }
        
        response = jwt_admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'has been blocked' in response.data['message']
    
    def test_security_test(self, jwt_admin_client):
        """Test security configuration test."""
        url = reverse('api:security_test')
        
        response = jwt_admin_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'overall_score' in response.data
        assert 'test_results' in response.data
