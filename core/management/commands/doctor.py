from __future__ import annotations

from django.core import checks
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Proje sağlığını kontrol eder (güvenlik, ödeme, SMTP, URL, statik, vb.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-level",
            default="ERROR",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Belirtilen düzeyde sorun bulunursa non-zero çıkış yapar (default: ERROR).",
        )

    def handle(self, *args, **options):
        level_order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        fail_level = level_order[options["fail_level"]]
        messages = checks.run_checks()

        if not messages:
            self.stdout.write(self.style.SUCCESS("✓ Her şey yolunda."))
            return

        worst_level = 0
        self.stdout.write("— Sistem Kontrolleri —")
        for m in messages:
            worst_level = max(worst_level, m.level)
            prefix = {
                checks.DEBUG: "[DEBUG] ",
                checks.INFO: "[INFO] ",
                checks.WARNING: "[WARN] ",
                checks.ERROR: "[ERROR]",
                checks.CRITICAL: "[CRIT] ",
            }.get(m.level, "")
            self.stdout.write(f"{prefix} {m.id}: {m.msg}")
            if m.hint:
                self.stdout.write(f"    ↳ {m.hint}")

        if worst_level >= fail_level:
            raise SystemExit(1)