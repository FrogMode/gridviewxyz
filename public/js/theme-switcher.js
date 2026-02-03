/**
 * GridView Theme Switcher
 * Manages racing livery themes with smooth transitions
 * 
 * v2.0 - Enhanced clickability and visual feedback
 */

const GridViewThemes = {
  themes: [
    { id: 'default', name: 'Midnight Racing', icon: '🌙', description: 'Classic F1 dark' },
    { id: 'gulf', name: 'Gulf Racing', icon: '🏎️', description: 'Le Mans \'70s legend' },
    { id: 'marlboro', name: 'Marlboro Red', icon: '🔴', description: 'Peak F1 dominance' },
    { id: 'jps', name: 'JPS Black & Gold', icon: '✨', description: 'Lotus elegance' },
    { id: 'silk-cut', name: 'Silk Cut Purple', icon: '💜', description: 'Jaguar Le Mans' },
    { id: 'camel', name: 'Camel Yellow', icon: '🌵', description: 'Desert heat' },
    { id: 'rothmans', name: 'Rothmans Blue', icon: '🔵', description: 'Williams excellence' },
    { id: 'martini', name: 'Martini Stripes', icon: '🍸', description: 'Italian racing (Light)' }
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
    
    // Load theme system CSS (only if not already loaded)
    if (!document.querySelector('link[href*="theme-system.css"]')) {
      const systemCss = document.createElement('link');
      systemCss.rel = 'stylesheet';
      systemCss.href = '/themes/theme-system.css';
      document.head.appendChild(systemCss);
    }
    
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
      // T key to cycle themes (when not in input)
      if (e.key === 't' && !e.target.matches('input, textarea, select')) {
        this.nextTheme();
      }
    });
    
    console.log('🎨 GridView Theme System v2.0 initialized');
    console.log('💡 Tip: Press T to cycle through themes!');
  },
  
  /**
   * Set the active theme
   * @param {string} themeId - Theme identifier
   * @param {boolean} animate - Whether to animate the transition
   */
  setTheme(themeId, animate = true) {
    const theme = this.themes.find(t => t.id === themeId);
    if (!theme) {
      console.warn(`Theme "${themeId}" not found, falling back to default`);
      themeId = 'default';
    }
    
    // Add transition class for smooth switching
    if (animate) {
      document.documentElement.classList.add('theme-transitioning');
    }
    
    // Update stylesheet
    this.themeLink.href = `/themes/${themeId}.css`;
    
    // Update data attribute
    document.documentElement.setAttribute('data-theme', themeId);
    
    // Update body class for light theme detection
    document.body.classList.toggle('theme-light', themeId === 'martini');
    
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
      detail: { theme: themeId, name: theme?.name } 
    }));
    
    // Log for debugging
    console.log(`🎨 Theme changed to: ${theme?.name || themeId}`);
  },
  
  /**
   * Update meta theme-color for mobile browsers
   */
  updateMetaThemeColor(themeId) {
    const colors = {
      default: '#e10600',
      gulf: '#5BA3D9',
      marlboro: '#EE1C25',
      'silk-cut': '#9B59B6',
      camel: '#F4C430',
      rothmans: '#0044AA',
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
      console.warn('Theme switcher: Nav container not found, retrying...');
      // Retry after DOM is fully loaded
      setTimeout(() => this.createSwitcherUI(), 100);
      return;
    }
    
    // Check if already created
    if (nav.querySelector('.theme-switcher')) {
      return;
    }
    
    // Create switcher container
    const switcher = document.createElement('div');
    switcher.className = 'theme-switcher relative';
    
    const currentTheme = this.themes.find(t => t.id === this.currentTheme);
    
    // Button only in the nav
    switcher.innerHTML = `
      <button class="theme-switcher-btn" aria-label="Change theme" aria-expanded="false" aria-haspopup="listbox">
        <span class="theme-icon">${currentTheme?.icon || '🎨'}</span>
        <span class="theme-name hidden sm:inline">Theme</span>
        <svg class="w-4 h-4 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
    `;
    
    // Create dialog element (uses browser's top-layer - guaranteed above everything)
    const dialog = document.createElement('dialog');
    dialog.className = 'theme-dialog';
    dialog.addEventListener('click', (e) => {
      // Close when clicking backdrop (outside dropdown content)
      if (e.target === dialog) {
        this.closeDropdown();
      }
    });
    
    // Create dropdown inside dialog
    const dropdown = document.createElement('div');
    dropdown.className = 'theme-dropdown';
    dropdown.setAttribute('role', 'listbox');
    dropdown.setAttribute('aria-label', 'Select theme');
    dropdown.innerHTML = this.themes.map(theme => `
      <button 
        class="theme-option ${theme.id === this.currentTheme ? 'active' : ''}" 
        data-theme="${theme.id}"
        role="option"
        aria-selected="${theme.id === this.currentTheme}"
        type="button"
      >
        <span class="theme-swatch swatch-${theme.id}"></span>
        <span class="theme-option-content">
          <span class="theme-option-name">${theme.icon} ${theme.name}</span>
          <span class="theme-option-desc text-xs opacity-60">${theme.description}</span>
        </span>
      </button>
    `).join('');
    dialog.appendChild(dropdown);
    document.body.appendChild(dialog);
    
    // Insert before the notification button
    const notifBtn = nav.querySelector('#notification-btn');
    if (notifBtn) {
      nav.insertBefore(switcher, notifBtn);
    } else {
      nav.appendChild(switcher);
    }
    
    // Set up event listeners
    this.setupEventListeners(switcher);
  },
  
  /**
   * Set up event listeners for the switcher
   */
  setupEventListeners(switcher) {
    const btn = switcher.querySelector('.theme-switcher-btn');
    const dropdown = document.body.querySelector('.theme-dropdown');
    
    // Toggle button click
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.toggleDropdown();
    });
    
    // Theme option clicks - Using event delegation for reliability
    dropdown.addEventListener('click', (e) => {
      const option = e.target.closest('.theme-option');
      if (option) {
        e.preventDefault();
        e.stopPropagation();
        
        const themeId = option.dataset.theme;
        if (themeId) {
          // Visual feedback
          option.style.transform = 'scale(0.95)';
          setTimeout(() => {
            option.style.transform = '';
          }, 100);
          
          // Apply theme
          this.setTheme(themeId);
          
          // Close dropdown after a tiny delay for visual feedback
          setTimeout(() => {
            this.closeDropdown();
          }, 150);
        }
      }
    });
    
    // Also add individual listeners as backup
    dropdown.querySelectorAll('.theme-option').forEach(option => {
      option.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const themeId = option.dataset.theme;
        if (themeId) {
          this.setTheme(themeId);
          setTimeout(() => this.closeDropdown(), 150);
        }
      });
      
      // Touch support
      option.addEventListener('touchend', (e) => {
        e.preventDefault();
        const themeId = option.dataset.theme;
        if (themeId) {
          this.setTheme(themeId);
          setTimeout(() => this.closeDropdown(), 150);
        }
      });
    });
    
    // Keyboard navigation within dropdown
    dropdown.addEventListener('keydown', (e) => {
      const options = [...dropdown.querySelectorAll('.theme-option')];
      const currentIndex = options.findIndex(opt => opt === document.activeElement);
      
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nextIndex = (currentIndex + 1) % options.length;
        options[nextIndex].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevIndex = (currentIndex - 1 + options.length) % options.length;
        options[prevIndex].focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const focusedOption = document.activeElement;
        if (focusedOption.classList.contains('theme-option')) {
          this.setTheme(focusedOption.dataset.theme);
          this.closeDropdown();
          btn.focus();
        }
      }
    });
  },
  
  /**
   * Toggle dropdown visibility
   */
  toggleDropdown() {
    this.dropdownOpen = !this.dropdownOpen;
    const dialog = document.querySelector('.theme-dialog');
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dialog && dropdown) {
      if (this.dropdownOpen) {
        // Position dropdown below button
        if (btn) {
          const rect = btn.getBoundingClientRect();
          dropdown.style.top = `${rect.bottom + 8}px`;
          dropdown.style.right = `${window.innerWidth - rect.right}px`;
        }
        // Show dialog (uses top-layer)
        dialog.showModal();
        dropdown.classList.add('open');
        
        // Focus first option
        const activeOption = dropdown.querySelector('.theme-option.active') || 
                           dropdown.querySelector('.theme-option');
        if (activeOption) {
          setTimeout(() => activeOption.focus(), 50);
        }
      } else {
        dropdown.classList.remove('open');
        dialog.close();
      }
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
    const dialog = document.querySelector('.theme-dialog');
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dropdown) {
      dropdown.classList.remove('open');
    }
    if (dialog && dialog.open) {
      dialog.close();
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
    
    // Update button icon and text
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
   * Cycle to previous theme
   */
  prevTheme() {
    const currentIndex = this.themes.findIndex(t => t.id === this.currentTheme);
    const prevIndex = (currentIndex - 1 + this.themes.length) % this.themes.length;
    this.setTheme(this.themes[prevIndex].id);
  },
  
  /**
   * Get current theme info
   */
  getCurrentTheme() {
    return this.themes.find(t => t.id === this.currentTheme);
  },
  
  /**
   * Check if current theme is light
   */
  isLightTheme() {
    return this.currentTheme === 'martini';
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
