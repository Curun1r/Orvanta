import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class SymbolPasswordValidator:
    """
    Перевіряє що пароль містить хоча б одну велику літеру,
    одну малу літеру, одну цифру і один спецсимвол.
    Відповідає підказці у формі: A–Z, a–z, 0–9, ! @ # $ % ^ & * ( ) _ - + =
    """
    SYMBOLS = r'[!@#$%^&*()\-_+=]'

    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append(_('Your password must contain at least one uppercase letter (A–Z).'))
        if not re.search(r'[a-z]', password):
            errors.append(_('Your password must contain at least one lowercase letter (a–z).'))
        if not re.search(r'[0-9]', password):
            errors.append(_('Your password must contain at least one digit (0–9).'))
        if not re.search(self.SYMBOLS, password):
            errors.append(_('Your password must contain at least one special character (! @ # $ % ^ & * ( ) _ - + =).'))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            'Your password must contain an uppercase letter, a lowercase letter, a digit and a special character (! @ # $ % ^ & * ( ) _ - + =).'
        )
