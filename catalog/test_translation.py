from django.utils import translation

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category


class TranslationTestCase(APITestCase):
    def setUp(self):
        translation.activate("ru")
        self.addCleanup(translation.deactivate)
        self.category = Category.objects.create(name="Уход за лицом")
        self.category.name_ky = "Бетти кам көрүү"
        self.category.name_en = "Face care"
        self.category.description = "Кремы, сыворотки, маски"
        self.category.save()

    def test_default_language_is_ru(self):
        resp = self.client.get("/api/categories/")
        root = next(c for c in resp.data["results"] if c["id"] == self.category.id)
        self.assertEqual(root["name"], "Уход за лицом")

    def test_accept_language_ky(self):
        resp = self.client.get("/api/categories/", HTTP_ACCEPT_LANGUAGE="ky")
        root = next(c for c in resp.data["results"] if c["id"] == self.category.id)
        self.assertEqual(root["name"], "Бетти кам көрүү")

    def test_accept_language_en(self):
        resp = self.client.get("/api/categories/", HTTP_ACCEPT_LANGUAGE="en")
        root = next(c for c in resp.data["results"] if c["id"] == self.category.id)
        self.assertEqual(root["name"], "Face care")

    def test_fallback_to_ru_when_empty(self):
        other = Category.objects.create(name="Макияж")
        with translation.override("ky"):
            self.assertEqual(other.name, "Макияж")

    def test_detail_endpoint_respects_language(self):
        resp = self.client.get(f"/api/categories/{self.category.slug}/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Face care")
