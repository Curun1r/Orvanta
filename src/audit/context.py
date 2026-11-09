from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AuditContext:
    request: object = None
    user: object = None
    description: str | None = None


_audit_context = ContextVar('audit_context', default=AuditContext())


def get_audit_context():
    return _audit_context.get()


@contextmanager
def audit_context(**overrides):
    """Supply a trusted actor or event details without leaking across requests."""
    token = _audit_context.set(replace(get_audit_context(), **overrides))
    try:
        yield
    finally:
        _audit_context.reset(token)
