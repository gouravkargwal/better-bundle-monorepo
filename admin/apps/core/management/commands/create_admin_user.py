"""
Management command to create admin user
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings


class Command(BaseCommand):
    help = 'Create admin user for BetterBundle Admin Dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Admin username (default: admin)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@betterbundle.com',
            help='Admin email (default: admin@betterbundle.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Admin password (default: admin123)'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User {username} already exists')
            )
            return

        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created admin user: {username}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Email: {email}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Password: {password}'
            )
        )
