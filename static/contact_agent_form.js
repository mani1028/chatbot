/**
 * Contact Agent Form Handler
 * Manages the display and submission of contact request forms
 */

class ContactAgentForm {
  constructor(options = {}) {
    this.apiEndpoint = options.apiEndpoint || '/api/chat/contact-agent';
    this.siteKey = options.siteKey;
    this.sessionId = options.sessionId;
    this.containerId = options.containerId || 'chat-container';
    this.onClose = options.onClose || (() => {});
    this.onSuccess = options.onSuccess || (() => {});
  }

  /**
   * Show the contact form in the chat
   */
  show() {
    const formHtml = this.getFormHTML();
    const container = document.getElementById(this.containerId);
    
    if (container) {
      container.insertAdjacentHTML('beforeend', formHtml);
      this.attachEventListeners();
    }
  }

  /**
   * Get the HTML for the contact form
   */
  getFormHTML() {
    return `
      <div class="contact-agent-form" id="contact-agent-form">
        <div class="form-wrapper">
          <div class="form-header">
            <h3>Connect with Our Team</h3>
            <button type="button" class="close-btn" id="close-contact-form" aria-label="Close">×</button>
          </div>
          
          <form id="contact-form-element">
            <div class="form-group">
              <label for="contact-name">Your Name *</label>
              <input 
                type="text" 
                id="contact-name" 
                name="user_name" 
                placeholder="John Doe"
                required
                class="form-input"
              />
              <span class="error-message" id="error-name"></span>
            </div>

            <div class="form-group">
              <label for="contact-email">Email Address *</label>
              <input 
                type="email" 
                id="contact-email" 
                name="user_email" 
                placeholder="john@example.com"
                required
                class="form-input"
              />
              <span class="error-message" id="error-email"></span>
            </div>

            <div class="form-group">
              <label for="contact-message">Message *</label>
              <textarea 
                id="contact-message" 
                name="message" 
                placeholder="Please describe how we can help you..."
                required
                rows="4"
                class="form-input"
              ></textarea>
              <span class="error-message" id="error-message"></span>
            </div>

            <div class="form-group">
              <label for="contact-priority">Priority Level</label>
              <select id="contact-priority" name="priority" class="form-input">
                <option value="low">Low - General inquiry</option>
                <option value="normal" selected>Normal - Standard request</option>
                <option value="high">High - Important matter</option>
                <option value="urgent">Urgent - Time-sensitive</option>
              </select>
            </div>

            <div class="form-actions">
              <button type="submit" class="btn-submit" id="submit-contact-form">
                Send Request
              </button>
              <button type="button" class="btn-cancel" id="cancel-contact-form">
                Cancel
              </button>
            </div>

            <div class="loading-spinner" id="form-loading" style="display: none;">
              <span class="spinner"></span> Submitting...
            </div>

            <div class="success-message" id="form-success" style="display: none;">
              ✓ Your request has been submitted. Our team will contact you shortly.
            </div>

            <div class="error-message" id="form-error" style="display: none;"></div>
          </form>
        </div>
      </div>
    `;
  }

  /**
   * Attach event listeners to the form
   */
  attachEventListeners() {
    const form = document.getElementById('contact-form-element');
    const closeBtn = document.getElementById('close-contact-form');
    const cancelBtn = document.getElementById('cancel-contact-form');

    if (form) {
      form.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeForm());
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this.closeForm());
    }
  }

  /**
   * Handle form submission
   */
  async handleSubmit(event) {
    event.preventDefault();

    // Clear previous errors
    this.clearErrors();

    // Get form values
    const formData = new FormData(event.target);
    const data = {
      site_key: this.siteKey,
      session_id: this.sessionId,
      user_name: formData.get('user_name').trim(),
      user_email: formData.get('user_email').trim(),
      message: formData.get('message').trim(),
      priority: formData.get('priority') || 'normal'
    };

    // Validate
    const validation = this.validateForm(data);
    if (!validation.valid) {
      this.showErrors(validation.errors);
      return;
    }

    // Show loading state
    this.showLoading();

    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });

      const result = await response.json();

      if (response.ok && result.ok) {
        this.showSuccess(result.message || 'Your request has been submitted successfully!');
        // Close form after 3 seconds
        setTimeout(() => {
          this.closeForm();
          this.onSuccess(result);
        }, 3000);
      } else {
        throw new Error(result.error || 'Failed to submit request');
      }
    } catch (error) {
      this.showError(error.message);
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Validate form data
   */
  validateForm(data) {
    const errors = {};

    if (!data.user_name || data.user_name.length < 2) {
      errors.name = 'Please enter your name (at least 2 characters)';
    }

    if (!data.user_email || !this.isValidEmail(data.user_email)) {
      errors.email = 'Please enter a valid email address';
    }

    if (!data.message || data.message.length < 10) {
      errors.message = 'Please enter a message (at least 10 characters)';
    }

    return {
      valid: Object.keys(errors).length === 0,
      errors
    };
  }

  /**
   * Validate email format
   */
  isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Show field errors
   */
  showErrors(errors) {
    for (const [field, message] of Object.entries(errors)) {
      const errorElement = document.getElementById(`error-${field}`);
      if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
      }
    }
  }

  /**
   * Clear all errors
   */
  clearErrors() {
    const errorElements = document.querySelectorAll('.error-message');
    errorElements.forEach(el => {
      el.textContent = '';
      el.style.display = 'none';
    });
  }

  /**
   * Show loading state
   */
  showLoading() {
    const loadingEl = document.getElementById('form-loading');
    if (loadingEl) {
      loadingEl.style.display = 'block';
    }
  }

  /**
   * Hide loading state
   */
  hideLoading() {
    const loadingEl = document.getElementById('form-loading');
    if (loadingEl) {
      loadingEl.style.display = 'none';
    }
  }

  /**
   * Show success message
   */
  showSuccess(message) {
    const successEl = document.getElementById('form-success');
    if (successEl) {
      successEl.textContent = '✓ ' + message;
      successEl.style.display = 'block';
    }
  }

  /**
   * Show error message
   */
  showError(message) {
    const errorEl = document.getElementById('form-error');
    if (errorEl) {
      errorEl.textContent = '✗ ' + message;
      errorEl.style.display = 'block';
    }
  }

  /**
   * Close the form
   */
  closeForm() {
    const form = document.getElementById('contact-agent-form');
    if (form) {
      form.remove();
    }
    this.onClose();
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ContactAgentForm;
}
