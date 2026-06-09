
from django.utils import translation

class LanguageFromQueryMixin:
    """
    Activates the language for the duration of the request
    based on ?lang=ar / ?lang=en query param.

    *NOTE:* Use EITHER this mixin OR the middleware but NOT both.
    """
    def initial(self, request, *args, **kwargs):
        lang = request.query_params.get('lang')
        if lang:
            translation.activate(lang)
        #Call the view's initial() after
        super().initial(request, *args, **kwargs)  #everything else runs here

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        translation.deactivate()  #deactivation runs AFTER the full chain completes
        return response


#Applied to views as follows:
# # views.py
# class TreatmentViewSet(LanguageFromQueryMixin, viewsets.ModelViewSet):
#     queryset = Treatment.objects.all()
#     serializer_class = TreatmentSerializer

#Or, for base views:
# core/base_views.py — place LanguageFromQueryMixin BEFORE ResponseMixin
# class ListCreateAPIView(LanguageFromQueryMixin, ResponseMixin, generics.ListCreateAPIView):
#     pass
# ...
# same for all others

#Workflow:
# ListCreatePatientsAPIView
#   → ListCreateAPIView
#     → LanguageFromQueryMixin       # ← inserted here
#       → ResponseMixin
#         → generics.ListCreateAPIView
#            → APIView


#########################


#Field names by arabic and english
FIELD_NAME_TRANSLATIONS = {
    'en': {
        'name': 'name',
        'description': 'description',
        'price': 'price',
    },
    'ar': {
        'name': 'اسم',
        'description': 'وصف',
        'price': 'سعر',
    },
    #...
    #...
}

#TODO: Or divide by model and detect the type of model in use -- efficiency to be confirmed!


class TranslatableFieldNamesMixin:   #TODO - How efficient?
    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context['request'].query_params.get('lang', 'en')
        mapping = FIELD_NAME_TRANSLATIONS.get(lang, {})
        return {mapping.get(k, k): v for k, v in data.items()} if mapping else data


#Applied to serializers as follows:
# class TreatmentSerializer(TranslatableFieldNamesMixin, serializers.ModelSerializer):
#     class Meta:
#         model = Treatment
#         fields = ['name', 'description', 'price']

#OR, on serializers with other mixins:
# class RetrievePatientSerializer(
#     TranslatableFieldNamesMixin,  # outermost — renames AFTER everything else builds the dict
#     UserPermissionsMixin,         # adds metadata
#     serializers.ModelSerializer   # builds the base dict
# ):
#     ...


#NOTE: DO NOT USE IF THE SERIALIZER ALREADY USES to_representation() AND REFERENCING A FIELD NAME!
# WRONG — mixin renames keys first, then your code tries data.get('phone') → None
# class CreatePatientSerializer(TranslatableFieldNamesMixin, ModelSerializer, ValidateBranchMixin):
#     def to_representation(self, instance):
#         data = super().to_representation(instance)  # mixin already renamed 'phone' → 'هاتف'
#         data.get('phone')  # ← returns None, silent failure


#Workflow:
# 1. TranslatableFieldNamesMixin.to_representation()
#    └─ super() ──────────────────────────────────────┐
#                                                      ▼
# 2.                       UserPermissionsMixin.to_representation()
#                          └─ super() ──────────────────┐
#                                                        ▼
# 3.                                    ModelSerializer.to_representation()
#                                          ← returns { id, name, phone, ... }
#                          ▲
#                          UserPermissionsMixin appends metadata: { userPermissions: [...] }
#    ▲
#    TranslatableFieldNamesMixin renames keys on the complete dict (including metadata)
#    — just don't include 'metadata'/'userPermissions' in your mapping and they pass through unchanged



## Summary
# | Location                                                     | Safe? | Reason                                                      |
# |--------------------------------------------------------------|-------|-------------------------------------------------------------|
# | 'LanguageFromQueryMixin' in 'base_views.py'                  | Yes   | initial() and finalize_response() both call super() cleanly |
# | 'TranslatableFieldNamesMixin' on 'RetrievePatientSerializer' | Yes   | No conflicting `to_representation()` on the class itself    |
# | 'TranslatableFieldNamesMixin' on 'CreatePatientSerializer'   | No    | Existing `to_representation()` accesses keys by name —      |
# |                                                              |       | do key renaming in the views "finalize_response" instead    |



#If you decide to use django-modeltranslation or django-parler:
# translation.py
# from modeltranslation.translator import register, TranslationOptions
# from patients.models import TreatmentPlan

# @register(TreatmentPlan)
# class TreatmentPlanTranslationOptions(TranslationOptions):
#     fields = ('name', 'description')

#This created two columns for each field, e.g., 'name_en' and 'name_ar'


#Settings:
# base.py
# MODELTRANSLATION_LANGUAGES = ('en', 'ar')
# MODELTRANSLATION_REQUIRED_LANGUAGES = ('en',)  # only enforce one
# MODELTRANSLATION_FALLBACK_LANGUAGES = {'default': ('en',)}  # explicit fallback chain