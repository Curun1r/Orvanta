from django.utils.translation import gettext as _
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .context import get_audit_context
from .models import AuditActionType, AuditEntityType, AuditLog

# Заповнюється у AuditConfig.ready() після того, як усі додатки готові.
_TRACKED_MODELS: dict = {}


def get_instance_organization(instance):
    organization = getattr(instance, 'organization', None)
    return organization if organization else None


def get_user_organization(user):
    if user is None:
        return None
    organization = getattr(user, 'organization', None)
    return organization if organization else None


def get_client_ip(request):
    if request is None:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        user=user,
        organization=get_user_organization(user),
        action_type=AuditActionType.LOGIN,
        entity_type=AuditEntityType.AUTH,
        entity_id=user.id,
        description=_('User %(username)s signed in.') % {'username': user.username},
        ip_address=get_client_ip(request),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user is None:
        return
    AuditLog.objects.create(
        user=user,
        organization=get_user_organization(user),
        action_type=AuditActionType.LOGOUT,
        entity_type=AuditEntityType.AUTH,
        entity_id=user.id,
        description=_('User %(username)s signed out.') % {'username': user.username},
        ip_address=get_client_ip(request),
    )


def get_acting_user(using):
    context = get_audit_context()
    # Read request.user at the time of the event: login/logout can replace it.
    user = context.user if context.user is not None else getattr(context.request, 'user', None)
    if user is None or not user.is_authenticated or user.pk is None:
        return None
    # Deletion signals may run after the actor's own account was deleted.
    if not user._meta.model.objects.using(using).filter(pk=user.pk).exists():
        return None
    return user


def log_model_save(sender, instance, created, using, raw=False, **kwargs):
    if raw:
        return
    entity_type = _TRACKED_MODELS[sender]
    if created:
        action_type = AuditActionType.CREATE
        description = _('Created %(entity)s with id=%(id)s.') % {'entity': instance._meta.verbose_name, 'id': instance.pk}
    else:
        action_type = AuditActionType.UPDATE
        description = _('Updated %(entity)s with id=%(id)s.') % {'entity': instance._meta.verbose_name, 'id': instance.pk}

    acting_user = get_acting_user(using)

    AuditLog.objects.using(using).create(
        user=acting_user,
        organization=get_instance_organization(instance),
        action_type=action_type,
        entity_type=entity_type,
        entity_id=instance.pk,
        description=description,
    )


def log_model_delete(sender, instance, using, **kwargs):
    entity_type = _TRACKED_MODELS[sender]

    if entity_type == AuditEntityType.USER:
        # Logs written during a bulk deletion were not in Django's initial
        # SET_NULL collection. Clear those references too, including self-delete.
        AuditLog.objects.using(using).filter(user_id=instance.pk).update(user=None)
    acting_user = get_acting_user(using)
    description = get_audit_context().description or (
        _('Deleted %(entity)s with id=%(id)s.') % {'entity': instance._meta.verbose_name, 'id': instance.pk}
    )
    request = get_audit_context().request

    AuditLog.objects.using(using).create(
        user=acting_user,
        organization=get_instance_organization(instance),
        action_type=AuditActionType.DELETE,
        entity_type=entity_type,
        entity_id=instance.pk,
        description=description,
        ip_address=request.META.get('REMOTE_ADDR') if request is not None else None,
    )
