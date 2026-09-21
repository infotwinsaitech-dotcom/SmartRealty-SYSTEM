from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client, RequestFactory, override_settings
from django.urls import reverse

from core.models import Lead
from .admin import ShowcaseViewerAdmin, ShowcaseViewerAdminForm
from .models import ShowcaseViewer

User = get_user_model()


def make_viewer(username="viewer1", password="Pass@1234", **kwargs):
    user = User.objects.create_user(username=username, password=password, role="user")
    data = dict(total_leads=250, new_leads=40, contacted_leads=None)
    data.update(kwargs)
    return ShowcaseViewer.objects.create(user=user, **data)


@override_settings(SECURE_SSL_REDIRECT=False)
class ShowcaseViewerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_login_redirects_viewer_to_numbers_page(self):
        make_viewer()
        resp = self.client.post("/login/", {"username": "viewer1", "password": "Pass@1234"})
        self.assertRedirects(resp, reverse("showcase:dashboard"), fetch_redirect_response=False)

    def test_page_shows_only_manual_numbers_not_real_lead_data(self):
        make_viewer()
        # Asli lead DB me hai -> page par kabhi nahi aani chahiye
        Lead.objects.create(name="SecretPerson", email="s@x.com", phone="9876543210")
        self.client.login(username="viewer1", password="Pass@1234")
        resp = self.client.get(reverse("showcase:dashboard"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-count="250"', html)   # haath se daala hua total
        self.assertIn('data-count="40"', html)    # New
        self.assertNotIn("Contacted", html)       # blank = card hidden
        self.assertNotIn("SecretPerson", html)
        self.assertNotIn("9876543210", html)
        self.assertEqual(resp["X-Robots-Tag"], "noindex, nofollow")

    def test_number_is_manual_not_actual_count(self):
        make_viewer(total_leads=9999)
        self.assertEqual(Lead.objects.count(), 0)
        self.client.login(username="viewer1", password="Pass@1234")
        html = self.client.get(reverse("showcase:dashboard")).content.decode()
        self.assertIn('data-count="9999"', html)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("showcase:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_other_roles_get_404(self):
        make_viewer()
        for role in ("builder", "agent", "user", "admin"):
            User.objects.create_user(username=f"u_{role}", password="Pass@1234", role=role)
            c = Client()
            c.login(username=f"u_{role}", password="Pass@1234")
            self.assertEqual(c.get(reverse("showcase:dashboard")).status_code, 404, role)
        su = User.objects.create_superuser("root", "r@x.com", "Pass@1234")
        c = Client(); c.force_login(su)
        self.assertEqual(c.get(reverse("showcase:dashboard")).status_code, 404)

    def test_inactive_viewer_sees_nothing(self):
        make_viewer(is_active=False)
        self.client.login(username="viewer1", password="Pass@1234")
        self.assertEqual(self.client.get(reverse("showcase:dashboard")).status_code, 404)

    def test_viewer_cannot_open_builder_or_agent_panel(self):
        make_viewer()
        self.client.login(username="viewer1", password="Pass@1234")
        for url in ("/builder/dashboard/", "/builder/leads/", "/agent/dashboard/", "/agent/leads/"):
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, 200, url)

    def test_viewers_are_isolated(self):
        make_viewer("v1", total_leads=111)
        make_viewer("v2", total_leads=222)
        self.client.login(username="v1", password="Pass@1234")
        html = self.client.get(reverse("showcase:dashboard")).content.decode()
        self.assertIn('data-count="111"', html)
        self.assertNotIn('data-count="222"', html)


@override_settings(SECURE_SSL_REDIRECT=False)
class ShowcaseAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("root", "r@x.com", "Pass@1234")
        self.site = AdminSite()
        self.model_admin = ShowcaseViewerAdmin(ShowcaseViewer, self.site)

    def _form(self, data, instance=None):
        base = dict(heading="Leads Overview", is_active="on", total_leads=100)
        base.update(data)
        return ShowcaseViewerAdminForm(base, instance=instance)

    def test_admin_creates_login_and_numbers(self):
        form = self._form({"username": "client1", "password": "Secret@99", "total_leads": 321})
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        req = RequestFactory().post("/")
        req.user = self.admin_user
        self.model_admin.save_model(req, obj, form, change=False)
        user = User.objects.get(username="client1")
        self.assertTrue(user.check_password("Secret@99"))
        self.assertEqual((user.role, user.is_staff, user.is_superuser), ("user", False, False))
        self.assertEqual(user.showcase_viewer.total_leads, 321)

        # Client se login -> seedha numbers page
        c = Client()
        resp = c.post("/login/", {"username": "client1", "password": "Secret@99"})
        self.assertRedirects(resp, reverse("showcase:dashboard"), fetch_redirect_response=False)
        self.assertIn('data-count="321"', c.get(reverse("showcase:dashboard")).content.decode())

    def test_password_required_on_create_optional_on_edit(self):
        self.assertFalse(self._form({"username": "abc", "password": ""}).is_valid())
        viewer = make_viewer("keepme", password="Old@1234")
        form = self._form({"username": "keepme", "password": "", "total_leads": 5}, instance=viewer)
        self.assertTrue(form.is_valid(), form.errors)
        req = RequestFactory().post("/"); req.user = self.admin_user
        self.model_admin.save_model(req, form.save(commit=False), form, change=True)
        viewer.user.refresh_from_db()
        self.assertTrue(viewer.user.check_password("Old@1234"))  # password same
        viewer.refresh_from_db()
        self.assertEqual(viewer.total_leads, 5)

    def test_duplicate_username_rejected(self):
        make_viewer("taken")
        self.assertFalse(self._form({"username": "TAKEN", "password": "Secret@99"}).is_valid())

    def test_deleting_viewer_removes_login(self):
        viewer = make_viewer("gone")
        req = RequestFactory().post("/"); req.user = self.admin_user
        self.model_admin.delete_model(req, viewer)
        self.assertFalse(User.objects.filter(username="gone").exists())

    def test_admin_pages_render(self):
        make_viewer()
        c = Client(); c.force_login(self.admin_user)
        for url in ("/admin/showcase/showcaseviewer/", "/admin/showcase/showcaseviewer/add/"):
            self.assertEqual(c.get(url).status_code, 200, url)
        pk = ShowcaseViewer.objects.first().pk
        self.assertEqual(c.get(f"/admin/showcase/showcaseviewer/{pk}/change/").status_code, 200)
