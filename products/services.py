"""Règles métier sur le stock, déclenchées par les événements de commande."""
import logging

from django.db import transaction

from .messaging import publish
from .models import Product

logger = logging.getLogger(__name__)


@transaction.atomic
def apply_stock_movement(items, direction):
    """
    direction = -1 : une commande est créée, on retire les quantités du stock.
    direction = +1 : une commande est annulée, on remet les quantités en stock.
    """
    for item in items:
        try:
            product = Product.objects.select_for_update().get(pk=item["product_id"])
        except Product.DoesNotExist:
            logger.warning("Produit %s introuvable, mouvement de stock ignoré", item["product_id"])
            continue
        new_stock = product.stock + direction * int(item["quantity"])
        if new_stock < 0:
            logger.error("Stock insuffisant pour %s (stock %s)", product.name, product.stock)
            new_stock = 0
        product.stock = new_stock
        product.save(update_fields=["stock", "updated_at"])
        publish("product.stock_updated", {"id": product.id, "name": product.name, "stock": product.stock})
