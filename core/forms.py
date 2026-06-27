"""
core/forms.py — Custom Social Signup Form
FIXED v4: Bulletproof version - handles all edge cases
"""

from django import forms
from django.contrib.auth import get_user_model
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
import re

User = get_user_model()


class CustomSocialSignupForm(SocialSignupForm):
    """
    Custom social signup form with auto username from email.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Auto-fill username from email
        email = self.initial.get('email', '')
        if email and not self.initial.get('username'):
            username = self._generate_username_from_email(email)
            self.initial['username'] = username
            # Set the actual field value too
            if 'username' in self.fields:
                self.fields['username'].initial = username

        # Style fields
        if 'username' in self.fields:
            self.fields['username'].widget.attrs.update({
                'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none',
                'placeholder': 'Choose a username',
            })

        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({
                'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white opacity-50 cursor-not-allowed',
                'readonly': 'readonly',
            })
            self.fields['email'].required = False

    def _generate_username_from_email(self, email):
        if not email or '@' not in email:
            return ''
        prefix = email.split('@')[0]
        username = re.sub(r'[^a-zA-Z0-9_.+-]', '', prefix)
        username = username.lstrip('_.+-')[:30]
        if not username:
            return ''
        base = username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            suffix = str(counter)
            username = base[:30 - len(suffix)] + suffix
            counter += 1
            if counter > 999:
                break
        return username

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def save(self, request):
        user = super().save(request)
        if not getattr(user, 'role', None):
            user.role = 'user'
            user.save(update_fields=['role'])
        return user


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': 'Full Name',
        'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Email Address',
        'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none'
    }))
    phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={
        'placeholder': 'Phone Number',
        'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none'
    }))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'placeholder': 'Username',
        'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Password',
        'class': 'w-full p-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-400 outline-none'
    }))