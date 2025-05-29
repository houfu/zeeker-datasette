/**
 * Zeeker Enhanced JavaScript - Safe Version
 * Only adds enhancements without interfering with table visibility
 */

class ZeekerEnhancer {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('DOMContentLoaded', () => {
      console.log('Zeeker Enhanced: Initializing...');
      this.addBodyClasses();
      this.enhanceSearch();
      this.addCopyButtons();
      this.enhanceExportLinks();
      this.addKeyboardShortcuts();
      // REMOVED: this.addTableEnhancements(); - This was hiding tables
      console.log('Zeeker Enhanced: Initialization complete');
    });
  }

  addBodyClasses() {
    document.body.classList.add('zeeker-enhanced');

    // Add specific page classes for enhanced styling
    const path = window.location.pathname;
    if (path === '/') {
      document.body.classList.add('page-home');
    } else if (path.includes('/query')) {
      document.body.classList.add('page-query');
    } else if (path.match(/\/[^/]+\/[^/]+$/)) {
      document.body.classList.add('page-table');
    } else if (path.match(/\/[^/]+$/)) {
      document.body.classList.add('page-database');
    }
  }

  enhanceSearch() {
    const searchInputs = document.querySelectorAll('input[type="search"], input[name="q"]');

    searchInputs.forEach(input => {
      // Add keyboard shortcuts
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          input.blur();
        }
        if (e.key === 'Enter' && e.ctrlKey) {
          // Ctrl+Enter for quick search
          input.form?.submit();
        }
      });
    });
  }

  addCopyButtons() {
    // Add copy buttons to code blocks only (not tables)
    const codeElements = document.querySelectorAll('pre code, .highlight');

    codeElements.forEach(element => {
      if (element.closest('.copy-button-added')) return;

      const wrapper = document.createElement('div');
      wrapper.className = 'code-wrapper copy-button-added';
      wrapper.style.position = 'relative';

      element.parentNode.insertBefore(wrapper, element);
      wrapper.appendChild(element);

      const copyButton = document.createElement('button');
      copyButton.className = 'copy-btn';
      copyButton.innerHTML = '📋 Copy';
      copyButton.style.cssText = `
        position: absolute;
        top: 8px;
        right: 8px;
        background: var(--color-accent-primary);
        color: white;
        border: none;
        padding: 0.4rem 0.8rem;
        border-radius: 4px;
        font-size: 0.8rem;
        cursor: pointer;
        z-index: 10;
      `;

      copyButton.addEventListener('click', () => {
        const text = element.textContent;
        navigator.clipboard.writeText(text).then(() => {
          copyButton.innerHTML = '✅ Copied!';
          setTimeout(() => {
            copyButton.innerHTML = '📋 Copy';
          }, 2000);
        });
      });

      wrapper.appendChild(copyButton);
    });
  }

  enhanceExportLinks() {
    const exportLinks = document.querySelectorAll('.export-links a, a[href$=".csv"], a[href$=".json"]');

    exportLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        // Add loading state
        const originalText = link.textContent;
        link.textContent = '⬇️ Downloading...';
        link.style.pointerEvents = 'none';

        setTimeout(() => {
          link.textContent = originalText;
          link.style.pointerEvents = 'auto';
        }, 2000);
      });
    });
  }

  addKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Only activate shortcuts when not in input fields
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case '/':
          e.preventDefault();
          const searchInput = document.querySelector('input[name="q"]');
          if (searchInput) {
            searchInput.focus();
          }
          break;

        case 'h':
          if (e.ctrlKey) {
            e.preventDefault();
            window.location.href = '/';
          }
          break;

        case 'b':
          if (e.ctrlKey) {
            e.preventDefault();
            window.history.back();
          }
          break;
      }
    });
  }
}

// Initialize the enhancer
new ZeekerEnhancer();

