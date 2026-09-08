from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class PermisoDist(IsAuthenticated):
    """Solo superusuarios, ADMIN y DIST pueden usar la API de distribución."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_superuser or getattr(request.user, 'rol', None) in ('ADMIN', 'DIST')

from produccion.models import Producto
from .models import Planilla, Entrega, Averia, Cliente
from .serializers import (
    PlanillaSerializer, EntregaSerializer, AveriaSerializer,
    ClienteConPreciosSerializer, ProductoSerializer,
)


class PlanillaActivaAPIView(APIView):
    permission_classes = [PermisoDist]
    """Devuelve (o crea) la planilla abierta del día para el distribuidor autenticado."""

    def get(self, request):
        planilla = Planilla.objects.filter(
            distribuidor=request.user, fecha=date.today()
        ).first()
        if not planilla:
            return Response({'detail': 'Sin planilla activa hoy.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlanillaSerializer(planilla).data)

    def post(self, request):
        planilla, created = Planilla.objects.get_or_create(
            distribuidor=request.user,
            fecha=date.today(),
            defaults={'estado': Planilla.Estado.ABIERTA},
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(PlanillaSerializer(planilla).data, status=code)


class EntregaCreateAPIView(APIView):
    permission_classes = [PermisoDist]
    """Crea una entrega. Crea Crédito automáticamente si la modalidad es Crédito."""

    def post(self, request):
        serializer = EntregaSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            entrega = serializer.save()
            return Response(EntregaSerializer(entrega).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AveriaCreateAPIView(APIView):
    permission_classes = [PermisoDist]
    def post(self, request):
        serializer = AveriaSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClienteListAPIView(APIView):
    permission_classes = [PermisoDist]
    """Lista clientes activos con sus precios — usado por el frontend de ruta."""

    def get(self, request):
        clientes = Cliente.objects.filter(activo=True)
        return Response(ClienteConPreciosSerializer(clientes, many=True).data)


class ProductoListAPIView(APIView):
    permission_classes = [PermisoDist]
    """Lista productos activos — usado por el frontend de ruta."""

    def get(self, request):
        productos = Producto.objects.filter(activo=True)
        return Response(ProductoSerializer(productos, many=True).data)
