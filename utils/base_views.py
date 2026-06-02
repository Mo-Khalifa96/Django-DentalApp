from rest_framework import generics
from utils.mixins import ResponseMixin, FilterByBranchMixin


__all__ = [
    'GenericAPIView',
    'CreateAPIView',
    'ListAPIView',
    'ListCreateAPIView',
    'FilterListAPIView',
    'FilterListCreateAPIView',
    'RetrieveAPIView',
    'UpdateAPIView',
    'DeleteAPIView',
    'RetrieveUpdateAPIView',
    'RetrieveUpdateDeleteAPIView',
]


class GenericAPIView(ResponseMixin, generics.GenericAPIView):
    pass

class CreateAPIView(ResponseMixin, generics.CreateAPIView):
    pass

class ListAPIView(ResponseMixin, generics.ListAPIView):
    pass

class ListCreateAPIView(ResponseMixin, generics.ListCreateAPIView):
    pass 

class FilterListAPIView(FilterByBranchMixin, ResponseMixin, generics.ListAPIView):
    pass 

class FilterListCreateAPIView(FilterByBranchMixin, ResponseMixin, generics.ListCreateAPIView):
    pass 

class RetrieveAPIView(ResponseMixin, generics.RetrieveAPIView):
    pass

class UpdateAPIView(ResponseMixin, generics.UpdateAPIView):
    pass

class DeleteAPIView(ResponseMixin, generics.DestroyAPIView):
    pass

class RetrieveUpdateAPIView(ResponseMixin, generics.RetrieveUpdateAPIView):
    pass

class RetrieveUpdateDeleteAPIView(ResponseMixin, generics.RetrieveUpdateDestroyAPIView):
    pass 
