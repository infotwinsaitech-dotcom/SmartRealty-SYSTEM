from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_email, user_username
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    
    def is_auto_signup_allowed(self, request, sociallogin):
        # Always allow auto signup
        return True
    
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        
        # Extract data from Google
        email = data.get('email', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        # Generate username from email if not provided
        if not user_username(user) and email:
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user_username(user, username)
        
        # Set email
        if email:
            user_email(user, email)
            
        # Set name fields
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
            
        # Set default role
        user.role = 'user'
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        
        # Create profile
        from core.models import Profile
        Profile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'email': user.email,
                'phone': getattr(user, 'phone', '') or ''
            }
        )
        
        return user