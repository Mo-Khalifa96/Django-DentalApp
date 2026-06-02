from django.conf import settings


#Swagger-related functions (if enabled)
if settings.ENABLE_SWAGGER:
    from drf_spectacular.types import OpenApiTypes
    from drf_spectacular.utils import (
        inline_serializer,
        extend_schema_view,
        extend_schema_field,
        extend_schema_serializer,
        extend_schema,
        OpenApiResponse,
        OpenApiParameter,
        OpenApiExample
    )

else:
    #Use no-op functions in production
    def extend_schema_view(*args, **kwargs):
        def no_op_decorator(func):
            return func
        return no_op_decorator
    
    def extend_schema_field(*args, **kwargs):
        def no_op_decorator(func):
            return func
        return no_op_decorator
    
    def extend_schema_serializer(*args, **kwargs):
        def no_op_decorator(cls):
            return cls
        return no_op_decorator
    
    def extend_schema(*args, **kwargs):
        def no_op_decorator(func):
            return func
        return no_op_decorator
    
    def inline_serializer(*args, **kwargs):
        def no_op_decorator(func):
            return func 
        return no_op_decorator

    class OpenApiResponse:
        """No-op OpenApiResponse class"""
        def __init__(self, *args, **kwargs):
            pass
        
        def __repr__(self):
            return f"<OpenApiResponse>"

    class OpenApiExample:
        """No-op OpenApiExample class"""
        def __init__(self, *args, **kwargs):
            pass
        
        def __repr__(self):
            return f"<NoOpOpenApiExample>"
    
    class OpenApiParameter:
        """No-op OpenApiParameter class"""
        # Location constants
        QUERY = 'query'
        PATH = 'path'
        HEADER = 'header'
        COOKIE = 'cookie'

        def __init__(self, *args, **kwargs):
            pass

        def __repr__(self):
            return '<OpenApiParameter>'


    class OpenApiTypes:
        """No-op OpenApiTypes class"""
        # Common type constants
        DATE = 'date'
        DATETIME = 'datetime'
        STR = 'string'
        INT = 'integer'
        FLOAT = 'number'
        BOOL = 'boolean'
        UUID = 'uuid'
        URI = 'uri'
        EMAIL = 'email'

        def __init__(self, *args, **kwargs):
            pass

        def __repr__(self):
            return '<OpenApiTypes>'
