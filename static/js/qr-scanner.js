/**
 * QR Scanner functionality using ZXing library
 */

class QRScannerApp {
    constructor() {
        this.codeReader = null;
        this.selectedDeviceId = null;
        this.isScanning = false;
        this.currentStream = null;
        this.devices = [];
        this.currentDeviceIndex = 0;
        this.scannedContent = null;
        
        this.initializeElements();
        this.bindEvents();
        this.requestCameraPermission();
    }
    
    initializeElements() {
        this.video = document.getElementById('video');
        this.loading = document.getElementById('loading');
        this.noCamera = document.getElementById('no-camera');
        this.scanOverlay = document.getElementById('scan-overlay');
        this.scanResult = document.getElementById('scan-result');
        this.scanContent = document.getElementById('scan-content');
        
        // Buttons
        this.startBtn = document.getElementById('start-scan');
        this.stopBtn = document.getElementById('stop-scan');
        this.switchBtn = document.getElementById('switch-camera');
        this.flashBtn = document.getElementById('toggle-flash');
        this.retryBtn = document.getElementById('retry-camera');
        this.scanAgainBtn = document.getElementById('scan-again');
        
        // Action buttons
        this.openArticleBtn = document.getElementById('open-article');
        this.quickAddBtn = document.getElementById('quick-add');
        this.quickUseBtn = document.getElementById('quick-use');
        
        // Manual entry
        this.manualReference = document.getElementById('manual-reference');
        this.manualSubmit = document.getElementById('manual-submit');
        
        // Modals
        this.quickAddModal = document.getElementById('quick-add-modal');
        this.quickUseModal = document.getElementById('quick-use-modal');
    }
    
