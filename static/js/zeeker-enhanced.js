/**
 * Zeeker Enhanced JavaScript - Consolidated Version
 * Streamlined functionality with reusable components
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
        this.setupQueryHelpers();
        this.setupExampleQueries();

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
                // Add visual feedback
                const wrapper = heroSearchInput.closest('.hero-search-wrapper');
                if (wrapper) {
                    wrapper.style.transform = 'scale(0.98)';
                    wrapper.style.opacity = '0.7';
                }

                // Navigate to search page
                setTimeout(() => {
                    const searchUrl = new URL('/-/search', window.location.origin);
                    searchUrl.searchParams.set('q', query);
                    window.location.href = searchUrl.toString();
                }, 200);
            }
        });

        // Enhanced keyboard support
        heroSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                heroSearchForm.dispatchEvent(new Event('submit'));
            }
            if (e.key === 'Escape') {
                heroSearchInput.blur();
                heroSearchInput.value = '';
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
        // Enhanced copy button functionality for code blocks
        const codeElements = document.querySelectorAll('pre code, .highlight, .example-box pre');

        codeElements.forEach(element => {
            // Skip if already processed
            if (element.closest('.copy-button-added')) return;

            const codeBlock = element.tagName === 'PRE' ? element : element.closest('pre');
            if (!codeBlock) return;

            // Check if parent already has copy button
            if (codeBlock.parentElement.querySelector('.copy-btn')) return;

            const wrapper = codeBlock.parentElement;
            wrapper.classList.add('copy-button-added');
            wrapper.style.position = 'relative';

            const copyButton = document.createElement('button');
            copyButton.className = 'copy-btn';
            copyButton.innerHTML = '📋';
            copyButton.setAttribute('aria-label', 'Copy code');
            copyButton.title = 'Copy to clipboard';

            copyButton.addEventListener('click', () => {
                const text = element.textContent || codeBlock.textContent;
                this.copyToClipboard(text, copyButton);
            });

            wrapper.appendChild(copyButton);
        });

        // Handle existing copy buttons (from templates)
        document.querySelectorAll('.copy-btn').forEach(button => {
            if (!button.hasAttribute('data-enhanced')) {
                button.setAttribute('data-enhanced', 'true');
                button.addEventListener('click', (e) => {
                    e.preventDefault();
                    const codeBlock = button.previousElementSibling;
                    if (codeBlock) {
                        const text = codeBlock.textContent;
                        this.copyToClipboard(text, button);
                    }
                });
            }
        });
    }

    copyToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.innerHTML;
            const originalClass = button.className;

            button.innerHTML = '✅';
            button.classList.add('copied');

            setTimeout(() => {
                button.innerHTML = originalText;
                button.className = originalClass;
            }, 2000);
        }).catch(() => {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);

            const originalText = button.innerHTML;
            button.innerHTML = '✅';
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        });
    }

    addKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Skip if typing in form fields
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

                case 'Escape':
                    // Clear focus from active element
                    document.activeElement?.blur();
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
            scrollToTopBtn.setAttribute('aria-label', 'Scroll to top');
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

    setupQueryHelpers() {
        // SQL Query interface enhancements
        const sqlTextarea = document.querySelector('.sql-textarea');
        if (sqlTextarea) {
            // Auto-save functionality
            let autoSaveTimeout;
            sqlTextarea.addEventListener('input', () => {
                clearTimeout(autoSaveTimeout);
                autoSaveTimeout = setTimeout(() => {
                    if (sqlTextarea.value.trim()) {
                        localStorage.setItem('zeeker_auto_saved_query', sqlTextarea.value);
                    }
                }, 2000);
            });

            // Load auto-saved query if textarea is empty
            if (!sqlTextarea.value.trim()) {
                const saved = localStorage.getItem('zeeker_auto_saved_query');
                if (saved) {
                    sqlTextarea.value = saved;
                }
            }

            // SQL-specific shortcuts
            sqlTextarea.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    const form = sqlTextarea.closest('form');
                    if (form) form.submit();
                }

                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = sqlTextarea.selectionStart;
                    const end = sqlTextarea.selectionEnd;
                    const value = sqlTextarea.value;
                    sqlTextarea.value = value.substring(0, start) + '  ' + value.substring(end);
                    sqlTextarea.selectionStart = sqlTextarea.selectionEnd = start + 2;
                }
            });
        }

        // Query result enhancements
        this.enhanceQueryResults();
    }

    enhanceQueryResults() {
        // Copy results functionality
        const copyResultsButton = document.querySelector('[onclick="copyResults()"]');
        if (copyResultsButton) {
            copyResultsButton.onclick = null; // Remove inline handler
            copyResultsButton.addEventListener('click', () => {
                const table = document.querySelector('.query-results-table');
                if (table) {
                    const text = Array.from(table.querySelectorAll('tr')).map(row =>
                        Array.from(row.querySelectorAll('th, td')).map(cell =>
                            cell.textContent.trim()
                        ).join('\t')
                    ).join('\n');

                    this.copyToClipboard(text, copyResultsButton);
                }
            });
        }

        // Enhanced table interactions
        const resultTable = document.querySelector('.query-results-table');
        if (resultTable) {
            // Make cells selectable
            resultTable.addEventListener('click', (e) => {
                if (e.target.tagName === 'TD') {
                    // Clear previous selections
                    resultTable.querySelectorAll('.selected-cell').forEach(cell => {
                        cell.classList.remove('selected-cell');
                    });

                    e.target.classList.add('selected-cell');

                    // Copy cell content on double-click
                    e.target.addEventListener('dblclick', () => {
                        this.copyToClipboard(e.target.textContent.trim(), e.target);
                    }, { once: true });
                }
            });
        }
    }

    setupExampleQueries() {
        // Enhanced example query functionality
        const exampleButtons = document.querySelectorAll('[onclick*="useExample"]');
        exampleButtons.forEach(button => {
            // Remove inline onclick
            button.onclick = null;

            button.addEventListener('click', (e) => {
                e.preventDefault();
                const codeBlock = button.previousElementSibling;
                if (codeBlock && codeBlock.tagName === 'PRE') {
                    const query = codeBlock.textContent.trim();
                    const textarea = document.querySelector('.sql-textarea');
                    if (textarea) {
                        textarea.value = query;
                        textarea.focus();

                        // Visual feedback
                        button.style.background = 'var(--color-success)';
                        button.textContent = '✅ Added to Editor';
                        setTimeout(() => {
                            button.style.background = '';
                            button.textContent = button.getAttribute('data-original-text') || '🔗 Try This Query';
                        }, 2000);
                    }
                }
            });

            // Store original text
            if (!button.getAttribute('data-original-text')) {
                button.setAttribute('data-original-text', button.textContent);
            }
        });

        // Query formatting helper
        const formatButton = document.querySelector('[onclick="formatQuery()"]');
        if (formatButton) {
            formatButton.onclick = null;
            formatButton.addEventListener('click', () => {
                const textarea = document.querySelector('.sql-textarea');
                if (textarea) {
                    textarea.value = this.formatSQL(textarea.value);
                }
            });
        }
    }

    formatSQL(sql) {
        if (!sql.trim()) return sql;

        // Basic SQL formatting
        let formatted = sql
            .replace(/\s+/g, ' ') // Normalize whitespace
            .replace(/\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|ON|AND|OR|UNION|LIMIT|OFFSET)\b/gi, '\n$1')
            .replace(/,(?!\s*\n)/g, ',\n  ') // Commas on new lines with indent
            .replace(/\n\s*\n/g, '\n') // Remove empty lines
            .trim();

        return formatted;
    }

    // Utility methods
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// Global functions for template compatibility
window.copyCode = function(button) {
    const codeBlock = button.nextElementSibling;
    if (codeBlock) {
        const text = codeBlock.textContent;

        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.textContent;
            button.textContent = '✅ Copied!';
            button.style.background = '#10B981';

            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '';
            }, 2000);
        });
    }
};

window.useExample = function(button) {
    const code = button.previousElementSibling.textContent;
    const textarea = document.querySelector('.sql-textarea');
    if (textarea) {
        textarea.value = code.trim();
        textarea.focus();
    }
};

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