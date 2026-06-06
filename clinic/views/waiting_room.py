from utils.base_views import *
from clinic.models import WaitingRoom
from rest_framework import status, generics
from rest_framework.response import Response
from clinic.filters import WaitingRoomFilter
from utils.mixins import BranchToSerializerMixin
from users.permissions import WaitingRoomPermission
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.waiting_room import (WaitingRoomSerializer, UpdateWaitingRoomSerializer,
                                             WaitingRoomOptionsSerializer)


#PROCEDURES API VIEWS
#List/Create waiting room API view 
@extend_schema(tags=['Waiting Room'])
class ListCreateWaitingRoomItemsAPIViews(FilterListCreateAPIView):
    serializer_class = WaitingRoomSerializer
    permission_classes = [WaitingRoomPermission]
    ordering = ['-arrivedAt']
    filterset_class = WaitingRoomFilter
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        #prepare queryset
        waiting_room = WaitingRoom.objects.select_related(
              'branch', 'appointment', 'appointment__doctor', 'appointment__patient',
            ).all()
        #filter queryset by branch 
        return self.filter_by_branch(waiting_room)


#Retrieve, update, delete procedures API view 
@extend_schema(tags=['Waiting Room'])
class UpdateDeleteWaitingRoomItemAPIViews(RetrieveUpdateDeleteAPIView):
    queryset = WaitingRoom.objects.select_related('appointment').all()
    permission_classes = [WaitingRoomPermission]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdateWaitingRoomSerializer
        return WaitingRoomSerializer
        

#View for retrieving procedure category choices
@extend_schema(
    tags=['Waiting Room'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveWaitingRoomOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    queryset = WaitingRoom.objects.all()
    serializer_class = WaitingRoomOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
