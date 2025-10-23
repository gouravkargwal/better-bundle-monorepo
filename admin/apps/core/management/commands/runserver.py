"""
Management command to run server with environment-based configuration
"""

from django.core.management.base import BaseCommand
from django.core.management.commands.runserver import Command as RunserverCommand
from django.conf import settings


class Command(RunserverCommand):
    help = "Run development server with environment-based port configuration"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--port",
            type=int,
            default=getattr(settings, "PORT", 8000),
            help="Port to run the server on (default: from settings)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default=getattr(settings, "HOST", "127.0.0.1"),
            help="Host to run the server on (default: from settings)",
        )

    def handle(self, *args, **options):
        # Override with environment settings if not provided
        if not options.get("addrport"):
            port = options.get("port") or getattr(settings, "PORT", 8000)
            host = options.get("host") or getattr(settings, "HOST", "127.0.0.1")
            options["addrport"] = f"{host}:{port}"

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting BetterBundle Admin Dashboard on {options["addrport"]}'
            )
        )

        super().handle(*args, **options)
