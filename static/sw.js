// Enhanced Service Worker for Repolizer PWA

const CACHE_NAME = 'repolizer-v1.1';
const STATIC_CACHE = 'repolizer-static-v1.1';
const DYNAMIC_CACHE = 'repolizer-dynamic-v1.1';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/static/icons/favicon-16x16.png',
  '/static/icons/favicon-32x32.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/icon-72x72.png',
  '/static/icons/icon-96x96.png',
  '/static/icons/icon-128x128.png',
  '/static/icons/icon-144x144.png',
  '/static/icons/icon-152x152.png',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-384x384.png',
  '/static/icons/icon-512x512.png',
  '/static/js/pwa-installer.js',
  '/static/css/offline.css',
  '/offline',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2',
  'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js'
];

// URLs that should be cached dynamically
const DYNAMIC_URLS = [
  '/repo/',
  '/stats',
  '/repo_viewer.html',
  'results.jsonl'
];

// Install event - cache assets
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('Service Worker: Caching static files');
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => {
          return name.startsWith('repolizer-') && 
                 name !== STATIC_CACHE && 
                 name !== DYNAMIC_CACHE;
        })
        .map(name => {
          console.log('Service Worker: Deleting old cache:', name);
          return caches.delete(name);
        })
      );
    }).then(() => {
      console.log('Service Worker: Claiming clients');
      return self.clients.claim();
    })
  );
});

// Helper function to check if URL should be cached dynamically
function shouldCacheDynamically(url) {
  const urlObj = new URL(url);
  return DYNAMIC_URLS.some(pattern => urlObj.pathname.includes(pattern));
}

// Helper function to determine if URL is a data request that shouldn't be cached
function isUncacheableRequest(url) {
  return url.includes('/api/') || 
         url.includes('/scrape/') || 
         url.includes('/analyze');
}

// Fetch event - network first with fallback to cache for API requests,
// cache first with fallback to network for static assets
self.addEventListener('fetch', event => {
  const request = event.request;
  
  // Only handle GET requests
  if (request.method !== 'GET') return;
  
  // Skip cross-origin requests except allowed CDNs
  const url = new URL(request.url);
  const isAllowedExternal = 
    url.origin.includes('cdn.tailwindcss.com') || 
    url.origin.includes('cdnjs.cloudflare.com');
    
  if (url.origin !== self.location.origin && !isAllowedExternal) {
    return;
  }
  
  // Don't cache API requests but handle offline failures
  if (isUncacheableRequest(request.url)) {
    event.respondWith(
      fetch(request)
        .catch(error => {
          console.log('Service Worker: API request failed, serving offline content', error);
          return caches.match('/offline');
        })
    );
    return;
  }
  
  // Dynamic content strategy - Network first, then cache, fallback to offline page
  if (shouldCacheDynamically(request.url)) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cache a clone of the response
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE)
            .then(cache => {
              cache.put(request, responseToCache);
            });
          return response;
        })
        .catch(error => {
          console.log('Service Worker: Dynamic content fetch failed, checking cache', error);
          return caches.match(request)
            .then(cachedResponse => {
              return cachedResponse || caches.match('/offline');
            });
        })
    );
    return;
  }
  
  // Static assets strategy - Cache first, then network
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        return cachedResponse || fetch(request)
          .then(networkResponse => {
            // Cache new static assets on the fly
            const responseToCache = networkResponse.clone();
            caches.open(STATIC_CACHE)
              .then(cache => {
                cache.put(request, responseToCache);
              });
            return networkResponse;
          })
          .catch(error => {
            console.log('Service Worker: Static asset fetch failed', error);
            
            // Special handling for HTML requests - return offline page
            if (request.headers.get('Accept').includes('text/html')) {
              return caches.match('/offline');
            }
            
            // For other resources, return a simple error response
            return new Response('Network error happened', {
              status: 408,
              headers: { 'Content-Type': 'text/plain' }
            });
          });
      })
  );
});

// Handle push notifications (placeholder for future implementation)
self.addEventListener('push', event => {
  const data = event.data.json();
  
  const options = {
    body: data.body || 'New update from Repolizer',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-icon.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/'
    }
  };
  
  event.waitUntil(
    self.registration.showNotification(
      data.title || 'Repolizer Notification', 
      options
    )
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
