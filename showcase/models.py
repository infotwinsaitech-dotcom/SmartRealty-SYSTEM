from django.conf import settings
from django.db import models


class ShowcaseViewer(models.Model):
    """
    Ek private login jisme sirf NUMBERS dikhte hain (lead ka naam / mobile nahi).

    - Numbers admin panel se haath se dale jaate hain (asli Lead table se koi
      connection nahi hai), isliye builder / agent panel me kahin nahi dikhte.
    - Login ID/password bhi admin panel se hi banta hai.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="showcase_viewer",
    )
    display_name = models.CharField(
        "Dikhane wala naam (optional)",
        max_length=100,
        blank=True,
        help_text="Page par 'Welcome, ...' me dikhega. Khali chhod sakte ho.",
    )
    heading = models.CharField(
        "Page heading",
        max_length=120,
        default="Leads Overview",
    )
    is_active = models.BooleanField(
        "Active",
        default=True,
        help_text="Band karoge to login karne par kuch nahi dikhega.",
    )

    # ---- Numbers (sab haath se daalne hain) ----
    total_leads = models.PositiveIntegerField("Total leads", default=0)
    new_leads = models.PositiveIntegerField("New", null=True, blank=True)
    contacted_leads = models.PositiveIntegerField("Contacted", null=True, blank=True)
    site_visit_leads = models.PositiveIntegerField("Site visit", null=True, blank=True)
    negotiation_leads = models.PositiveIntegerField("Negotiation", null=True, blank=True)
    closed_leads = models.PositiveIntegerField("Closed", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead viewer (numbers only)"
        verbose_name_plural = "Lead viewers (numbers only)"

    def __str__(self):
        return self.display_name or self.user.username

    def breakdown(self):
        """Sirf wahi cards dikhao jinme number daala gaya hai (blank = hidden)."""
        rows = [
            ("New", self.new_leads),
            ("Contacted", self.contacted_leads),
            ("Site Visit", self.site_visit_leads),
            ("Negotiation", self.negotiation_leads),
            ("Closed", self.closed_leads),
        ]
        return [(label, value) for label, value in rows if value is not None]