class ZeekerFullViewportHero {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('DOMContentLoaded', () => {
      this.setupHeroEnhancements();
      this.addScrollIndicator();
      this.handleViewportResize();
      this.optimizeImageLoading();
      this.addKeyboardNavigation();
    });
  }

  setupHeroEnhancements() {
    // Add body classes for styling coordination
    const heroElement = document.querySelector('.hero-fullscreen, .hero-split-viewport, .hero-immersive-full');

    if (heroElement) {
      if (heroElement.classList.contains('hero-fullscreen')) {
        document.body.classList.add('hero-fullscreen-active');
      } else if (heroElement.classList.contains('hero-split-viewport')) {
        document.body.classList.add('hero-split-active');
      } else if (heroElement.classList.contains('hero-immersive-full')) {
        document.body.classList.add('hero-immersive-active');
      }
    }

    // Enhanced search form functionality
    const heroSearchForm = document.querySelector('.search-form-hero');
    if (heroSearchForm) {
      this.enhanceHeroSearch(heroSearchForm);
    }

    // Add parallax scrolling for immersive hero
    if (document.querySelector('.hero-immersive-full')) {
      this.addParallaxScrolling();
    }
  }

  enhanceHeroSearch(form) {
    const input = form.querySelector('input');

    // Add auto-complete suggestions
    this.addSearchAutoComplete(input);

    // Add search animation
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.animateSearch(input);

      // Simulate search - replace with actual search logic
      setTimeout(() => {
        if (input.value.trim()) {
          window.location.href = `/-/search?q=${encodeURIComponent(input.value)}`;
        }
      }, 500);
    });

    // Add keyboard shortcuts
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        input.blur();
        input.value = '';
      }
    });
  }

  addSearchAutoComplete(input) {
    const suggestions = [
      'court decisions',
      'supreme court',
      'high court',
      'parliamentary debates',
      'legal regulations',
      'case law',
      'statutory instruments',
      'legal precedents',
      'contract law',
      'criminal law',
      'civil procedure'
    ];

    let suggestionContainer = null;

    input.addEventListener('input', () => {
      this.showSearchSuggestions(input, suggestions);
    });

    input.addEventListener('blur', () => {
      setTimeout(() => this.hideSearchSuggestions(), 200);
    });
  }

  showSearchSuggestions(input, suggestions) {
    const query = input.value.toLowerCase().trim();

    if (query.length < 2) {
      this.hideSearchSuggestions();
      return;
    }

    const matches = suggestions.filter(s =>
      s.toLowerCase().includes(query)
    ).slice(0, 5);

    if (matches.length === 0) {
      this.hideSearchSuggestions();
      return;
    }

    let container = document.getElementById('hero-search-suggestions');
    if (!container) {
      container = document.createElement('div');
      container.id = 'hero-search-suggestions';
      container.className = 'hero-search-suggestions';
      input.parentNode.appendChild(container);
    }

    container.innerHTML = matches.map(match =>
      `<div class="suggestion-item" data-value="${match}">
        <span class="suggestion-icon">🔍</span>
        <span class="suggestion-text">${match}</span>
      </div>`
    ).join('');

    container.style.display = 'block';

    // Add click handlers
    container.querySelectorAll('.suggestion-item').forEach(item => {
      item.addEventListener('click', () => {
        input.value = item.dataset.value;
        this.hideSearchSuggestions();
        input.form.dispatchEvent(new Event('submit'));
      });
    });

    this.addSuggestionStyles();
  }

  hideSearchSuggestions() {
    const container = document.getElementById('hero-search-suggestions');
    if (container) {
      container.style.display = 'none';
    }
  }

  addSuggestionStyles() {
    if (document.getElementById('hero-search-styles')) return;

    const style = document.createElement('style');
    style.id = 'hero-search-styles';
    style.textContent = `
      .hero-search-suggestions {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: rgba(17, 17, 17, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-top: none;
        border-radius: 0 0 25px 25px;
        max-height: 300px;
        overflow-y: auto;
        z-index: 1000;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      }

      .suggestion-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 1.5rem;
        cursor: pointer;
        transition: all 0.2s ease;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      }

      .suggestion-item:hover {
        background: rgba(0, 212, 255, 0.1);
        color: var(--color-accent-cyan);
      }

      .suggestion-item:last-child {
        border-bottom: none;
      }

      .suggestion-icon {
        opacity: 0.7;
      }

      .suggestion-text {
        flex: 1;
        color: var(--color-text-secondary);
      }

      .suggestion-item:hover .suggestion-text {
        color: var(--color-text-primary);
      }
    `;
    document.head.appendChild(style);
  }

  animateSearch(input) {
    input.style.transform = 'scale(0.98)';
    input.style.opacity = '0.8';

    setTimeout(() => {
      input.style.transform = 'scale(1)';
      input.style.opacity = '1';
    }, 200);
  }

  addScrollIndicator() {
    const heroElement = document.querySelector('.hero-fullscreen, .hero-split-viewport, .hero-immersive-full');
    if (!heroElement) return;

    const indicator = document.createElement('div');
    indicator.className = 'scroll-indicator';
    indicator.innerHTML = `
      <div class="scroll-arrow">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M7 13l3 3 7-7"></path>
          <path d="M7 6l3 3 7-7"></path>
        </svg>
      </div>
      <span>Scroll to explore</span>
    `;

    heroElement.appendChild(indicator);
    this.addScrollIndicatorStyles();

    // Hide indicator on scroll
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const scrolled = window.pageYOffset > 100;
          indicator.style.opacity = scrolled ? '0' : '1';
          indicator.style.transform = scrolled ? 'translateY(20px)' : 'translateY(0)';
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  addScrollIndicatorStyles() {
    if (document.getElementById('scroll-indicator-styles')) return;

    const style = document.createElement('style');
    style.id = 'scroll-indicator-styles';
    style.textContent = `
      .scroll-indicator {
        position: absolute;
        bottom: 2rem;
        left: 50%;
        transform: translateX(-50%);
        z-index: 10;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        color: var(--color-text-muted);
        font-size: 0.9rem;
        opacity: 0.8;
        transition: all 0.3s ease;
        animation: bounce 2s infinite;
      }

      .scroll-arrow {
        transform: rotate(90deg);
        opacity: 0.7;
      }

      @keyframes bounce {
        0%, 20%, 50%, 80%, 100% {
          transform: translateX(-50%) translateY(0);
        }
        40% {
          transform: translateX(-50%) translateY(-10px);
        }
        60% {
          transform: translateX(-50%) translateY(-5px);
        }
      }

      @media (max-width: 768px) {
        .scroll-indicator {
          bottom: 1rem;
          font-size: 0.8rem;
        }
      }
    `;
    document.head.appendChild(style);
  }

  addParallaxScrolling() {
    const parallaxElement = document.querySelector('.hero-immersive-bg');
    if (!parallaxElement) return;

    let ticking = false;

    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const scrolled = window.pageYOffset;
          const rate = scrolled * -0.5;
          parallaxElement.style.transform = `translate3d(0, ${rate}px, 0)`;
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  handleViewportResize() {
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        this.updateViewportHeight();
      }, 250);
    });
  }

  updateViewportHeight() {
    const heroElements = document.querySelectorAll('.hero-fullscreen, .hero-split-viewport, .hero-immersive-full');
    heroElements.forEach(hero => {
      hero.style.height = `${window.innerHeight}px`;
    });
  }

  optimizeImageLoading() {
    // Preload the hero image
    const img = new Image();
    img.src = '/static/images/holographic-building.png';

    // Add intersection observer for lazy loading optimization
    if ('IntersectionObserver' in window) {
      const heroImages = document.querySelectorAll('.hero-building-image');
      const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('loaded');
            imageObserver.unobserve(entry.target);
          }
        });
      });

      heroImages.forEach(img => imageObserver.observe(img));
    }
  }

  addKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
      // Skip if user is typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case '/':
          e.preventDefault();
          const searchInput = document.querySelector('.search-form-hero input');
          if (searchInput) {
            searchInput.focus();
          }
          break;

        case 'Escape':
          const activeInput = document.activeElement;
          if (activeInput.tagName === 'INPUT') {
            activeInput.blur();
          }
          this.hideSearchSuggestions();
          break;
      }
    });
  }
}

// Initialize the full viewport hero enhancement
new ZeekerFullViewportHero();

// Debug helper - shows when tables are being manipulated
const originalHide = Element.prototype.style.setProperty;
Element.prototype.style.setProperty = function(property, value, priority) {
  if ((property === 'display' && value === 'none') ||
      (property === 'visibility' && value === 'hidden') ||
      (property === 'opacity' && value === '0')) {
    if (this.tagName === 'TR' || this.tagName === 'TABLE' || this.closest('table')) {
      console.warn('WARNING: Something is trying to hide table element:', this, property, value);
      console.trace(); // This will show what's calling it
      return; // Prevent hiding table elements
    }
  }
  return originalHide.call(this, property, value, priority);
};