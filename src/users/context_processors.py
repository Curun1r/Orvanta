from .models import OrganizationTimeFormat


def workspace_preferences(request):
    user = getattr(request, 'user', None)
    organization = getattr(user, 'organization', None) if getattr(user, 'is_authenticated', False) else None
    preference = getattr(organization, 'time_format', OrganizationTimeFormat.TWENTY_FOUR_HOUR)
    return {
        'workspace_time_format': preference,
        'workspace_hour12': preference == OrganizationTimeFormat.TWELVE_HOUR,
    }
