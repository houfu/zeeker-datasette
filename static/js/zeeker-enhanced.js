/**
 * Zeeker Enhanced JavaScript - Cleaned Version
 * Streamlined functionality for hero banner and core features
 */

class ZeekerEnhancer {
    constructor() {
        this.init();
    }

    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupFeatures());
        } else {
            this.setupFeatures();
        }
    }

    setupFeatures() {
        console.log('Zeeker Enhanced: Initializing...');

        this.addBodyClasses();
        this.enhanceHeroBanner();
        this.addSearchEnhancements();
        this.addCopyButtons();
        this.addKeyboardShortcuts();
        this.setupScrollToTop();

        console.log('Zeeker Enhanced: Complete');
    }

    addBodyClasses() {
        document.body.classList.add('zeeker-enhanced');

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

    enhanceHeroBanner() {
        const heroImage = document.querySelector('.hero-background-image');
        if (!heroImage) return;

        console.log('Zeeker: Enhancing hero banner...');

        const handleImageLoad = () => {
            heroImage.classList.remove('loading');
            heroImage.classList.add('loaded');
            this.triggerContentAnimations();
        };

        const handleImageError = () => {
            heroImage.classList.remove('loading');
            heroImage.classList.add('error');
            this.triggerContentAnimations();
        };

        if (heroImage.complete && heroImage.naturalWidth > 0) {
            handleImageLoad();
        } else {
            heroImage.addEventListener('load', handleImageLoad);
            heroImage.addEventListener('error', handleImageError);

            setTimeout(() => {
                if (!heroImage.classList.contains('loaded') && !heroImage.classList.contains('error')) {
                    this.triggerContentAnimations();
                }
            }, 3000);
        }

        this.setupHeroSearch();
        this.setupParallax(heroImage);
    }

    triggerContentAnimations() {
        const contentWrapper = document.querySelector('.hero-content-wrapper');
        if (contentWrapper) {
            contentWrapper.classList.add('animate-in');
        }
    }

    setupHeroSearch() {
        const heroSearchInput = document.querySelector('.hero-search-input');
        const heroSearchForm = document.querySelector('.hero-search-form');

        if (!heroSearchInput || !heroSearchForm) return;

        // Enhanced form submission
        heroSearchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const query = heroSearchInput.value.trim();

            if (query) {
                const wrapper = heroSearchInput.closest('.hero-search-wrapper');
                wrapper.style.transform = 'scale(0.98)';
                wrapper.style.opacity = '0.7';

                setTimeout(() => {
                    window.location.href = `/-/search?q=${encodeURIComponent(query)}`;
                }, 300);
            }
        });

        // Focus effects
        heroSearchInput.addEventListener('focus', () => {
            const wrapper = heroSearchInput.closest('.hero-search-wrapper');
            if (wrapper) {
                wrapper.style.transform = 'translateY(-2px) scale(1.02)';
                wrapper.style.boxShadow = '0 0 35px rgba(0, 212, 255, 0.4)';
            }
        });

        heroSearchInput.addEventListener('blur', () => {
            const wrapper = heroSearchInput.closest('.hero-search-wrapper');
            if (wrapper) {
                wrapper.style.transform = 'translateY(0) scale(1)';
                wrapper.style.boxShadow = '';
            }
        });

        // Escape key
        heroSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                heroSearchInput.blur();
                heroSearchInput.value = '';
            }
        });
    }

    setupParallax(heroImage) {
        // Only on larger screens and if motion is allowed
        if (window.innerWidth <= 768 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }

        let ticking = false;

        const updateParallax = () => {
            const scrollY = window.pageYOffset;
            const scrollProgress = Math.min(scrollY / window.innerHeight, 1);

            const parallaxY = scrollY * -0.4;
            const scale = 1.05 + (scrollProgress * 0.02);
            const opacity = Math.max(0.1, 0.35 - (scrollProgress * 0.25));

            heroImage.style.transform = `translate3d(0, ${parallaxY}px, 0) scale(${scale})`;
            heroImage.style.opacity = opacity;

            ticking = false;
        };

        const handleScroll = () => {
            if (!ticking) {
                requestAnimationFrame(updateParallax);
                ticking = true;
            }
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
    }

    addSearchEnhancements() {
        const searchInputs = document.querySelectorAll('input[type="search"], input[name="q"]');

        searchInputs.forEach(input => {
            if (input.classList.contains('hero-search-input')) return;

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    input.blur();
                }
                if (e.key === 'Enter' && e.ctrlKey) {
                    input.form?.submit();
                }
            });
        });
    }

    addCopyButtons() {
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
                transition: all 0.2s ease;
            `;

            copyButton.addEventListener('click', () => {
                const text = element.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    copyButton.innerHTML = '✅ Copied!';
                    copyButton.style.background = 'var(--color-success, #10B981)';
                    setTimeout(() => {
                        copyButton.innerHTML = '📋 Copy';
                        copyButton.style.background = 'var(--color-accent-primary)';
                    }, 2000);
                });
            });

            wrapper.appendChild(copyButton);
        });
    }

    addKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case '/':
                    e.preventDefault();
                    const heroSearchInput = document.querySelector('.hero-search-input');
                    const searchInput = heroSearchInput || document.querySelector('input[name="q"]');
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

    setupScrollToTop() {
        if (window.location.pathname !== '/') return;

        let scrollToTopBtn = document.querySelector('.scroll-to-top');

        if (!scrollToTopBtn) {
            scrollToTopBtn = document.createElement('button');
            scrollToTopBtn.className = 'scroll-to-top';
            scrollToTopBtn.innerHTML = '↑';
            scrollToTopBtn.style.cssText = `
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                width: 50px;
                height: 50px;
                background: var(--color-accent-primary);
                color: white;
                border: none;
                border-radius: 50%;
                font-size: 1.2rem;
                cursor: pointer;
                z-index: 1000;
                opacity: 0;
                transform: translateY(100px);
                transition: all 0.3s ease;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            `;
            document.body.appendChild(scrollToTopBtn);
        }

        window.addEventListener('scroll', () => {
            if (window.pageYOffset > window.innerHeight) {
                scrollToTopBtn.style.opacity = '1';
                scrollToTopBtn.style.transform = 'translateY(0)';
            } else {
                scrollToTopBtn.style.opacity = '0';
                scrollToTopBtn.style.transform = 'translateY(100px)';
            }
        });

        scrollToTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// Viewport height fix for mobile
function updateViewportHeight() {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
}

window.addEventListener('resize', updateViewportHeight);
window.addEventListener('orientationchange', updateViewportHeight);
updateViewportHeight();

// Initialize
new ZeekerEnhancer();