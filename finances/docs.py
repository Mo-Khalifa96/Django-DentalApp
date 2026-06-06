from utils.swagger_utils import (extend_schema, extend_schema_serializer, extend_schema_field,
                                extend_schema_view, OpenApiExample)






#Schema for clinic tax config options serializer
# tax_config_options_schema = extend_schema_serializer(
#     examples=[
#         OpenApiExample(
#             name='Response',
#             response_only=True,
#             value={
#                 'branchChoices': [
#                     {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
#                     {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
#                 ],
#             }
#         )
#     ]
# )