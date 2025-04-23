/**
 * Repolizer PWA Installation Handler
 * Manages the installation prompt and installation process
 */

// Store the deferred prompt for later use
let deferredPrompt;
let installButtonShown = false;

// Functions to control the install UI
function showInstallPromotion() {
  const installPromo = document.getElementById('pwa-install-promotion');
  const installButton = document.getElementById('pwa-install-button');
  
  if (installPromo && !installButtonShown) {
    installPromo.classList.remove('hidden');
    installButtonShown = true;
  }
  
  if (installButton) {
    installButton.addEventListener('click', installPWA);
  }
}

function hideInstallPromotion() {
  const installPromo = document.getElementById('pwa-install-promotion');
  
  if (installPromo) {
    installPromo.classList.add('hidden');
    installButtonShown = false;
  }
}

// Install the PWA
async function installPWA() {
  if (!deferredPrompt) {
    console.log('No installation prompt available');
    return;
  }
  
  // Show the browser's install prompt
  deferredPrompt.prompt();
  
  // Wait for the user to respond
  const choiceResult = await deferredPrompt.userChoice;
  
  // Log the user's choice
  if (choiceResult.outcome === 'accepted') {
    console.log('User accepted the install prompt');
    showInstallSuccess();
  } else {
    console.log('User dismissed the install prompt');
  }
  
  // Clear the deferred prompt
  deferredPrompt = null;
  hideInstallPromotion();
}

// Show a success message after install
function showInstallSuccess() {
  const successMessage = document.getElementById('pwa-install-success');
  
  if (successMessage) {
    successMessage.classList.remove('hidden');
    
    // Hide the success message after 5 seconds
    setTimeout(() => {
      successMessage.classList.add('hidden');
    }, 5000);
  }
}

// Listen for the beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (event) => {
  // Prevent the default browser install prompt
  event.preventDefault();
  
  // Store the event for later use
  deferredPrompt = event;
  
  // Show custom install button
  showInstallPromotion();
});

// Listen for the appinstalled event
window.addEventListener('appinstalled', (event) => {
  console.log('PWA was installed');
  deferredPrompt = null;
  hideInstallPromotion();
  showInstallSuccess();
});

// Check if running in standalone mode (already installed)
window.addEventListener('DOMContentLoaded', () => {
  if (window.matchMedia('(display-mode: standalone)').matches || 
      window.navigator.standalone === true) {
    console.log('App is running in standalone mode');
    // Add a class to the body for special PWA styling
    document.body.classList.add('pwa-standalone');
  }
  
  // Add install button to the DOM if it doesn't exist
  if (!document.getElementById('pwa-install-promotion')) {
    const installPrompt = document.createElement('div');
    installPrompt.id = 'pwa-install-promotion';
    installPrompt.className = 'fixed bottom-0 left-0 right-0 bg-blue-600 text-white p-4 flex justify-between items-center hidden';
    installPrompt.innerHTML = `
      <div>
        <strong>Install Repolizer</strong>
        <p class="text-sm">Add to your home screen for easier access</p>
      </div>
      <button id="pwa-install-button" class="bg-white text-blue-600 px-4 py-2 rounded-lg font-bold">Install</button>
      <button id="pwa-dismiss-button" class="text-white ml-2"><i class="fas fa-times"></i></button>
    `;
    
    document.body.appendChild(installPrompt);
    
    // Add success message element
    const successMessage = document.createElement('div');
    successMessage.id = 'pwa-install-success';
    successMessage.className = 'fixed top-0 left-0 right-0 bg-green-600 text-white p-4 text-center hidden';
    successMessage.innerHTML = `
      <p><i class="fas fa-check-circle mr-2"></i> Repolizer has been successfully installed!</p>
    `;
    
    document.body.appendChild(successMessage);
    
    // Add dismiss button functionality
    document.getElementById('pwa-dismiss-button').addEventListener('click', hideInstallPromotion);
  }
});
