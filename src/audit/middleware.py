from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware

from .context import audit_context


@sync_and_async_middleware
def audit_context_middleware(get_response):
    if iscoroutinefunction(get_response):
        async def middleware(request):
            with audit_context(request=request, user=None, description=None):
                return await get_response(request)
    else:
        def middleware(request):
            with audit_context(request=request, user=None, description=None):
                return get_response(request)

    return middleware
