"""Django application configuration for application log access."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SiteLogsConfig(AppConfig):
    """Configure application logging when Django initializes the app."""

    name = "site_logs"
    verbose_name = _("Site logs")

    def ready(self) -> None:
        from site_logs.logging import configure_loguru

        configure_loguru()
