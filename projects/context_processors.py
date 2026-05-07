from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import CompanyProfile


def firm_config(request):
    profile = None
    try:
        profile = CompanyProfile.objects.first()
    except (OperationalError, ProgrammingError):
        # Pre-migrate boot: table doesn't exist yet. Templates fall back to repo defaults.
        pass
    return {
        'firm': getattr(settings, 'FIRM_CONFIG', {}) or {},
        'company_profile': profile,
    }
