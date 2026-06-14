from rest_framework import generics
from utils.mixins import ResponseMixin, FilterByBranchMixin
from services.translation.mixins import FieldsTranslationMixin

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


class GenericAPIView(FieldsTranslationMixin, ResponseMixin, generics.GenericAPIView):
    pass

class CreateAPIView(FieldsTranslationMixin, ResponseMixin, generics.CreateAPIView):
    pass

class ListAPIView(FieldsTranslationMixin, ResponseMixin, generics.ListAPIView):
    pass

class ListCreateAPIView(FieldsTranslationMixin, ResponseMixin, generics.ListCreateAPIView):
    pass 

class FilterListAPIView(FieldsTranslationMixin, FilterByBranchMixin, ResponseMixin, generics.ListAPIView):
    pass 

class FilterListCreateAPIView(FieldsTranslationMixin, FilterByBranchMixin, ResponseMixin, generics.ListCreateAPIView):
    pass 

class RetrieveAPIView(FieldsTranslationMixin, ResponseMixin, generics.RetrieveAPIView):
    pass

class UpdateAPIView(FieldsTranslationMixin, ResponseMixin, generics.UpdateAPIView):
    pass

class DeleteAPIView(FieldsTranslationMixin, ResponseMixin, generics.DestroyAPIView):
    pass

class RetrieveUpdateAPIView(FieldsTranslationMixin, ResponseMixin, generics.RetrieveUpdateAPIView):
    pass

class RetrieveUpdateDeleteAPIView(FieldsTranslationMixin, ResponseMixin, generics.RetrieveUpdateDestroyAPIView):
    pass 
