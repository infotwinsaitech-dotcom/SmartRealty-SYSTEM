"""
core/adapters.py — Custom Social Account Adapter
Handles Google OAuth user creation with auto-populated fields.
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_email
from django.contrib.auth import get_user_model
import re

User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for social login that:
    1. Auto-populates username from email
    2. Sets default role to 'user'
    3. Prevents duplicate email conflicts
    """

    def populate_user(self, request, sociallogin, data):
        """
        Populate user fields from social account data.
        Called before the signup form is shown.
        """
        user = super().populate_user(request, sociallogin, data)

        email = data.get('email', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')

        # Auto-generate username from email if not set
        if not user.username and email:
            username = self._generate_username_from_email(email)
            user.username = username

        # Set full name if available
        if first_name or last_name:
            full_name = f"{first_name} {last_name}".strip()
            # Will be saved to Profile in signals.py
            user.first_name = first_name
            user.last_name = last_name

        # Set default role
        user.role = 'user'

        return user

    def _generate_username_from_email(self, email):
        """Extract clean username from email prefix."""
        if not email or '@' not in email:
            return ''

        prefix = email.split('@')[0]
        username = re.sub(r'[^a-zA-Z0-9_.+-]', '', prefix)
        username = username.lstrip('_.+-')
        username = username[:30]

        if not username:
            return ''

        # Handle duplicates
        base_username = username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            suffix = str(counter)
            username = base_username[:30 - len(suffix)] + suffix
            counter += 1
            if counter > 999:
                break

        return username

    def is_open_for_signup(self, request, sociallogin):
        """Allow social signup."""
        return True

    def save_user(self, request, sociallogin, form=None):
        """Save user after social signup."""
        user = super().save_user(request, sociallogin, form)

        # Ensure role is set
        if not user.role:
            user.role = 'user'
            user.save(update_fields=['role'])

        return user