    bindEvents() {
        this.startBtn.addEventListener('click', () => this.startScanning());
        this.stopBtn.addEventListener('click', () => this.stopScanning());
        this.switchBtn.addEventListener('click', () => this.switchCamera());
        this.flashBtn.addEventListener('click', () => this.toggleFlash());
        this.retryBtn.addEventListener('click', () => this.requestCameraPermission());
        this.scanAgainBtn.addEventListener('click', () => this.resetScan());
        
        // Action buttons
        this.openArticleBtn.addEventListener('click', () => this.openArticle());
        this.quickAddBtn.addEventListener('click', () => this.showQuickAddModal());
        this.quickUseBtn.addEventListener('click', () => this.showQuickUseModal());
        
        // Manual entry
        this.manualSubmit.addEventListener('click', () => this.manualLookup());
        this.manualReference.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.manualLookup();
        });
        
        // Modal events
        this.bindModalEvents();
    }
    
    bindModalEvents() {
        // Quick Add Modal
        document.getElementById('confirm-add').addEventListener('click', () => this.confirmQuickAdd());
        document.getElementById('cancel-add').addEventListener('click', () => this.hideQuickAddModal());
        
        // Quick Use Modal
        document.getElementById('confirm-use').addEventListener('click', () => this.confirmQuickUse());
        document.getElementById('cancel-use').addEventListener('click', () => this.hideQuickUseModal());
        
        // Close modals on outside click
        this.quickAddModal.addEventListener('click', (e) => {
            if (e.target === this.quickAddModal) this.hideQuickAddModal();
        });
        this.quickUseModal.addEventListener('click', (e) => {
            if (e.target === this.quickUseModal) this.hideQuickUseModal();
        });
    }
    
    async requestCameraPermission() {
        try {
            this.loading.classList.remove('hidden');
            this.noCamera.classList.add('hidden');
            
            // Initialize ZXing code reader
            this.codeReader = new ZXing.BrowserQRCodeReader();
            
            // Get video devices
            this.devices = await this.codeReader.listVideoInputDevices();
            
            if (this.devices.length === 0) {
                throw new Error('No camera devices found');
            }
            
            // Enable buttons
            this.startBtn.disabled = false;
            if (this.devices.length > 1) {
                this.switchBtn.disabled = false;
            }
            
            this.selectedDeviceId = this.devices[0].deviceId;
            this.loading.classList.add('hidden');
            
        } catch (error) {
            console.error('Camera permission error:', error);
            this.showNoCameraMessage();
        }
    }
    
    showNoCameraMessage() {
        this.loading.classList.add('hidden');
        this.noCamera.classList.remove('hidden');
        this.startBtn.disabled = true;
        this.switchBtn.disabled = true;
        this.flashBtn.disabled = true;
    }
    
    async startScanning() {
        if (this.isScanning) return;
        
        try {
            this.isScanning = true;
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.scanOverlay.classList.remove('hidden');
            this.resetScanResult();
            
            // Start scanning
            const result = await this.codeReader.decodeOnceFromVideoDevice(
                this.selectedDeviceId,
                this.video
            );
            
            if (result) {
                this.handleScanResult(result.text);
            }
            
        } catch (error) {
            console.error('Scanning error:', error);
            if (error.name !== 'NotFoundException') {
                this.showError('Scanning failed: ' + error.message);
            }
        }
    }
    
    stopScanning() {
        if (!this.isScanning) return;
        
        this.isScanning = false;
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.scanOverlay.classList.add('hidden');
        
        if (this.codeReader) {
            this.codeReader.reset();
        }
    }
    
    switchCamera() {
        if (this.devices.length <= 1) return;
        
        this.currentDeviceIndex = (this.currentDeviceIndex + 1) % this.devices.length;
        this.selectedDeviceId = this.devices[this.currentDeviceIndex].deviceId;
        
        if (this.isScanning) {
            this.stopScanning();
            setTimeout(() => this.startScanning(), 500);
        }
    }
    
    toggleFlash() {
        // Flash control implementation would depend on browser support
        // This is a placeholder for future implementation
        console.log('Flash toggle not implemented yet');
    }
    
    handleScanResult(content) {
        this.scannedContent = content;
        this.scanContent.textContent = content;
        this.scanResult.classList.remove('hidden');
        this.stopScanning();
        
        // Parse content and show appropriate actions
        this.parseScannedContent(content);
    }
    
    parseScannedContent(content) {
        // Hide all action buttons first
        this.openArticleBtn.classList.add('hidden');
        this.quickAddBtn.classList.add('hidden');
        this.quickUseBtn.classList.add('hidden');
        
        // Check if it's an article reference URL
        const articleMatch = content.match(/\/a\/([^\/\?]+)/);
        if (articleMatch) {
            this.articleReference = articleMatch[1];
            this.openArticleBtn.classList.remove('hidden');
            
            // Show quick actions only for technicians
            if (this.isTechnician()) {
                this.quickAddBtn.classList.remove('hidden');
                this.quickUseBtn.classList.remove('hidden');
            }
        }
    }
    
    isTechnician() {
        // Check if current user is a technician
        return document.body.dataset.userRole === 'TECH';
    }
    
    openArticle() {
        if (this.articleReference) {
            window.location.href = `/a/${this.articleReference}/`;
        }
    }
    
    showQuickAddModal() {
        this.quickAddModal.classList.remove('hidden');
        document.getElementById('add-quantity').focus();
    }
    
    hideQuickAddModal() {
        this.quickAddModal.classList.add('hidden');
    }
    
    showQuickUseModal() {
        this.quickUseModal.classList.remove('hidden');
        document.getElementById('use-quantity').focus();
    }
    
    hideQuickUseModal() {
        this.quickUseModal.classList.add('hidden');
    }
    
    async confirmQuickAdd() {
        const quantity = parseFloat(document.getElementById('add-quantity').value);
        const notes = document.getElementById('add-notes').value;
        
        if (!quantity || quantity <= 0) {
            this.showError('Please enter a valid quantity');
            return;
        }
        
        try {
            const response = await fetch('/api/quick-add-to-cart/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    article_reference: this.articleReference,
                    quantity: quantity,
                    notes: notes
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
                this.hideQuickAddModal();
                this.resetScan();
            } else {
                this.showError(data.error);
            }
            
        } catch (error) {
            console.error('Quick add error:', error);
            this.showError('Failed to add to cart');
        }
    }
    
    async confirmQuickUse() {
        const quantity = parseFloat(document.getElementById('use-quantity').value);
        const location = document.getElementById('use-location').value;
        const notes = document.getElementById('use-notes').value;
        
        if (!quantity || quantity <= 0) {
            this.showError('Please enter a valid quantity');
            return;
        }
        
        if (!location.trim()) {
            this.showError('Please enter a location');
            return;
        }
        
        try {
            const response = await fetch('/api/quick-declare-usage/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    article_reference: this.articleReference,
                    quantity: quantity,
                    location: location,
                    notes: notes
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
                this.hideQuickUseModal();
                this.resetScan();
            } else {
                this.showError(data.error);
            }
            
        } catch (error) {
            console.error('Quick use error:', error);
            this.showError('Failed to declare usage');
        }
    }
    
    manualLookup() {
        const reference = this.manualReference.value.trim();
        if (reference) {
            window.location.href = `/a/${reference}/`;
        }
    }
    
    resetScan() {
        this.scanResult.classList.add('hidden');
        this.scannedContent = null;
        this.articleReference = null;
        
        // Clear modal inputs
        document.getElementById('add-quantity').value = '1';
        document.getElementById('add-notes').value = '';
        document.getElementById('use-quantity').value = '1';
        document.getElementById('use-location').value = '';
        document.getElementById('use-notes').value = '';
    }
    
    resetScanResult() {
        this.scanResult.classList.add('hidden');
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }
    
    showSuccess(message) {
        this.showToast(message, 'success');
    }
    
    showError(message) {
        this.showToast(message, 'error');
    }
    
    showToast(message, type) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-500' : 'bg-red-500'
        } text-white`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Initialize QR Scanner when page loads
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('video')) {
        new QRScannerApp();
    }
});
