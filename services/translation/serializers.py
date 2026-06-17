from django.conf import settings
from django.utils import translation
from rest_framework import serializers


#Serializer for choice fields to enable translation of choices
class TranslatedChoiceField(serializers.ChoiceField):
    '''
    A ChoiceField with language support.
    - OUTPUT: returns the translated display label respecting the active language
    - INPUT: accepts either the stored value ('Male') OR any translated label ('ذكر')
             and normalizes to the stored value
    '''

    def to_representation(self, value):
        #self.choices automatically hands translation when using models.TextChoices
        return str(self.choices.get(value, value)) 

    def to_internal_value(self, input_value):
        #Accept original (english) labels automatically
        if input_value in self.choices:
            return input_value
        #account for choice fields with blank and null set to True
        elif input_value == '' and getattr(self, 'allow_blank', False):
            return ''
        elif input_value is None and getattr(self, 'allow_null', False):
            return None

        #Process translated labels and store values in english
        for lang_code, _ in settings.LANGUAGES:
            with translation.override(lang_code):
                for value, label in self.choices.items():
                    if str(label) == str(input_value):
                        return value

        raise serializers.ValidationError(
            self.error_messages['invalid_choice'].format(input=input_value)
        )


#How To Use: 
# Example 1:
# class CreatePatientSerializer(serializers.ModelSerializer, ValidateBranchMixin):
#     branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)
#     gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
#     status = TranslatedChoiceField(choices=Patient.StatusChoices.choices, read_only=True)

#     class Meta:
#         model = Patient
#         fields = [...]
#         read_only_fields = ['id', 'status', 'createdAt', 'updatedAt']
#         ...

# Example 2:
# class ListPatientSerializer(serializers.ModelSerializer):
#     gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices, read_only=True)
#     status = TranslatedChoiceField(choices=Patient.StatusChoices.choices, read_only=True)

#     class Meta:
#         model = Patient
#         fields = [...]