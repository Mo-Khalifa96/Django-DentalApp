
from django.utils import translation

#Field names by arabic and english
FIELD_NAME_TRANSLATIONS = {
    'ar': {
        'branch': 'الفرع',
        'branches': 'الفروع',
        'name': 'الاسم',
        'fullName': 'الاسم كامل',
        'phone': 'الهاتف',
        'email': 'البريد الإلكتروني',
        'address': 'العنوان',
        'region': 'المنطقة',
        'role': 'الدور الوظيفي',
        'specialization': 'التخصص',
        'speciality': 'التخصص',
        'avatar': 'الصورة الشخصية',
        'userPermissions': 'صلاحيات المستخدم',
        'isActive': 'نشط',
        'is_staff': 'موظف',
        'password': 'كلمة المرور',
        'permission': 'الصلاحية',
        'permissions': 'الصلاحيات',
        'createdAt': 'تاريخ الإنشاء',
        'updatedAt': 'تاريخ التحديث',
        'is_deleted': 'محذوف',
        'isDeleted': 'محذوف',
        'key': 'المفتاح',
        'label': 'التسمية',
        'module': 'الوحدة',
        'doctor': 'الطبيب',
        'doctorName': 'اسم الطبيب',
        'workingDays': 'أيام العمل',
        'startDate': 'تاريخ البدء',
        'startTime': 'وقت البدء',
        'endTime': 'وقت الانتهاء',
        'breakStart': 'بداية الاستراحة',
        'breakEnd': 'نهاية الاستراحة',
        'schedule': 'جدول المواعيد',
        'date': 'التاريخ',
        'type': 'النوع',
        'note': 'ملاحظة',
        'notes': 'ملاحظات',
        'description': 'الوصف',
        'age': 'العمر',
        'gender': 'الجنس',
        'status': 'الحالة',
        'code': 'الرمز',
        'countryCode': 'رمز الدولة',
        'nationalId': 'الرقم القومي',
        'patientNationalId': 'الرقم القومي',
        'patientPhone': 'هاتف المريض',
        'is_newPatient': 'مريض جديد',
        'newPatientDetails': 'بيانات المريض الجديد',
        'bloodType': 'فصيلة الدم',
        'allergies': 'الحساسيات',
        'insurance': 'التأمين',
        'insuranceId': 'رقم التأمين',
        'lastVisit': 'آخر زيارة',
        'nextAppointment': 'الموعد القادم',
        'patient': 'المريض',
        'patientName': 'اسم المريض',
        'toothNumber': 'رقم السن',
        # 'teeth': 'الأسنان',
        # 'surfaces': 'الاسطح',
        # 'sites': 'مواقع الفحص',
        # 'sitesProbed': 'عدد المواقع المفحوصة',
        # 'probingDepth': 'عمق الفحص',
        # 'meanProbingDepth': 'متوسط عمق الفحص',
        # 'mobility': 'حركية السن',
        # 'furcation': 'الكسر',
        # 'recession': 'تراجع اللثة',
        # 'bleeding': 'نزيف',
        # 'bleedingPercent': 'نسبة النسزيف',
        # 'plaque': 'بلاك',
        # 'suppuration': 'تقيح',
        # 'calculus': 'جير',
        # 'attachmentLoss': 'فقدان الارتباط السني', 
        'lastUpdated': 'آخر تحديث',
        'procedure': 'الإجراء',
        'procedures': 'الإجراءات',
        'procedureName': 'اسم الإجراء',
        'price': 'السعر',
        'cost': 'التكلفة',
        'paid': 'المدفوع',
        'currency': 'العملة',
        'xray': 'الأشعة',
        'xrayUploads': 'ملفات الأشعة',
        'xrayUrls': 'روابط الأشعة',
        'image': 'الصورة',
        'document': 'المستند',
        'documents': 'المستندات',
        'fileName': 'اسم الملف',
        'contentType': 'نوع الملف',
        'sizeBytes': 'حجم الملف',
        'uploadedAt': 'تاريخ الرفع',
        'uploadedBy': 'رفع بواسطة',
        'title': 'العنوان',
        'totalCost': 'إجمالي التكلفة',
        'installmentMonths': 'مدة التقسيط (بالأشهر)',
        'session': 'جلسة',
        'sessions': 'الجلسات',
        'treatmentPlan': 'خطة العلاج',
        'installmentPlan': 'نظام التقسيط',
        'installments': 'الاقساط',
        'downPayment': 'مقدم',
        'deposit': 'إيداع',
        'isWalkIn': 'زيارة بدون موعد',
        'dueDate': 'تاريخ الاستحقاق',
        'contactedAt': 'تاريخ التواصل',
        'refundReason': 'سبب الاسترداد',
        'correctionReason': 'سبب طلب التصحيح',
        'isMain': 'رئيسي',
        'openTime': 'وقت الفتح',
        'closeTime': 'وقت الإغلاق',
        'room': 'الغرفة',
        'rooms': 'الغرف',
        'color': 'اللون',
        'appointment': 'الموعد',
        'referredBy': 'محال من', 
        'referredTo': 'محال الى', 
        'referredByName': 'اسم المحيل',
        'referredToName': 'اسم المحال اليه',
        # 'referredById': 'رقم المحيل', 
        # 'referredByUserId': 'رقم المحيل', 
        # 'referredToUserId': 'رقم المحال اليه', 
        # 'referredToEntityId': 'رقم الجها المحال اليها', 
        'examinedBy': 'الفاحص', 
        'examinedByName': 'اسم الفاحص',
        'examinedAt': 'تاريخ الفحص', 
        'outcome': 'النتيجة',
        'provider': 'المتكفل',
        'providerName': 'اسم المتكفل',
        'insuranceProviderName': 'اسم متكفل التأمين',
        'arrivedAt': 'وقت الوصول',
        'startedAt': 'وقت البدء',
        'completedAt': 'وقت الانتهاء',
        'duration': 'المدة',
        'tier': 'الفئة',
        'contact': 'جهة الاتصال',
        # 'is_newProvider': 'متكفل جديد',
        # 'newProviderDetails': 'بيانات المتكفل الجديد',
        'memberId': 'رقم العضوية',
        'annualMax': 'الحد الأقصى السنوي',
        'usedYTD': 'استخدام السنة الحالية',
        'deductible': 'الحد الادنى لتفعيل التأمين',
        'deductibleMet': 'استوفى المبلغ المقتطع',
        'effectiveFrom': 'ساري من',
        'effectiveTo': 'ساري حتى',
        'eligibilityStatus': 'حالة الأهلية',
        'eligibilityChecked': 'تاريخ التحقيق من الاهلية',
        'coveragePercent': 'نسبة التغطية',
        # 'byEligibility': 'بحالة الصلاحية',
        # 'active': 'نشط',
        # 'expiring': 'منتهي',
        # 'expired': 'سينتهي قريباً',
        # 'limit_reached': 'بلغ الحد الاقصى',
        # 'none': 'لا يوجد',
        'responseDays': 'فترة الاستجابة',
        'category': 'الفئة',
        'currentStock': 'المخزون الحالي',
        'minStock': 'الحد الأدنى للمخزون',
        'unit': 'الوحدة',
        'supplier': 'المورد',
        'lastOrdered': 'آخر طلب',
        'contactPerson': 'جهة الاتصال',
        'lab': 'المختبر',
        'labName': 'اسم المختبر',
        'instructions': 'التعليمات',
        'sentDate': 'تاريخ الإرسال',
        'receivedDate': 'تاريخ الاستلام',
        'deliveredDate': 'تاريخ التسليم',
        'time': 'الوقت',
        'operator': 'المشغّل',
        'cycleType': 'نوع الدورة',
        'cycleNumber': 'رقم الدورة',
        'autoclaveType': 'نوع جهاز التعقيم',
        'temp': 'الحرارة',
        'pressure': 'الضغط',
        'turnaroundDays': 'مدة التجهيز (بالأيام)',
        'instrumentSets': 'مجموعات الأدوات',
        'result': 'النتيجة',
        'sealedAt': 'تاريخ التغليف',
        'shelfLifeDays': 'مدة الصلاحية (بالأيام)',
        'message': 'الرسالة',
        'messageType': 'نوع الرسالة',
        'sentAt': 'وقت الإرسال',
        'clinic': 'العيادة',
        'clinicName': 'اسم العيادة',
        'taxId': 'الرقم الضريبي',
        'activityCode': 'رمز النشاط',
        'commercialReg': 'رقم السجل التجاري',
        'branchName': 'اسم الفرع',
        'visit': 'الزيارة',
        'visits': 'الزيارات',
        'treatment': 'العلاج',
        'treatmentTitle': 'عنوان العلاج',
        'items': 'العناصر',
        'tax': 'الضريبة',
        'discount': 'الخصم',
        'total': 'الإجمالي',
        'totalAmount': 'إجمالي المبلغ',
        'totalPaid': 'إجمالي المدفوع',
        'subtotal': 'المجموع الفرعي',
        'createdBy': 'تم الإنشاء بواسطة',
        'issuedBy': 'تم الإصدار بواسطة',
        'issuedAt': 'تاريخ الإصدار',
        'SubmittedAt': 'تاريخ التقديم',
        'bill': 'الفاتورة',
        'billDescription': 'وصف الفاتورة',
        'amount': 'المبلغ',
        'method': 'طريقة الدفع',
        'sequence': 'التسلسل',
        'paidAt': 'تاريخ الدفع',
        'invoice': 'وصل',
        'invoiceNumber': 'رقم الوصل',
        'recipientName': 'اسم المستلم', 
        'billedToName': 'اسم المستلم', 
        'billedToTaxId': 'الرقم الضريبي',
        'billedToAddress': 'عنوان المستلم',
        'quantity': 'الكمية',
        'unitPrice': 'سعر الوحدة',
        'taxCode': 'الرمز الضريبي',
        # 'revenue': 'الإيرادات',
        # 'totalOutstanding': 'إجمالي التكاليف المطلوبة',
        # 'outstandingBalance': 'إجمالي التكاليف المطلوبة',
        # 'totalBilled': 'إجمالي الفواتير',
        # 'billedInPeriod': 'إجمالي الفواتير',
        # 'totalCollected': 'إجمالي المدفوعات المسددة',
        # 'collectedInPeriod': 'إجمالي المدفوعات المسددة',
        # 'collectedFromPatient': 'مدفوعات المريض',
        # 'collectedFromInsurer': 'مدفوعات شركة التأمين',
        # 'totalCreditHeld': 'إجمالي الودائع و المستردات',
        # 'collectedByMethod': 'المدفوعات بوسيلة الدفع',
        # 'cash': 'كاش', 
        # 'card': 'بطاقة',
        # 'bank_transfer': 'تحويل بنكي', 
        # 'insurance': 'تأمين',
        # 'mobile_wallet': 'محفظة إلكترونية',
        # 'unsettledBillsCount': '',
        # 'totalBilledOutstanding': '',
        # 'lastBillUpdatedAt': '',
        # 'pendingInstallmentsCount': '',
        # 'totalInstallmentsOutstanding': '',
        # 'insuranceCoverageStatus': '',
        # 'coverageEffectiveTo': '',
        # 'insuranceAnnualMax': '',
        # 'insuranceUsedYTD': '',
        # 'yearlyBenefitRemaining': '',
        # 'patientCount': 'عدد المرضى',
        # 'patientsTotal': 'إجمالي المرضى',
        # 'patientsNew': 'المرضى الجدد',
        # 'appointmentsCount': 'المواعيد',
        # 'appointmentsCount': 'عدد المواعيد',
        # 'appointmentsCompleted': 'المواعيد المكتملة',
        # 'appointmentsCancelled': 'المواعيد الملغية',
        # 'appointmentsNoShow': 'لم يظهر بالمعاد',
        # 'transactionsCount': 'عدد التحويلات',
        # 'coveredPatientsCount': 'عدد المرضى المؤمن عليهم', 
        # 'patientsTotalAnnualMax': 'إجمالي المسموح به',
        # 'patientsTotalUsedYTD': 'إجمالي المستخدم',
        # 'totalYearlyBenefitRemaining': 'إجمالي المتاح للاستخدام',
        # 'relatedBillsCount': 'عدد الفواتير',
        # 'relatedPayments': 'المدفوعات المرتبطة', 
        # 'insuredPatients': 'عدد المرضى المؤمن عليهم',
        # 'annualMaxTotal': 'الحد الاقصى السنوي',
        # 'usedYTDTotal': 'إجمالي المستخدم للسنة',
        # 'remainingTotal': 'إجمالي المتبقي',
        # 'utilisationPercent': 'نسبة الاستخدام',
        # 'waitingRoom': 'غرفة الانتظار',
        # 'waiting': '',
        # 'inChair': '',
        # 'doneToday': '',
        # 'avgWaitMinutes': '',
        # 'recalls': 'المتابعة',
        # 'overdue': '',
        # 'dueToday': '',
        # 'dueThisWeek': '',
        # 'inventory': 'المخزون',
        # 'lowStock': '',
        # 'criticalStock': '',
        # 'id': 'رقم التعريف',
        # 'patientId': 'رقم المريض',
        # 'doctorId': 'رقم الطبيب',
        # 'branchId': 'رقم الفرع',
        # 'branchIds': 'ارقام الفروع',
        # 'activeBranchId': 'رقم الفرع النشط',
        # 'examinedById': 'رقم الفاحص',
        # 'visitId': 'رقم الزيارة',
        # 'visitIds': 'ارقام الزيارات',
        # 'appointmentId': 'رقم الموعد',
        # 'treatmentId': 'رقم العلاج',
        # 'procedureId': 'رقم الإجراء',
        # 'providerId': 'معرف متكفل التأمين',
        # 'insuranceProviderId': 'معرف متكفل التأمين',
        # 'coveredPatientId': 'رقم المريض',
        # 'patientTreatmentId': 'رقم العلاج',
        # 'labId': 'رقم المختبر',
        # 'billId': 'رقم الفاتورة',
        # 'transactionId': 'رقم التحويل',
        # 'transactionIds': 'ارقام التحويلات',
        # 'installmentPlanId': 'رقم نظام التقسيط',
        # 'installmentIds': 'ارقام الاقساط',
        # 'invoiceId': 'رقم الوصل',
        # 'messageId': 'رقم الرسالة',
        # 'hasInstallmentPlan': 'لديه نظام تقسيط', 
        # 'isInsuranceBill': '', 
        # 'isCreditHeld': '', 
    }
}


