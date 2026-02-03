/**
 * GridView Theme Switcher
 * Manages racing livery themes with smooth transitions
 */

const GridViewThemes = {
  themes: [
    { id: 'default', name: 'Midnight Racing', icon: '🌙' },
    { id: 'gulf', name: 'Gulf Racing', icon: '🏎️' },
    { id: 'marlboro', name: 'Marlboro Red', icon: '🔴' },
    { id: 'silk-cut', name: 'Silk Cut Purple', icon: '💜' },
    { id: 'camel', name: 'Camel Yellow', icon: '🌵' },
    { id: 'rothmans', name: 'Rothmans Blue', icon: '🔵' },
    { id: 'martini', name: 'Martini Stripes', icon: '🍸' },
    { id: 'jps', name: 'JPS Black & Gold', icon: '🖤' }
  ],
  
  currentTheme: 'default',
  themeLink: null,
  dropdownOpen: false,
  
  /**
   * Initialize the theme system
   */
  init() {
    // Load saved theme preference
    const savedTheme = localStorage.getItem('gridview-theme') || 'default';
    
    // Create theme stylesheet link
    this.themeLink = document.createElement('link');
    this.themeLink.rel = 'stylesheet';
    this.themeLink.id = 'theme-css';
    document.head.appendChild(this.themeLink);
    
    // Load theme system CSS
    const systemCss = document.createElement('link');
    systemCss.rel = 'stylesheet';
    systemCss.href = '/themes/theme-system.css';
    document.head.appendChild(systemCss);
    
    // Apply saved theme
    this.setTheme(savedTheme, false);
    
    // Create UI
    this.createSwitcherUI();
    
    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.theme-switcher')) {
        this.closeDropdown();
      }
    });
    
    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.dropdownOpen) {
        this.closeDropdown();
      }
    });
    
    console.log('🎨 GridView Theme System initialized');
  },
  
  /**
   * Set the active theme
   * @param {string} themeId - Theme identifier
   * @param {boolean} animate - Whether to animate the transition
   */
  setTheme(themeId, animate = true) {
    const theme = this.themes.find(t => t.id === themeId);
    if (!theme) return;
    
    // Add transition class for smooth switching
    if (animate) {
      document.documentElement.classList.add('theme-transitioning');
    }
    
    // Update stylesheet
    this.themeLink.href = `/themes/${themeId}.css`;
    
    // Update data attribute
    document.documentElement.setAttribute('data-theme', themeId);
    
    // Update meta theme-color for mobile
    this.updateMetaThemeColor(themeId);
    
    // Save preference
    localStorage.setItem('gridview-theme', themeId);
    this.currentTheme = themeId;
    
    // Update UI
    this.updateSwitcherUI();
    
    // Remove transition class after animation
    if (animate) {
      setTimeout(() => {
        document.documentElement.classList.remove('theme-transitioning');
      }, 400);
    }
    
    // Fire custom event
    document.dispatchEvent(new CustomEvent('themechange', { 
      detail: { theme: themeId } 
    }));
  },
  
  /**
   * Update meta theme-color for mobile browsers
   */
  updateMetaThemeColor(themeId) {
    const colors = {
      default: '#e10600',
      gulf: '#6CACE4',
      marlboro: '#EE1C25',
      'silk-cut': '#7B4397',
      camel: '#F4C430',
      rothmans: '#003399',
      martini: '#CE1126',
      jps: '#D4AF37'
    };
    
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = colors[themeId] || colors.default;
  },
  
  /**
   * Create the theme switcher UI
   */
  createSwitcherUI() {
    // Find the nav container
    const nav = document.querySelector('nav .hidden.md\\:flex');
    if (!nav) {
      console.warn('Theme switcher: Nav container not found');
      return;
    }
    
    // Create switcher container
    const switcher = document.createElement('div');
    switcher.className = 'theme-switcher relative';
    switcher.innerHTML = `
      <button class="theme-switcher-btn" aria-label="Change theme" aria-expanded="false">
        <span class="theme-icon">🎨</span>
        <span class="theme-name hidden sm:inline">Theme</span>
        <svg class="w-4 h-4 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div class="theme-dropdown" role="listbox" aria-label="Select theme">
        ${this.themes.map(theme => `
          <button class="theme-option ${theme.id === this.currentTheme ? 'active' : ''}" 
                  data-theme="${theme.id}"
                  role="option"
                  aria-selected="${theme.id === this.currentTheme}">
            <span class="theme-swatch swatch-${theme.id}"></span>
            <span>${theme.icon} ${theme.name}</span>
          </button>
        `).join('')}
      </div>
    `;
    
    // Insert before the notification button
    const notifBtn = nav.querySelector('#notification-btn');
    if (notifBtn) {
      nav.insertBefore(switcher, notifBtn);
    } else {
      nav.appendChild(switcher);
    }
    
    // Event listeners
    const btn = switcher.querySelector('.theme-switcher-btn');
    const dropdown = switcher.querySelector('.theme-dropdown');
    
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleDropdown();
    });
    
    // Theme option clicks
    dropdown.querySelectorAll('.theme-option').forEach(option => {
      option.addEventListener('click', () => {
        const themeId = option.dataset.theme;
        this.setTheme(themeId);
        this.closeDropdown();
      });
    });
  },
  
  /**
   * Toggle dropdown visibility
   */
  toggleDropdown() {
    this.dropdownOpen = !this.dropdownOpen;
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dropdown) {
      dropdown.classList.toggle('open', this.dropdownOpen);
    }
    if (btn) {
      btn.setAttribute('aria-expanded', this.dropdownOpen);
      btn.querySelector('svg')?.classList.toggle('rotate-180', this.dropdownOpen);
    }
  },
  
  /**
   * Close the dropdown
   */
  closeDropdown() {
    this.dropdownOpen = false;
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dropdown) {
      dropdown.classList.remove('open');
    }
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
      btn.querySelector('svg')?.classList.remove('rotate-180');
    }
  },
  
  /**
   * Update the switcher UI to reflect current theme
   */
  updateSwitcherUI() {
    const options = document.querySelectorAll('.theme-option');
    options.forEach(option => {
      const isActive = option.dataset.theme === this.currentTheme;
      option.classList.toggle('active', isActive);
      option.setAttribute('aria-selected', isActive);
    });
    
    // Update button icon
    const theme = this.themes.find(t => t.id === this.currentTheme);
    const iconSpan = document.querySelector('.theme-switcher-btn .theme-icon');
    if (iconSpan && theme) {
      iconSpan.textContent = theme.icon;
    }
  },
  
  /**
   * Cycle to next theme (useful for keyboard shortcut)
   */
  nextTheme() {
    const currentIndex = this.themes.findIndex(t => t.id === this.currentTheme);
    const nextIndex = (currentIndex + 1) % this.themes.length;
    this.setTheme(this.themes[nextIndex].id);
  },
  
  /**
   * Get current theme info
   */
  getCurrentTheme() {
    return this.themes.find(t => t.id === this.currentTheme);
  }
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => GridViewThemes.init());
} else {
  GridViewThemes.init();
}

// Expose globally
window.GridViewThemes = GridViewThemes;
