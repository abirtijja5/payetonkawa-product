"""Endpoints REST du service Produits."""
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .messaging import publish
from .models import Product
from .permissions import ReadOnlyOrStaff
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD du catalogue.
    - lecture publique (webshop, revendeurs)
    - création / modification / suppression : administrateurs
    - recherche : ?search=ethiopie   tri : ?ordering=price   filtre : ?in_stock=true
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [ReadOnlyOrStaff]
    search_fields = ["name", "description", "origin"]
    ordering_fields = ["name", "price", "stock", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not (self.request.user and self.request.user.is_staff):
            queryset = queryset.filter(is_active=True)  # produits retirés invisibles du public
        if self.request.query_params.get("in_stock") == "true":
            queryset = queryset.filter(stock__gt=0)
        return queryset

    def perform_create(self, serializer):
        product = serializer.save()
        publish("product.created", ProductSerializer(product).data)

    def perform_update(self, serializer):
        product = serializer.save()
        publish("product.updated", ProductSerializer(product).data)

    def perform_destroy(self, instance):
        data = {"id": instance.id, "name": instance.name}
        instance.delete()
        publish("product.deleted", data)

    @action(detail=False, methods=["get"], url_path="low-stock", permission_classes=[permissions.IsAdminUser])
    def low_stock(self, request):
        """GET /api/products/low-stock/?threshold=10 : alerte de réapprovisionnement."""
        try:
            threshold = int(request.query_params.get("threshold", 10))
        except ValueError:
            return Response({"detail": "threshold doit être un entier."}, status=400)
        products = Product.objects.filter(stock__lt=threshold)
        return Response({"threshold": threshold, "count": products.count(),
                         "products": ProductSerializer(products, many=True).data})
