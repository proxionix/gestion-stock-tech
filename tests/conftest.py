"""
Pytest configuration and fixtures for Stock Management System tests.
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from apps.users.models import Profile
from apps.inventory.models import Article, StockTech, Threshold
from apps.orders.models import Panier, Demande
from apps.audit.models import EventLog

User = get_user_model()


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Setup test database with initial data."""
    with django_db_blocker.unblock():
        # Create initial test data
        call_command('loaddata', 'test_fixtures.json', verbosity=0)


@pytest.fixture
def api_client():
    """API client for testing."""
    return Client()


@pytest.fixture
def admin_user(db):
    """Create admin user for testing."""
    user = User.objects.create_user(
        username='admin_test',
        email='admin@test.com',
        password='test_admin_123'
    )
    Profile.objects.create(
        user=user,
        role=Profile.Role.ADMIN,
        language_pref='en'
    )
    return user


@pytest.fixture
def technician_user(db):
    """Create technician user for testing."""
    user = User.objects.create_user(
        username='tech_test',
        email='tech@test.com',
        password='test_tech_123'
    )
    Profile.objects.create(
        user=user,
        role=Profile.Role.TECH,
        language_pref='en'
    )
    return user


@pytest.fixture
def second_technician_user(db):
    """Create second technician user for testing."""
    user = User.objects.create_user(
        username='tech2_test',
        email='tech2@test.com',
        password='test_tech2_123'
    )
    Profile.objects.create(
        user=user,
        role=Profile.Role.TECH,
        language_pref='fr'
    )
    return user


@pytest.fixture
def test_article(db):
    """Create test article."""
    return Article.objects.create(
        reference='TEST001',
        name='Test Article',
        description='Test article for unit tests',
        unit='PCS',
        is_active=True
    )


@pytest.fixture
def test_article_2(db):
    """Create second test article."""
    return Article.objects.create(
        reference='TEST002',
        name='Test Article 2',
        description='Second test article for unit tests',
        unit='KG',
        is_active=True
    )


@pytest.fixture
def inactive_article(db):
    """Create inactive test article."""
    return Article.objects.create(
        reference='INACTIVE001',
        name='Inactive Article',
        description='Inactive article for testing',
        unit='PCS',
        is_active=False
    )


@pytest.fixture
def technician_stock(db, technician_user, test_article):
    """Create technician stock for testing."""
    return StockTech.objects.create(
        technician=technician_user.profile,
        article=test_article,
        quantity=50
    )


@pytest.fixture
def technician_stock_2(db, technician_user, test_article_2):
    """Create second technician stock for testing."""
    return StockTech.objects.create(
        technician=technician_user.profile,
        article=test_article_2,
        quantity=25
    )


@pytest.fixture
def threshold(db, technician_user, test_article):
    """Create threshold for testing."""
    return Threshold.objects.create(
        technician=technician_user.profile,
        article=test_article,
        min_quantity=10
    )


@pytest.fixture
def draft_panier(db, technician_user):
    """Create draft panier for testing."""
    return Panier.objects.create(
        technician=technician_user.profile,
        status=Panier.Status.DRAFT
    )


@pytest.fixture
def submitted_panier(db, technician_user):
    """Create submitted panier for testing."""
    return Panier.objects.create(
        technician=technician_user.profile,
        status=Panier.Status.SUBMITTED
    )


@pytest.fixture
def test_demande(db, technician_user):
    """Create test demande."""
    return Demande.objects.create(
        technician=technician_user.profile,
        status=Demande.Status.SUBMITTED
    )


@pytest.fixture
def approved_demande(db, technician_user):
    """Create approved demande."""
    return Demande.objects.create(
        technician=technician_user.profile,
        status=Demande.Status.APPROVED
    )


@pytest.fixture
def prepared_demande(db, technician_user):
    """Create prepared demande."""
    return Demande.objects.create(
        technician=technician_user.profile,
        status=Demande.Status.PREPARED
    )


@pytest.fixture
def authenticated_admin_client(api_client, admin_user):
    """API client authenticated as admin."""
    api_client.force_login(admin_user)
    return api_client


@pytest.fixture
def authenticated_tech_client(api_client, technician_user):
    """API client authenticated as technician."""
    api_client.force_login(technician_user)
    return api_client


@pytest.fixture
def jwt_admin_client(api_client, admin_user):
    """API client with JWT token for admin."""
    from rest_framework_simplejwt.tokens import RefreshToken
    
    refresh = RefreshToken.for_user(admin_user)
    api_client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
    return api_client


@pytest.fixture
def jwt_tech_client(api_client, technician_user):
    """API client with JWT token for technician."""
    from rest_framework_simplejwt.tokens import RefreshToken
    
    refresh = RefreshToken.for_user(technician_user)
    api_client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
    return api_client


@pytest.fixture
def mock_redis():
    """Mock Redis for testing."""
    import fakeredis
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def mock_celery(monkeypatch):
    """Mock Celery for testing."""
    def mock_delay(*args, **kwargs):
        return None
    
    def mock_apply_async(*args, **kwargs):
        return None
    
    monkeypatch.setattr('celery.Task.delay', mock_delay)
    monkeypatch.setattr('celery.Task.apply_async', mock_apply_async)


@pytest.fixture
def event_log_sample(db, admin_user):
    """Create sample event log."""
    return EventLog.objects.create(
        actor_user=admin_user,
        entity_type='Article',
        entity_id='test-id',
        action='CREATE',
        before_data=None,
        after_data={'name': 'Test Article'},
        hash_value='sample_hash'
    )


@pytest.fixture
def security_test_ip():
    """IP address for security testing."""
    return '192.168.1.100'


@pytest.fixture
def test_files():
    """Test files for upload testing."""
    import tempfile
    import os
    from PIL import Image
    
    # Create temporary test files
    temp_dir = tempfile.mkdtemp()
    
    # Test image
    img = Image.new('RGB', (100, 100), color='red')
    img_path = os.path.join(temp_dir, 'test_image.png')
    img.save(img_path)
    
    # Test PDF (mock)
    pdf_path = os.path.join(temp_dir, 'test_document.pdf')
    with open(pdf_path, 'wb') as f:
        f.write(b'%PDF-1.4 mock pdf content')
    
    return {
        'image': img_path,
        'pdf': pdf_path,
        'temp_dir': temp_dir
    }


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    This is needed for Django testing.
    """
    pass


@pytest.fixture
def settings_override(settings):
    """Override settings for testing."""
    settings.CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    return settings
