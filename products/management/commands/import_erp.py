"""
python manage.py import_erp
Reprise du catalogue de l'ancien ERP (API REST mockée fournie par PayeTonKawa).
"""
import os
from decimal import Decimal, InvalidOperation

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Product

DEFAULT_URL = "https://615f5fb4f7254d0017068109.mockapi.io/api/v1"


def map_product(raw):
    """Transforme un produit de l'ancien ERP vers le nouveau modèle."""
    details = raw.get("details") or {}
    try:
        price = Decimal(str(details.get("price", raw.get("price", "0"))))
    except InvalidOperation:
        price = Decimal("0")
    return {
        "description": details.get("description", ""),
        "price": price,
        "stock": max(int(raw.get("stock") or 0), 0),
    }


class Command(BaseCommand):
    help = "Importe les produits de l'ancien ERP (sans doublon, par nom)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default=os.environ.get("ERP_API_URL", DEFAULT_URL))

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            response = requests.get(f"{options['url']}/products", timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"ERP injoignable : {exc}")

        created = updated = 0
        for raw in response.json():
            name = (raw.get("name") or "").strip()[:150]
            if not name:
                continue
            _, is_new = Product.objects.update_or_create(name=name, defaults=map_product(raw))
            created += is_new
            updated += not is_new
        self.stdout.write(self.style.SUCCESS(f"{created} produit(s) créé(s), {updated} mis à jour."))
