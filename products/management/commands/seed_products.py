"""python manage.py seed_products : charge un catalogue de démonstration."""
from decimal import Decimal

from django.core.management.base import BaseCommand

from products.models import Product

CATALOGUE = [
    ("Moka Sidamo", "Éthiopie", "Notes florales et agrumes, torréfaction légère.", "12.50", 40),
    ("Santos", "Brésil", "Doux, chocolaté, faible acidité.", "8.90", 120),
    ("Huehuetenango", "Guatemala", "Corsé, notes de cacao et d'épices.", "14.00", 25),
    ("Supremo", "Colombie", "Équilibré, notes de caramel.", "10.20", 60),
    ("Kilimandjaro AA", "Tanzanie", "Vif et fruité.", "15.80", 8),
]


class Command(BaseCommand):
    help = "Crée les produits de démonstration (sans doublon)."

    def handle(self, *args, **options):
        for name, origin, description, price, stock in CATALOGUE:
            _, created = Product.objects.get_or_create(
                name=name,
                defaults={"origin": origin, "description": description, "price": Decimal(price), "stock": stock},
            )
            self.stdout.write(("Créé : " if created else "Déjà présent : ") + name)
