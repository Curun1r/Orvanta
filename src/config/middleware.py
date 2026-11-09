from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from django.utils.cache import patch_vary_headers


class PreferredLanguageMiddleware(LocaleMiddleware):
    """Start in English and retain an explicit language choice across visits."""

    def process_request(self, request):
        language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if language not in dict(settings.LANGUAGES):
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        response = super().process_response(request, response)
        patch_vary_headers(response, ('Cookie',))
        return response
