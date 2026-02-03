/**
 * GridView Live Race Banner
 * Auto-updates every 30 seconds, shows when races are live
 */

(function() {
    const POLL_INTERVAL = 30000; // 30 seconds
    let bannerElement = null;

    function createBanner() {
        const banner = document.createElement('div');
        banner.id = 'live-race-banner';
        banner.style.cssText = `
            display: none;
            background: linear-gradient(90deg, #e10600, #ff4444);
            color: white;
            padding: 10px 20px;
            text-align: center;
            font-family: Inter, system-ui, sans-serif;
            font-weight: 600;
            font-size: 14px;
            position: relative;
            z-index: 100;
            animation: pulse-bg 2s ease-in-out infinite;
        `;
        
        // Add animation style
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse-bg {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.9; }
            }
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
            #live-race-banner .live-dot {
                display: inline-block;
                width: 8px;
                height: 8px;
                background: white;
                border-radius: 50%;
                margin-right: 8px;
                animation: blink 1s ease-in-out infinite;
            }
            #live-race-banner a {
                color: white;
                text-decoration: underline;
                margin-left: 10px;
            }
            #live-race-banner .upcoming-badge {
                background: rgba(255,255,255,0.2);
                padding: 2px 8px;
                border-radius: 4px;
                margin-left: 8px;
                font-size: 12px;
            }
        `;
        document.head.appendChild(style);
        
        // Insert at top of body
        document.body.insertBefore(banner, document.body.firstChild);
        return banner;
    }

    function formatTimeUntil(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = date - now;
        
        if (diff < 0) return 'now';
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        if (hours > 24) {
            const days = Math.floor(hours / 24);
            return `${days}d`;
        }
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }

    function renderBanner(data) {
        if (!bannerElement) {
            bannerElement = createBanner();
        }

        // Check for live races
        if (data.live && data.live.length > 0) {
            const race = data.live[0];
            bannerElement.innerHTML = `
                <span class="live-dot"></span>
                <strong>LIVE NOW:</strong> ${race.series_name} — ${race.event} ${race.session || ''}
                <a href="/telemetry.html">Watch Telemetry →</a>
            `;
            bannerElement.style.display = 'block';
            bannerElement.style.background = 'linear-gradient(90deg, #e10600, #ff4444)';
        }
        // Check for starting soon
        else if (data.live && data.live.some(r => r.status === 'starting_soon')) {
            const race = data.live.find(r => r.status === 'starting_soon');
            bannerElement.innerHTML = `
                <span class="live-dot" style="background: #fbbf24;"></span>
                <strong>STARTING SOON:</strong> ${race.series_name} — ${race.event} ${race.session || ''}
                <span class="upcoming-badge">in ${formatTimeUntil(race.starts)}</span>
            `;
            bannerElement.style.display = 'block';
            bannerElement.style.background = 'linear-gradient(90deg, #d97706, #f59e0b)';
        }
        // Show next upcoming race
        else if (data.upcoming && data.upcoming.length > 0) {
            const next = data.upcoming[0];
            const timeUntil = formatTimeUntil(next.date);
            
            // Only show if within 24 hours
            const hoursUntil = (new Date(next.date) - new Date()) / (1000 * 60 * 60);
            if (hoursUntil <= 24) {
                bannerElement.innerHTML = `
                    🏁 <strong>NEXT UP:</strong> ${next.series_name} — ${next.event}
                    <span class="upcoming-badge">${timeUntil}</span>
                `;
                bannerElement.style.display = 'block';
                bannerElement.style.background = 'linear-gradient(90deg, #1f2937, #374151)';
            } else {
                bannerElement.style.display = 'none';
            }
        } else {
            bannerElement.style.display = 'none';
        }
    }

    async function checkLiveRaces() {
        try {
            const resp = await fetch('/api/live');
            const data = await resp.json();
            renderBanner(data);
        } catch (e) {
            console.error('Live banner error:', e);
        }
    }

    // Initialize
    function init() {
        checkLiveRaces();
        setInterval(checkLiveRaces, POLL_INTERVAL);
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
