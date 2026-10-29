"""Modèle de données du service Produits."""
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    """Un café vendu par PayeTonKawa."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    origin = models.CharField("pays d'origine", max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
