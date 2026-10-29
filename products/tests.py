"""Tests unitaires et d'intégration du service Produits."""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import CommandError, call_command

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from . import messaging
from .events import HANDLERS
from .models import Product


def jwt_for(user_id, is_staff=False):
    """Fabrique un jeton identique à ceux émis par le service Clients."""
    token = AccessToken()
    token["user_id"] = user_id
    token["is_staff"] = is_staff
    return str(token)


@patch("products.views.publish")
class ProductApiTests(APITestCase):
    def setUp(self):
        self.ethiopie = Product.objects.create(name="Moka Sidamo", origin="Éthiopie", price=Decimal("12.50"), stock=40)
        self.bresil = Product.objects.create(name="Santos", origin="Brésil", price=Decimal("8.90"), stock=0)
        self.list_url = reverse("product-list")

    def as_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for('admin-id', is_staff=True)}")

    def as_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_for('client-id')}")

    def test_catalogue_public(self, mock_publish):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_recherche_tri_et_filtre(self, mock_publish):
        self.assertEqual(len(self.client.get(self.list_url, {"search": "sidamo"}).data), 1)
        prices = [p["price"] for p in self.client.get(self.list_url, {"ordering": "price"}).data]
        self.assertEqual(prices, ["8.90", "12.50"])
        self.assertEqual(len(self.client.get(self.list_url, {"in_stock": "true"}).data), 1)

    def test_detail(self, mock_publish):
        response = self.client.get(reverse("product-detail", kwargs={"pk": self.ethiopie.pk}))
        self.assertEqual(response.data["name"], "Moka Sidamo")

    def test_produit_inexistant(self, mock_publish):
        self.assertEqual(self.client.get(reverse("product-detail", kwargs={"pk": 999})).status_code, 404)

    def test_creation_interdite_sans_jeton(self, mock_publish):
        response = self.client.post(self.list_url, {"name": "X", "price": "5.00"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creation_interdite_a_un_client(self, mock_publish):
        self.as_customer()
        response = self.client.post(self.list_url, {"name": "X", "price": "5.00"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_jeton_invalide(self, mock_publish):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer faux.jeton.jwt")
        response = self.client.post(self.list_url, {"name": "X", "price": "5.00"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creation_par_admin(self, mock_publish):
        self.as_admin()
        data = {"name": "Huehuetenango", "origin": "Guatemala", "price": "14.00", "stock": 25}
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(mock_publish.call_args[0][0], "product.created")

    def test_validation_prix_et_stock(self, mock_publish):
        self.as_admin()
        response = self.client.post(self.list_url, {"name": "X", "price": "0", "stock": -3}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)
        self.assertIn("stock", response.data)

    def test_nom_unique(self, mock_publish):
        self.as_admin()
        response = self.client.post(self.list_url, {"name": "Santos", "price": "5"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modification(self, mock_publish):
        self.as_admin()
        url = reverse("product-detail", kwargs={"pk": self.bresil.pk})
        response = self.client.patch(url, {"stock": 100}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.bresil.refresh_from_db()
        self.assertEqual(self.bresil.stock, 100)
        self.assertEqual(mock_publish.call_args[0][0], "product.updated")

    def test_suppression(self, mock_publish):
        self.as_admin()
        response = self.client.delete(reverse("product-detail", kwargs={"pk": self.bresil.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(mock_publish.call_args[0][0], "product.deleted")

    def test_produit_desactive_invisible_du_public(self, mock_publish):
        Product.objects.filter(pk=self.bresil.pk).update(is_active=False)
        self.assertEqual(len(self.client.get(self.list_url).data), 1)
        self.as_admin()
        self.assertEqual(len(self.client.get(self.list_url).data), 2)

    def test_stock_faible(self, mock_publish):
        self.as_admin()
        response = self.client.get(reverse("product-low-stock"), {"threshold": 10})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self.client.get(reverse("product-low-stock"), {"threshold": "abc"}).status_code, 400)

    def test_stock_faible_reserve_aux_admins(self, mock_publish):
        self.as_customer()
        self.assertEqual(self.client.get(reverse("product-low-stock")).status_code, 403)


@patch("products.services.publish")
class StockEventTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(name="Moka", price=Decimal("10"), stock=10)

    def test_commande_creee_decremente_le_stock(self, mock_publish):
        HANDLERS["order.created"]({"items": [{"product_id": self.product.id, "quantity": 3}]})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)
        self.assertEqual(mock_publish.call_args[0][0], "product.stock_updated")

    def test_commande_annulee_remet_en_stock(self, mock_publish):
        HANDLERS["order.cancelled"]({"items": [{"product_id": self.product.id, "quantity": 5}]})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

    def test_stock_jamais_negatif(self, mock_publish):
        HANDLERS["order.created"]({"items": [{"product_id": self.product.id, "quantity": 50}]})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_produit_inconnu_ignore(self, mock_publish):
        HANDLERS["order.created"]({"items": [{"product_id": 999, "quantity": 1}]})
        mock_publish.assert_not_called()


RABBIT_ON = {"ENABLED": True, "HOST": "x", "PORT": 1, "USER": "g", "PASSWORD": "g", "EXCHANGE": "e"}


class MessagingTests(APITestCase):
    """Publication RabbitMQ : activée, désactivée, et en panne (tolérance aux pannes)."""

    @override_settings(RABBITMQ={"ENABLED": False})
    def test_publication_desactivee(self):
        self.assertFalse(messaging.publish("test.event", {"id": 1}))
        self.assertIsNone(messaging.start_consumer("q", {"a": print}))

    @override_settings(RABBITMQ=RABBIT_ON)
    @patch("products.messaging._connection", side_effect=ConnectionError("RabbitMQ en panne"))
    def test_rabbitmq_en_panne_ne_bloque_pas(self, _):
        with self.assertLogs("products.messaging", level="ERROR"):
            self.assertFalse(messaging.publish("test.event", {"id": 1}))

    @override_settings(RABBITMQ=RABBIT_ON)
    @patch("products.messaging._connection")
    def test_publication_ok(self, mock_connection):
        self.assertTrue(messaging.publish("test.event", {"id": 1}))
        channel = mock_connection.return_value.channel.return_value
        body = channel.basic_publish.call_args.kwargs["body"]
        self.assertIn('"type": "test.event"', body)

    @override_settings(RABBITMQ=RABBIT_ON)
    @patch("products.messaging.threading.Thread")
    def test_demarrage_du_consommateur(self, mock_thread):
        messaging.start_consumer("q", {"a.b": print})
        mock_thread.return_value.start.assert_called_once()

    @override_settings(RABBITMQ=RABBIT_ON)
    @patch("products.messaging._connection")
    def test_consommateur_traite_et_acquitte(self, mock_connection):
        channel = mock_connection.return_value.channel.return_value
        received = []

        def fake_consume():
            on_message = channel.basic_consume.call_args.kwargs["on_message_callback"]
            method = type("M", (), {"routing_key": "a.b", "delivery_tag": 1})()
            on_message(channel, method, None, b'{"data": {"x": 1}}')
            on_message(channel, method, None, b"pas du json")
            raise KeyboardInterrupt  # sort de la boucle infinie pour le test

        channel.start_consuming.side_effect = fake_consume
        with self.assertRaises(KeyboardInterrupt), self.assertLogs("products.messaging", level="ERROR"):
            messaging._consume_forever("q", {"a.b": received.append})
        self.assertEqual(received, [{"x": 1}])
        channel.basic_ack.assert_called_once_with(delivery_tag=1)
        channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)


class ImportErpTests(APITestCase):
    """Reprise du catalogue de l'ancien ERP (API mockée simulée)."""

    ERP_DATA = [
        {"id": "1", "name": "Rustic Frozen Pants", "details": {"price": "743.00", "description": "Arabica"},
         "stock": 12},
        {"id": "2", "name": "Moka Sidamo", "details": {"price": "pas-un-prix"}, "stock": -4},
        {"id": "3", "name": ""},
    ]

    @patch("products.management.commands.import_erp.requests.get")
    def test_import(self, mock_get):
        Product.objects.create(name="Moka Sidamo", price=Decimal("10"), stock=5)
        mock_get.return_value.json.return_value = self.ERP_DATA
        out = StringIO()
        call_command("import_erp", stdout=out)
        self.assertIn("1 produit(s) créé(s), 1 mis à jour", out.getvalue())
        self.assertEqual(Product.objects.get(name="Rustic Frozen Pants").price, Decimal("743.00"))
        moka = Product.objects.get(name="Moka Sidamo")
        self.assertEqual((moka.price, moka.stock), (Decimal("0"), 0))

    @patch("products.management.commands.import_erp.requests.get", side_effect=requests.Timeout())
    def test_erp_injoignable(self, _):
        with self.assertRaises(CommandError):
            call_command("import_erp", stdout=StringIO())

    def test_seed_products_idempotent(self):
        call_command("seed_products", stdout=StringIO())
        call_command("seed_products", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 5)
        self.assertEqual(str(Product.objects.get(name="Santos")), "Santos")
