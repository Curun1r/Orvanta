import asyncio
from types import SimpleNamespace

from django.http import HttpResponse
from django.test import SimpleTestCase

from .context import audit_context, get_audit_context
from .middleware import audit_context_middleware


class AuditRequestContextTests(SimpleTestCase):
    def test_request_context_is_reset_after_an_exception(self):
        request = SimpleNamespace(user=object())
        outer_user = object()

        def failing_response(current_request):
            self.assertIs(get_audit_context().request, current_request)
            self.assertIsNone(get_audit_context().user)
            raise RuntimeError('Request failed')

        with audit_context(user=outer_user):
            with self.assertRaisesMessage(RuntimeError, 'Request failed'):
                audit_context_middleware(failing_response)(request)
            self.assertIs(get_audit_context().user, outer_user)
            self.assertIsNone(get_audit_context().request)

        self.assertIsNone(get_audit_context().user)
        self.assertIsNone(get_audit_context().request)

    async def test_concurrent_async_requests_keep_their_own_context(self):
        both_entered = asyncio.Event()
        entered = 0
        first = SimpleNamespace(user=object())
        second = SimpleNamespace(user=object())

        async def response(request):
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=5)
            self.assertIs(get_audit_context().request, request)
            return HttpResponse()

        middleware = audit_context_middleware(response)
        await asyncio.gather(middleware(first), middleware(second))

        self.assertIsNone(get_audit_context().request)

    async def test_async_request_context_is_reset_after_an_exception(self):
        async def failing_response(request):
            await asyncio.sleep(0)
            self.assertIs(get_audit_context().request, request)
            raise RuntimeError('Async request failed')

        with self.assertRaisesMessage(RuntimeError, 'Async request failed'):
            await audit_context_middleware(failing_response)(SimpleNamespace(user=object()))

        self.assertIsNone(get_audit_context().request)
