from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create (or update) a Manager login.  Usage: python manage.py create_manager <username> <password> [--email x@y.com]"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument("--email", default="")

    def handle(self, *args, **opts):
        User = get_user_model()
        username, password = opts["username"], opts["password"]
        if len(password) < 8:
            raise CommandError("Password kam se kam 8 characters ka rakho.")
        user, created = User.objects.get_or_create(
            username=username, defaults={"email": opts["email"]}
        )
        user.role = "manager"
        user.is_active = True
        user.set_password(password)
        if opts["email"]:
            user.email = opts["email"]
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Manager '{username}' {'created' if created else 'updated'}. Login: /login/"))