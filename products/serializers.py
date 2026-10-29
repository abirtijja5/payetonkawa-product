from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "origin", "price", "stock", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le prix doit être supérieur à 0.")
        return value
