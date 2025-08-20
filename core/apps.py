from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:  # noqa: D401
        """Sistem kontrollerini kaydet"""
        from . import checks  # noqa: F401
        return super().ready()