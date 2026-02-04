/**
 * GridView Theme Switcher
 * Manages racing livery themes with light/dark mode toggle
 * 
 * v3.0 - Separate theme selection + light/dark toggle
 */

const GridViewThemes = {
  // Base themes (each has a dark and light variant)
  themes: [
    { id: 'default', name: 'Racing Red', icon: '🏎️', description: 'Classic F1' },
    { id: 'gulf', name: 'Gulf', icon: '🌊', description: 'Le Mans \'70s' },
    { id: 'marlboro', name: 'Marlboro', icon: '🔴', description: 'Peak F1' },
    { id: 'jps', name: 'JPS', icon: '✨', description: 'Lotus elegance' },
    { id: 'silk-cut', name: 'Silk Cut', icon: '💜', description: 'Jaguar' },
    { id: 'camel', name: 'Camel', icon: '🌵', description: 'Desert heat' },
    { id: 'rothmans', name: 'Rothmans', icon: '🔵', description: 'Williams' },
    { id: 'martini', name: 'Martini', icon: '🍸', description: 'Italian' }
  ],
  
  currentTheme: 'default',
  darkMode: true, // true = dark, false = light
  themeLink: null,
  dropdownOpen: false,
  
  /**
   * Initialize the theme system
   */
  init() {
    // Load saved preferences
    const savedTheme = localStorage.getItem('gridview-theme') || 'default';
    const savedMode = localStorage.getItem('gridview-mode');
    this.darkMode = savedMode !== 'light'; // Default to dark
    
    // Handle legacy theme names (convert old -light themes)
    let baseTheme = savedTheme;
    if (savedTheme.endsWith('-light')) {
      baseTheme = savedTheme.replace('-light', '');
      this.darkMode = false;
    } else if (savedTheme === 'light') {
      baseTheme = 'default';
      this.darkMode = false;
    }
    
    // Create theme stylesheet link
    this.themeLink = document.createElement('link');
    this.themeLink.rel = 'stylesheet';
    this.themeLink.id = 'theme-css';
    document.head.appendChild(this.themeLink);
    
    // Load theme system CSS
    if (!document.querySelector('link[href*="theme-system.css"]')) {
      const systemCss = document.createElement('link');
      systemCss.rel = 'stylesheet';
      systemCss.href = '/themes/theme-system.css';
      document.head.appendChild(systemCss);
    }
    
    // Apply saved theme
    this.currentTheme = baseTheme;
    this.applyTheme(false);
    
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
      if (e.key === 't' && !e.target.matches('input, textarea, select')) {
        this.nextTheme();
      }
      if (e.key === 'd' && !e.target.matches('input, textarea, select')) {
        this.toggleMode();
      }
    });
    
    console.log('🎨 GridView Theme System v3.0 initialized');
    console.log('💡 Press T to cycle themes, D to toggle dark/light!');
  },
  
  /**
   * Get the CSS file name for current theme + mode
   */
  getThemeCssFile() {
    // Martini is always light-ish, no dark variant
    if (this.currentTheme === 'martini') {
      return 'martini';
    }
    // Default theme: dark = 'default', light = 'light'
    if (this.currentTheme === 'default') {
      return this.darkMode ? 'default' : 'light';
    }
    // Other themes: dark = '{theme}', light = '{theme}-light'
    return this.darkMode ? this.currentTheme : `${this.currentTheme}-light`;
  },
  
  /**
   * Apply current theme and mode
   */
  applyTheme(animate = true) {
    const cssFile = this.getThemeCssFile();
    
    if (animate) {
      document.documentElement.classList.add('theme-transitioning');
    }
    
    // Update stylesheet
    this.themeLink.href = `/themes/${cssFile}.css`;
    
    // Update data attributes
    document.documentElement.setAttribute('data-theme', cssFile);
    document.documentElement.setAttribute('data-mode', this.darkMode ? 'dark' : 'light');
    
    // Update body class
    document.body.classList.toggle('theme-light', !this.darkMode);
    
    // Update meta theme-color
    this.updateMetaThemeColor();
    
    // Save preferences
    localStorage.setItem('gridview-theme', this.currentTheme);
    localStorage.setItem('gridview-mode', this.darkMode ? 'dark' : 'light');
    
    // Update UI
    this.updateSwitcherUI();
    
    if (animate) {
      setTimeout(() => {
        document.documentElement.classList.remove('theme-transitioning');
      }, 400);
    }
    
    // Fire event
    const theme = this.themes.find(t => t.id === this.currentTheme);
    document.dispatchEvent(new CustomEvent('themechange', { 
      detail: { theme: this.currentTheme, mode: this.darkMode ? 'dark' : 'light', name: theme?.name } 
    }));
    
    console.log(`🎨 Theme: ${theme?.name || this.currentTheme} (${this.darkMode ? 'dark' : 'light'})`);
  },
  
  /**
   * Set theme (base theme only)
   */
  setTheme(themeId, animate = true) {
    const theme = this.themes.find(t => t.id === themeId);
    if (!theme) {
      console.warn(`Theme "${themeId}" not found`);
      return;
    }
    this.currentTheme = themeId;
    this.applyTheme(animate);
  },
  
  /**
   * Toggle between light and dark mode
   */
  toggleMode() {
    this.darkMode = !this.darkMode;
    this.applyTheme(true);
  },
  
  /**
   * Set mode explicitly
   */
  setMode(dark) {
    this.darkMode = dark;
    this.applyTheme(true);
  },
  
  /**
   * Update meta theme-color
   */
  updateMetaThemeColor() {
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
    meta.content = colors[this.currentTheme] || colors.default;
  },
  
  /**
   * Create the theme switcher UI
   */
  createSwitcherUI() {
    const nav = document.querySelector('nav .hidden.md\\:flex');
    if (!nav) {
      setTimeout(() => this.createSwitcherUI(), 100);
      return;
    }
    
    if (nav.querySelector('.theme-switcher')) return;
    
    const theme = this.themes.find(t => t.id === this.currentTheme);
    
    // Create container with theme dropdown + mode toggle
    const switcher = document.createElement('div');
    switcher.className = 'theme-switcher relative flex items-center gap-2';
    
    switcher.innerHTML = `
      <button class="theme-switcher-btn" aria-label="Change theme" aria-expanded="false">
        <span class="theme-icon">${theme?.icon || '🎨'}</span>
        <span class="theme-name hidden sm:inline">${theme?.name || 'Theme'}</span>
        <svg class="w-4 h-4 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <button class="mode-toggle-btn" aria-label="Toggle light/dark mode" title="Toggle light/dark (D)">
        <span class="mode-icon">${this.darkMode ? '🌙' : '☀️'}</span>
      </button>
    `;
    
    // Create dialog for dropdown
    const dialog = document.createElement('dialog');
    dialog.className = 'theme-dialog';
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) this.closeDropdown();
    });
    
    const dropdown = document.createElement('div');
    dropdown.className = 'theme-dropdown';
    dropdown.setAttribute('role', 'listbox');
    dropdown.innerHTML = this.themes.map(t => `
      <button class="theme-option ${t.id === this.currentTheme ? 'active' : ''}" 
              data-theme="${t.id}" role="option" type="button">
        <span class="theme-swatch swatch-${t.id}"></span>
        <span class="theme-option-content">
          <span class="theme-option-name">${t.icon} ${t.name}</span>
          <span class="theme-option-desc text-xs opacity-60">${t.description}</span>
        </span>
      </button>
    `).join('');
    
    dialog.appendChild(dropdown);
    document.body.appendChild(dialog);
    
    // Insert before notification button
    const notifBtn = nav.querySelector('#notification-btn');
    if (notifBtn) {
      nav.insertBefore(switcher, notifBtn);
    } else {
      nav.appendChild(switcher);
    }
    
    this.setupEventListeners(switcher);
  },
  
  /**
   * Set up event listeners
   */
  setupEventListeners(switcher) {
    const btn = switcher.querySelector('.theme-switcher-btn');
    const modeBtn = switcher.querySelector('.mode-toggle-btn');
    const dropdown = document.body.querySelector('.theme-dropdown');
    
    // Theme dropdown toggle
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.toggleDropdown();
    });
    
    // Mode toggle
    modeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.toggleMode();
    });
    
    // Theme selection
    dropdown.addEventListener('click', (e) => {
      const option = e.target.closest('.theme-option');
      if (option) {
        e.preventDefault();
        const themeId = option.dataset.theme;
        if (themeId) {
          this.setTheme(themeId);
          setTimeout(() => this.closeDropdown(), 150);
        }
      }
    });
    
    // Keyboard nav in dropdown
    dropdown.addEventListener('keydown', (e) => {
      const options = [...dropdown.querySelectorAll('.theme-option')];
      const idx = options.findIndex(opt => opt === document.activeElement);
      
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        options[(idx + 1) % options.length].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        options[(idx - 1 + options.length) % options.length].focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const focused = document.activeElement;
        if (focused.classList.contains('theme-option')) {
          this.setTheme(focused.dataset.theme);
          this.closeDropdown();
        }
      }
    });
  },
  
  toggleDropdown() {
    this.dropdownOpen = !this.dropdownOpen;
    const dialog = document.querySelector('.theme-dialog');
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dialog && dropdown) {
      if (this.dropdownOpen) {
        if (btn) {
          const rect = btn.getBoundingClientRect();
          dropdown.style.top = `${rect.bottom + 8}px`;
          dropdown.style.right = `${window.innerWidth - rect.right}px`;
        }
        dialog.showModal();
        dropdown.classList.add('open');
        const active = dropdown.querySelector('.theme-option.active') || dropdown.querySelector('.theme-option');
        if (active) setTimeout(() => active.focus(), 50);
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
  
  closeDropdown() {
    this.dropdownOpen = false;
    const dialog = document.querySelector('.theme-dialog');
    const dropdown = document.querySelector('.theme-dropdown');
    const btn = document.querySelector('.theme-switcher-btn');
    
    if (dropdown) dropdown.classList.remove('open');
    if (dialog && dialog.open) dialog.close();
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
      btn.querySelector('svg')?.classList.remove('rotate-180');
    }
  },
  
  updateSwitcherUI() {
    // Update theme options
    document.querySelectorAll('.theme-option').forEach(opt => {
      const isActive = opt.dataset.theme === this.currentTheme;
      opt.classList.toggle('active', isActive);
      opt.setAttribute('aria-selected', isActive);
    });
    
    // Update button
    const theme = this.themes.find(t => t.id === this.currentTheme);
    const iconSpan = document.querySelector('.theme-switcher-btn .theme-icon');
    const nameSpan = document.querySelector('.theme-switcher-btn .theme-name');
    if (iconSpan && theme) iconSpan.textContent = theme.icon;
    if (nameSpan && theme) nameSpan.textContent = theme.name;
    
    // Update mode toggle
    const modeIcon = document.querySelector('.mode-toggle-btn .mode-icon');
    if (modeIcon) modeIcon.textContent = this.darkMode ? '🌙' : '☀️';
  },
  
  nextTheme() {
    const idx = this.themes.findIndex(t => t.id === this.currentTheme);
    const next = (idx + 1) % this.themes.length;
    this.setTheme(this.themes[next].id);
  },
  
  prevTheme() {
    const idx = this.themes.findIndex(t => t.id === this.currentTheme);
    const prev = (idx - 1 + this.themes.length) % this.themes.length;
    this.setTheme(this.themes[prev].id);
  },
  
  getCurrentTheme() {
    return this.themes.find(t => t.id === this.currentTheme);
  },
  
  isLightMode() {
    return !this.darkMode;
  }
};

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => GridViewThemes.init());
} else {
  GridViewThemes.init();
}

window.GridViewThemes = GridViewThemes;
