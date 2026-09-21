from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import ShowcaseViewer

User = get_user_model()


class ShowcaseViewerAdminForm(forms.ModelForm):
    """Login ID + password isi form se banta hai (alag se User banane ki zaroorat nahi)."""

    username = forms.CharField(
        label="Login ID (username)",
        max_length=150,
        help_text="Isi ID se login karoge.",
    )
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Naya viewer banate waqt zaroori hai. Edit karte waqt khali chhodo to purana password hi rahega.",
    )

    class Meta:
        model = ShowcaseViewer
        exclude = ("user",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["username"].initial = self.instance.user.username

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("Ye ID pehle se use me hai, doosri ID daalo.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        is_new = not (self.instance and self.instance.pk)
        if is_new and not password:
            self.add_error("password", "Naye viewer ke liye password daalna zaroori hai.")
        if password and len(password) < 6:
            self.add_error("password", "Password kam se kam 6 characters ka rakho.")
        return cleaned


@admin.register(ShowcaseViewer)
class ShowcaseViewerAdmin(admin.ModelAdmin):
    form = ShowcaseViewerAdminForm

    list_display = (
        "login_id",
        "display_name",
        "total_leads",
        "new_leads",
        "contacted_leads",
        "site_visit_leads",
        "negotiation_leads",
        "closed_leads",
        "is_active",
        "updated_at",
    )
    list_display_links = ("login_id",)
    # List page se hi numbers seedha badal sakte ho
    list_editable = (
        "total_leads",
        "new_leads",
        "contacted_leads",
        "site_visit_leads",
        "negotiation_leads",
        "closed_leads",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Login (ID & Password)", {"fields": ("username", "password")}),
        ("Page settings", {"fields": ("display_name", "heading", "is_active")}),
        (
            "Lead numbers (jo yahan daaloge wahi dikhega)",
            {
                "fields": (
                    "total_leads",
                    "new_leads",
                    "contacted_leads",
                    "site_visit_leads",
                    "negotiation_leads",
                    "closed_leads",
                ),
                "description": "Breakdown wale number khali chhodoge to page par woh card dikhega hi nahi.",
            },
        ),
        ("Info", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Login ID", ordering="user__username")
    def login_id(self, obj):
        return obj.user.username

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def save_model(self, request, obj, form, change):
        username = form.cleaned_data["username"]
        password = form.cleaned_data.get("password")

        if change:
            user = obj.user
            user.username = username
            if password:
                user.set_password(password)
            user.save()
        else:
            # role="user" + no staff/superuser => builder/agent/admin panel ka access nahi
            user = User(username=username, role="user", is_staff=False, is_superuser=False)
            user.set_password(password)
            user.save()
            obj.user = user
        super().save_model(request, obj, form, change)

    # Viewer delete karne par uska login bhi hata do (koi bekaar login na bache)
    def _delete_login(self, viewer):
        user = viewer.user
        if not user.is_staff and not user.is_superuser and user.role == "user":
            user.delete()  # ShowcaseViewer cascade se hat jaata hai
        else:
            viewer.delete()

    def delete_model(self, request, obj):
        self._delete_login(obj)

    def delete_queryset(self, request, queryset):
        for viewer in queryset.select_related("user"):
            self._delete_login(viewer)
