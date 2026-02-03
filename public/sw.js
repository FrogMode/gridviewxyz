// GridView Service Worker - Push Notifications
// Version: 1.0.0

const CACHE_NAME = 'gridview-v1';

// Handle push events from server
self.addEventListener('push', event => {
    console.log('[SW] Push received:', event);
    
    let data = {
        title: '🏁 GridView',
        body: 'New motorsport update!',
        icon: '/icons/icon-192.png',
        badge: '/icons/badge-72.png',
        tag: 'gridview-notification',
        url: '/'
    };
    
    // Parse push data if available
    if (event.data) {
        try {
            const payload = event.data.json();
            data = { ...data, ...payload };
        } catch (e) {
            // If not JSON, use as body text
            data.body = event.data.text();
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon || '/icons/icon-192.png',
        badge: data.badge || '/icons/badge-72.png',
        tag: data.tag || 'gridview-notification',
        data: { url: data.url || '/' },
        vibrate: [200, 100, 200],
        requireInteraction: data.requireInteraction || false,
        actions: data.actions || []
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    console.log('[SW] Notification clicked:', event);
    
    event.notification.close();
    
    const urlToOpen = event.notification.data?.url || '/';
    
    // Handle action button clicks
    if (event.action) {
        console.log('[SW] Action clicked:', event.action);
        // Could handle specific actions here
    }
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(windowClients => {
                // Check if GridView is already open
                for (const client of windowClients) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        client.navigate(urlToOpen);
                        return client.focus();
                    }
                }
                // Open new window if not
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

// Handle notification close
self.addEventListener('notificationclose', event => {
    console.log('[SW] Notification dismissed:', event.notification.tag);
});

// Service worker install
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker...');
    self.skipWaiting();
});

// Service worker activate
self.addEventListener('activate', event => {
    console.log('[SW] Service worker activated');
    event.waitUntil(clients.claim());
});

// Handle messages from main thread
self.addEventListener('message', event => {
    console.log('[SW] Message received:', event.data);
    
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
