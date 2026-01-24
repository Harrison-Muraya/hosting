let currentBillingCycle = 'monthly';
let selectedPlan = null;

function changeBillingCycle(cycle) {
    currentBillingCycle = cycle;
    
    // Update button styles
    document.querySelectorAll('.billing-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(cycle + 'Btn').classList.add('active');
    
    // Update all plan prices
    document.querySelectorAll('.plan-card').forEach(card => {
        const priceEl = card.querySelector('.plan-price');
        const price = card.dataset[cycle];
        priceEl.textContent = price;
    });
}

function orderPlan(planId, planName) {
    const isAuthenticated = document.body.dataset.authenticated === 'true';

    if (!isAuthenticated) {
        window.location.href = '/auth/login/?next=/plans/'
        return;
    }
    // {% if not user.is_authenticated %}
    //     window.location.href = '/auth/login/?next=/plans/';
    //     return;
    // {% endif %}
    
    selectedPlan = planId;
    const card = document.querySelector(`[data-plan-id="${planId}"]`);
    
    document.getElementById('orderPlanId').value = planId;
    document.getElementById('modalPlanName').textContent = planName;
    document.getElementById('summaryPlanName').textContent = planName;
    
    // Set prices in modal
    document.getElementById('monthlyPrice').textContent = '$' + card.dataset.monthly;
    document.getElementById('quarterlyPrice').textContent = '$' + card.dataset.quarterly;
    document.getElementById('annuallyPrice').textContent = '$' + card.dataset.annually;
    document.getElementById('summaryTotal').textContent = '$' + card.dataset.monthly;
    
    document.getElementById('orderModal').classList.remove('hidden');
}

function closeOrderModal() {
    document.getElementById('orderModal').classList.add('hidden');
}

// Update summary when billing cycle changes
document.addEventListener('DOMContentLoaded', function() {
    const billingInputs = document.querySelectorAll('input[name="billing_cycle"]');
    billingInputs.forEach(input => {
        input.addEventListener('change', function() {
            const cycle = this.value;
            document.getElementById('summaryBillingCycle').textContent = 
                cycle.charAt(0).toUpperCase() + cycle.slice(1);
            
            const card = document.querySelector(`[data-plan-id="${selectedPlan}"]`);
            if (card) {
                const price = card.dataset[cycle];
                document.getElementById('summaryTotal').textContent = '$' + price;
            }
        });
    });
});

// Handle form submission
document.getElementById('orderForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const errorDiv = document.getElementById('orderError');
    const submitBtn = document.getElementById('orderSubmitBtn');
    
    errorDiv.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Processing...';
    
    const formData = {
        plan_id: document.getElementById('orderPlanId').value,
        billing_cycle: document.querySelector('input[name="billing_cycle"]:checked').value,
        domain: document.getElementById('domain').value
    };
    
    try {
        const response = await fetch('/api/services/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin',
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Success - redirect to payment page
            window.location.href = `/dashboard/invoices/?new_invoice=${data.invoice.id}`;
        } else {
            errorDiv.textContent = data.error || 'Failed to create service. Please try again.';
            errorDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-credit-card mr-2"></i> Proceed to Payment';
        }
    } catch (error) {
        console.error('Error:', error);
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.classList.remove('hidden');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-credit-card mr-2"></i> Proceed to Payment';
    }
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