#Mixin for translating model field names
class FieldsTranslationMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if 200 <= response.status_code < 300 and response.data:
            lang = getattr(request, 'LANGUAGE_CODE', 'en')
            if lang != 'en':
                lang_mapping = FIELD_NAME_TRANSLATIONS.get(lang)
                if lang_mapping:
                    incoming_data = response.data.get('data')
                    if isinstance(incoming_data, dict):
                        response.data['data'] = {lang_mapping.get(key,key): val for key,val in incoming_data.items()}
                    elif isinstance(incoming_data, list):
                        response.data['data'] = [
                            {lang_mapping.get(key,key): val for key,val in item.items()}
                            if isinstance(item, dict) else item for item in incoming_data
                        ]
        return response


#Applied to views (or base views) as follows:
# class RetrieveAPIView(FieldsTranslationMixin, ResponseMixin, generics.RetrieveAPIView):
#     pass

# class ListAPIView(FieldsTranslationMixin, ResponseMixin, generics.ListAPIView):
#     pass


# The rule is: 
# when work happens after super(), leftmost = last to act. 
# So, FieldsTranslationMixin must be on the left of ResponseMixin.


#Thus the call chain must follow this order:

# FieldsTranslationMixin.finalize_response()
#     └─ super() ──────────────────────────────────────┐
#                                                       ▼
#                         ResponseMixin.finalize_response()
#                             └─ super() → APIView → raw response
#                         ▲
#                         ResponseMixin wraps { success: True, data: {...} }
#     ▲
#     FieldsTranslationMixin translates keys inside data{}
#     on the fully wrapped response


#########################


class LanguageFromQueryMixin:
    """
    Activates the language for the duration of the request
    based on ?lang=ar / ?lang=en query param.

    *NOTE:* Use EITHER this mixin OR the middleware but NOT both. Currently not in use.
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