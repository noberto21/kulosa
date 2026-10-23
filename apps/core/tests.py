from django.test import TestCase
from django.urls import reverse


class AboutPageTests(TestCase):
    def test_about_page_renders_full_brand_sections(self):
        response = self.client.get(reverse("core:about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kenya’s event hub")
        self.assertContains(response, "What we do")
        self.assertContains(response, "Our mission")
