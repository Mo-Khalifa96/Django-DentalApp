from django.conf import settings
from django.utils import translation


#Middleware for language localization
class LanguageMiddleware:
    '''
    Extends Django's locale resolution with query param support.
    Resolution order:
      1. ?lang= query param          (API clients)
      2. Accept-Language header       (browsers / mobile)
      3. settings.LANGUAGE_CODE      (fallback)
    '''

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        lang = self._resolve_language(request)
        translation.activate(lang)
        request.LANGUAGE_CODE = lang 

        #entire view runs with language active
        response = self.get_response(request) 

        translation.deactivate()
        response['Content-Language'] = lang
        return response

    def _resolve_language(self, request):
        #use query param, 'lang', if provided
        lang = request.GET.get('lang')
        if lang in self.supported:
            return lang

        #else, use the 'Accept-Language' header, if provided
        header = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if header:
            lang = header.split(',')[0].split(';')[0].strip()[:5]  #trim noise
            if lang in self.supported:
                return lang
            #try base language code ('ar-EG' → 'ar')
            base = lang.split('-')[0]
            if base in self.supported:
                return base

        #Fallback -- uses default language ('en')
        return settings.LANGUAGE_CODE
