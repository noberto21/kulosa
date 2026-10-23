from django.test import TestCase
from django.urls import reverse


class AboutPageTests(TestCase):
    def test_about_page_renders_full_brand_sections(self):
        response = self.client.get(reverse("core:about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kenya’s event hub")
        self.assertContains(response, "What we do")
        self.assertContains(response, "Our mission")


class CoreViewsTests(TestCase):
    def test_terms_page_renders_successfully(self):
        url = reverse("core:terms")
        self.assertEqual(url, "/terms/")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/terms.html")
        self.assertContains(response, "Terms of Use")
        self.assertContains(response, "Republic of Kenya")
        self.assertContains(response, "Event Discovery")
        self.assertContains(response, "support@kulosa.co.ke")
        self.assertNotContains(response, "isn't available yet")

    def test_terms_in_sitemap(self):
        response = self.client.get(reverse("sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/terms/")

    def test_footer_contains_terms_link(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/terms/"')

    def test_privacy_page_renders_successfully(self):
        url = reverse("core:privacy")
        self.assertEqual(url, "/privacy/")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/privacy.html")
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "Data Protection Act, 2019")
        self.assertContains(response, "ODPC")
        self.assertContains(response, "Office of the Data Protection Commissioner")
        self.assertContains(response, "privacy@kulosa.co.ke")
        self.assertNotContains(response, "isn't available yet")

    def test_privacy_in_sitemap(self):
        response = self.client.get(reverse("sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/privacy/")

    def test_footer_contains_privacy_link(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/privacy/"')
