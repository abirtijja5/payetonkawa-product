# PayeTonKawa – API Produits

Micro-service de catalogue des cafés et gestion des stocks. Django 5.2 + Django REST Framework, base PostgreSQL dédiée (SQLite en développement).

## Lancer seul (développement)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8002
```

Documentation interactive : http://localhost:8002/api/docs/ (via la passerelle : http://localhost:8080/product/api/docs/)

La plateforme complète (3 services, RabbitMQ, PostgreSQL, passerelle, supervision) se lance depuis le dépôt **payetonkawa-infra**.

## Endpoints

| Méthode | URL | Accès |
|---|---|---|
| GET | `/api/products/` (`?search=`, `?ordering=price`, `?in_stock=true`) · `/api/products/{id}/` | public |
| POST, PUT, PATCH, DELETE | `/api/products/`, `/api/products/{id}/` | admin |
| GET | `/api/products/low-stock/?threshold=10` | admin |

Authentification : en-tête `Authorization: Bearer <jeton>` (jeton obtenu sur le service Clients).

## Événements RabbitMQ

Publie `product.created/updated/deleted/stock_updated`. Écoute `order.created` (retire du stock) et `order.cancelled` (remet en stock).

## Tests

```bash
python manage.py test                       # tests unitaires et d'intégration
coverage run manage.py test && coverage report
flake8 .
```

## Commandes utiles

`python manage.py import_erp` : reprise du catalogue de l'ancien ERP. `python manage.py seed_products` : catalogue de démonstration.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` | sécurité Django |
| `JWT_SIGNING_KEY` | clé partagée de signature des jetons |
| `DB_ENGINE=postgres`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | base de données |
| `RABBITMQ_ENABLED`, `RABBITMQ_HOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | message broker |
| `URL_PREFIX` | préfixe derrière la passerelle (`/product`) |
