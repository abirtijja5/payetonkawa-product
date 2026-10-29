"""Événements RabbitMQ écoutés par le service Produits."""
from .services import apply_stock_movement


def on_order_created(data):
    apply_stock_movement(data.get("items", []), direction=-1)


def on_order_cancelled(data):
    apply_stock_movement(data.get("items", []), direction=+1)


HANDLERS = {
    "order.created": on_order_created,
    "order.cancelled": on_order_cancelled,
}
