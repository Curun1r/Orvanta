(function () {
    function setupPasswordToggles(root) {
        root.querySelectorAll('[data-password-toggle]').forEach(function (button) {
            var field = button.closest('.password-field');
            if (!field) {
                return;
            }

            var input = field.querySelector('input[type="password"], input[type="text"]');
            if (!input) {
                return;
            }

            button.addEventListener('click', function () {
                var isHidden = input.getAttribute('type') === 'password';
                input.setAttribute('type', isHidden ? 'text' : 'password');
                button.textContent = isHidden ? window.gettext('Hide') : window.gettext('Show');
                button.setAttribute(
                    'aria-label',
                    isHidden ? window.gettext('Hide password') : window.gettext('Show password')
                );
                input.focus({ preventScroll: true });
            });
        });
    }

    function setButtonLoading(button, text) {
        if (!button || button.disabled) {
            return;
        }

        button.dataset.originalText = button.textContent.trim();
        button.disabled = true;
        button.classList.add('is-loading');
        button.setAttribute('aria-busy', 'true');

        var spinner = document.createElement('span');
        spinner.className = 'button-spinner';
        spinner.setAttribute('aria-hidden', 'true');

        var label = document.createElement('span');
        label.textContent = text || button.dataset.originalText || window.gettext('Please wait...');

        button.replaceChildren(spinner, label);
    }

    function setupSubmitLoading(root) {
        root.querySelectorAll('[data-auth-form]').forEach(function (form) {
            form.addEventListener('submit', function () {
                if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
                    return;
                }

                form.setAttribute('aria-busy', 'true');
                var button = form.querySelector('[data-submit-button], button[type="submit"]');
                setButtonLoading(button, form.dataset.loadingText);
            });
        });
    }

    function setupAutofocus(root) {
        if (document.activeElement && document.activeElement !== document.body) {
            return;
        }

        var input = root.querySelector(
            '.auth-card input:not([type="hidden"]):not([disabled]), ' +
            '.auth-card select:not([disabled]), ' +
            '.auth-card textarea:not([disabled])'
        );

        if (input) {
            input.focus({ preventScroll: true });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var page = document.querySelector('.auth-page');
        if (!page) {
            return;
        }

        page.classList.add('auth-enhanced');
        setupPasswordToggles(page);
        setupSubmitLoading(page);
        setupAutofocus(page);

        window.requestAnimationFrame(function () {
            page.classList.add('is-ready');
        });
    });
})();
