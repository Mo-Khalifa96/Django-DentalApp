from utils.swagger_utils import (extend_schema, extend_schema_serializer, extend_schema_field,
                                extend_schema_view, OpenApiExample)


def get_login_schema():
    '''Helper function for lazy import of login view schema to prevent circular import'''
    from rest_framework import serializers
    class login_response_serializer(serializers.Serializer):
        refresh = serializers.CharField()
        access = serializers.CharField()
        user = serializers.DictField(child=serializers.CharField())

    return extend_schema_view(
            post=extend_schema(
                tags=['Auth'],
                summary='Obtain JWT Token Pair',
                description=(
                    'Login to obtain access and refresh tokens\n\n'
                    'Available users for testing:\n'
                    '- <b>Admin</b>:\n'
                    '  > email: admin@clinic.com<br>password: Admin123<br><br>\n'
                    '- <b>Dentist</b>:\n'
                    '  > email: dentist@clinic.com<br>password: Dentist123<br><br>\n'
                    '- <b>Dentist 2</b>:\n'
                    '  > email: dentist2@clinic.com<br>password: Dentist123<br><br>\n'
                    '- <b>Receptionist</b>:\n'
                    '  > email: receptionist@clinic.com<br>password: Receptionist123<br><br>\n'
                    '- <b>Assistant</b>:\n'
                    '  > email: assistant@clinic.com<br>password: Assistant123<br><br>\n'
                    '- <b>Accountant</b>:\n'
                    '  > email: accountant@clinic.com<br>password: Accountant123\n'
                ),
                responses={200: login_response_serializer, 401: login_response_serializer},
                examples=[
                    OpenApiExample(
                        name='Request body',
                        request_only=True,
                        value={
                            'email': 'admin@clinic.com',
                            'password': 'Admin123'
                        }
                    ),
                    OpenApiExample(
                        name='Response (200 OK)',
                        response_only=True,
                        status_codes=[200],
                        value={
                            'refresh': '<JWT refresh token>',
                            'access': '<JWT access token>',
                            'user': {
                                'id': 'ebe27408-2fb9-42b2-977a-fbaa1bf0a396',
                                'email': 'dr.layla@dentaltech.com',
                                'name': 'Dr. Layla Hassan',
                                'role': 'dentist',
                                'specialization': 'General Dentistry',
                                'activeBranchId': 'f8c1df87-88d5-4516-9498-7d3273d28db2',
                                'branchIds': [
                                    'f8c1df87-88d5-4516-9498-7d3273d28db2',
                                    '4b003dd4-f654-4ac3-8dc4-07bd2c7bd7f3',
                                    '908be626-8934-4093-a93f-1541d50ceb29'
                                    ]
                                }
                        }
                    ),
                    OpenApiExample(
                        name='Error Response (401 Unauthorized)',
                        response_only=True,
                        status_codes=[401],
                        value={
                            'success': False,
                            'error': {
                                'code': 'NO_ACTIVE_ACCOUNT',
                                'message': 'No active account found with the given credentials'
                            }
                        }
                    )
                ]
            )
        )


#Schema for 'permissions' field
permissions_field_schema = extend_schema_field({
    'type': 'object', 'properties': {
        'view.calender': {'type': 'boolean'},
        'view.clinicalAnalytics': {'type': 'boolean'},
        'view.financialAnalytics': {'type': 'boolean'},
        'view.waitingRoom': {'type': 'boolean'},
        'view.patients': {'type': 'boolean'},
        'view.patientDetail': {'type': 'boolean'},
        'create.patient': {'type': 'boolean'},
        'update.patient': {'type': 'boolean'},
        'delete.patient': {'type': 'boolean'},
        'view.visits': {'type': 'boolean'},
        'create.visit': {'type': 'boolean'},
        'view.appointments': {'type': 'boolean'},
        'view.appointmentDetail': {'type': 'boolean'},
        'create.appointment': {'type': 'boolean'},
        'update.appointment': {'type': 'boolean'},
        'delete.appointment': {'type': 'boolean'},
        'send.whatsappMessage': {'type': 'boolean'},
        'view.treatments': {'type': 'boolean'},
        'create.treatment': {'type': 'boolean'},
        'update.treatment': {'type': 'boolean'},
        'delete.treatment': {'type': 'boolean'},
        'view.procedures': {'type': 'boolean'},
        'create.procedure': {'type': 'boolean'},
        'update.procedure': {'type': 'boolean'},
        'delete.procedure': {'type': 'boolean'},
        'view.inventory': {'type': 'boolean'},
        'create.inventory': {'type': 'boolean'},
        'update.inventory': {'type': 'boolean'},
        'delete.inventory': {'type': 'boolean'},
        'view.labs': {'type': 'boolean'},
        'create.lab': {'type': 'boolean'},
        'update.lab': {'type': 'boolean'},
        'delete.lab': {'type': 'boolean'},
        'view.labOrders': {'type': 'boolean'},
        'view.labOrderDetail': {'type': 'boolean'},
        'create.labOrder': {'type': 'boolean'},
        'update.labOrder': {'type': 'boolean'},
        'delete.labOrder': {'type': 'boolean'},
        'view.bills': {'type': 'boolean'},
        'create.bill': {'type': 'boolean'},
        'update.bill': {'type': 'boolean'},
        'delete.bill': {'type': 'boolean'},
        'view.transactions': {'type': 'boolean'},
        'create.transaction': {'type': 'boolean'},
        'delete.transaction': {'type': 'boolean'},
        'view.invoices': {'type': 'boolean'},
        'create.invoice': {'type': 'boolean'},
        'update.invoice': {'type': 'boolean'},
        'delete.invoice': {'type': 'boolean'},
        'view.sterilizationLogs': {'type': 'boolean'},
        'create.sterilizationLog': {'type': 'boolean'},
        'update.sterilizationLog': {'type': 'boolean'},
        'delete.sterilizationLog': {'type': 'boolean'},
        'view.recalls': {'type': 'boolean'},
        'create.recall': {'type': 'boolean'},
        'update.recall': {'type': 'boolean'},
        'delete.recall': {'type': 'boolean'},
        'view.doctorSchedules': {'type': 'boolean'},
        # 'view.doctorScheduleDetail': {'type': 'boolean'},
        'view.settings': {'type': 'boolean'}, 
        'view.preferences': {'type': 'boolean'}
        }})


#Schema for retrieve user serializer
retrieve_user_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='user permissions are visible to admin only.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'email': 'dr.layla@dentaltech.com',
                    'name': 'Dr. Layla Hassan',
                    'role': 'dentist',
                    'specialization': 'General Dentistry',
                    'activeBranchId': 'f8c1df87-88d5-4516-9498-7d3273d28db2',
                    'branchIds': [
                        'f8c1df87-88d5-4516-9498-7d3273d28db2',
                        '4b003dd4-f654-4ac3-8dc4-07bd2c7bd7f3',
                        '908be626-8934-4093-a93f-1541d50ceb29'
                    ],
                    'avatar': 'https://dentaltech.com/media/user_avatars/example_img.jpg',
                    'permissions': {
                        'view.calender': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.patientDetail': True,
                        'create.patient': True,
                        'update.patient': True,
                        'delete.patient': False,
                        'view.visits': True,
                        'create.visit': True,
                        'view.appointments': True,
                        'view.appointmentDetail': True,
                        'create.appointment': True,
                        'update.appointment': True,
                        'delete.appointment': False,
                        'send.whatsappMessage': False,
                        'view.treatments': True,
                        'create.treatment': True,
                        'update.treatment': True,
                        'delete.treatment': False,
                        'view.procedures': True,
                        'create.procedure': True,
                        'update.procedure': True, 
                        'delete.procedure': True,
                        'view.inventory': True,
                        'create.inventory': True,
                        'update.inventory': True,
                        'delete.inventory': False,
                        'view.labs': True,
                        'create.lab': False,
                        'update.lab': False,
                        'delete.lab': False,
                        'view.labOrders': True,
                        'view.labOrderDetail': True,
                        'create.labOrder': False,
                        'update.labOrder': False,
                        'delete.labOrder': False,
                        'view.bills': True,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False,
                        'view.transactions': False,
                        'create.transaction': True,
                        'delete.transaction': False,
                        'view.invoices': True,
                        'create.invoice': True,
                        'update.invoice': False,
                        'delete.invoice': False,
                        'view.sterilizationLogs': True,
                        'create.sterilizationLog': True,
                        'update.sterilizationLog': True,
                        'delete.sterilizationLog': False,
                        'view.recalls': True,
                        'create.recall': True,
                        'update.recall': True,
                        'delete.recall': True,
                        'view.doctorSchedules': True,  
                        # 'view.doctorScheduleDetail': True,
                        'view.settings': False, 
                        'view.preferences': True,
                    },
                    'isActive': True,
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'metadata': {
                        'userPermissions': {
                            'view.calender': True,
                            'view.waitingRoom': True,
                            'view.patients': True,
                            'view.appointments': True,
                            'view.procedures': True,
                            'view.inventory': True,
                            'view.labs': True,
                            'view.labOrders': True,
                            'view.bills': True,
                            'view.transactions': False,
                            'view.invoices': True,
                            'view.doctorSchedules': True,
                            'view.sterilizationLogs': True,
                            'view.recalls': True,
                            'view.clinicalAnalytics': True,
                            'view.financialAnalytics': False,
                            'view.settings': True,
                            'view.preferences': True
                        }
                    }
                }
            }
        ),
        OpenApiExample(
            name='Non-Admin Response',
            response_only=True,
            description='Response without user permissions for non-admins.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'email': 'dr.layla@dentaltech.com',
                    'name': 'Dr. Layla Hassan',
                    'role': 'dentist',
                    'specialization': 'General Dentistry',
                    'activeBranchId': 'f8c1df87-88d5-4516-9498-7d3273d28db2',
                    'branchIds': [
                        'f8c1df87-88d5-4516-9498-7d3273d28db2',
                        '4b003dd4-f654-4ac3-8dc4-07bd2c7bd7f3',
                        '908be626-8934-4093-a93f-1541d50ceb29'
                    ],
                    'avatar': 'https://dentaltech.com/media/user_avatars/example_img.jpg',
                    'isActive': True,
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'metadata': {
                        'userPermissions': {
                            'view.calender': True,
                            'view.waitingRoom': True,
                            'view.patients': True,
                            'view.appointments': True,
                            'view.procedures': True,
                            'view.inventory': True,
                            'view.labs': False,
                            'view.labOrders': True,
                            'view.bills': False,
                            'view.transactions': False,
                            'view.invoices': False,
                            'view.doctorSchedules': True,
                            'view.sterilizationLogs': True,
                            'view.recalls': True,
                            'view.clinicalAnalytics': True,
                            'view.financialAnalytics': False,
                            'view.settings': False,
                            'view.preferences': True,
                        }
                    }
                }
            }
        )
    ]
)


#Schema for update user serializer
update_user_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Admin Request',
            request_only=True,
            description='Full update request for admin (*NOTE:* password fields are removed for non-account owners).',
            value={
                'email': 'dr.layla@dentaltech.com',
                'currentPassword': 'currentPassword123',
                'newPassword': 'newpassword123',
                'newPassword2': 'newpassword123',
                'name': 'Dr. Layla Hassan',
                'role': 'dentist',
                'specialization': 'General Dentistry',
                'branchIds': [
                        '4b003dd4-f654-4ac3-8dc4-07bd2c7bd7f3',
                        '908be626-8934-4093-a93f-1541d50ceb29'
                    ],
                'avatar': 'https://dentaltech.com/media/user_avatars/example_img.jpg',
                'permissions': {
                    'view.calender': True,
                    'view.clinicalAnalytics': True,
                    'view.financialAnalytics': False,
                    'view.waitingRoom': True,
                    'view.patients': True,
                    'view.patientDetail': True,
                    'create.patient': True,
                    'update.patient': True,
                    'delete.patient': False,
                    'view.visits': True,
                    'create.visit': True,
                    'view.appointments': True,
                    'view.appointmentDetail': True,
                    'create.appointment': True,
                    'update.appointment': True,
                    'delete.appointment': True,
                    'send.whatsappMessage': False, 
                    'view.treatments': True,
                    'create.treatment': True,
                    'update.treatment': True,
                    'delete.treatment': False,
                    'view.procedures': True,
                    'create.procedure': True,
                    'update.procedure': True, 
                    'delete.procedure': True,
                    'view.inventory': True,
                    'create.inventory': True,
                    'update.inventory': True,
                    'delete.inventory': True,
                    'view.labs': True,
                    'create.lab': False,
                    'update.lab': False,
                    'delete.lab': False,
                    'view.labOrders': True,
                    'view.labOrderDetail': True,
                    'create.labOrder': False,
                    'update.labOrder': True,
                    'delete.labOrder': False,
                    'view.bills': True,
                    'create.bill': True,
                    'update.bill': False,
                    'delete.bill': False,
                    'view.transactions': False,
                    'create.transaction': True,
                    'delete.transaction': False,
                    'view.invoices': True,
                    'create.invoice': True,
                    'update.invoice': False,
                    'delete.invoice': False,
                    'view.sterilizationLogs': True,
                    'create.sterilizationLog': True,
                    'update.sterilizationLog': True,
                    'delete.sterilizationLog': False,
                    'view.recalls': True,
                    'create.recall': True,
                    'update.recall': True,
                    'delete.recall': True,
                    'view.doctorSchedules': True,
                    # 'view.doctorScheduleDetail': True,
                    'view.settings': False,
                    'view.preferences': True,
                },
                'isActive': True,
                'updatedAt': '2026-04-24T23:33:54.610Z',
            }
        ),
        OpenApiExample(
            name='Non-Admin (account owner) Request',
            request_only=True,
            description='Request without role, permissions and branch fields.',
            value={
                'email': 'dr.layla@dentaltech.com',
                'currentPassword': 'currentPassword123',
                'newPassword': 'newpassword123',
                'newPassword2': 'newpassword123',
                'name': 'Dr. Layla Hassan',
                'specialization': 'General Dentistry',
                'avatar': 'https://dentaltech.com/media/user_avatars/example_img.jpg',
            }
        ),
        OpenApiExample(
            name='Success Response (200 OK)',
            response_only=True,
            description='Response (for admin and non-admin users) -- *let me know if it needs customization by role too!*',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'email': 'dr.layla@dentaltech.com',
                    'name': 'Dr. Layla Hassan',
                    'role': 'dentist',
                    'specialization': 'General Dentistry',
                    'branchIds': [
                        '4b003dd4-f654-4ac3-8dc4-07bd2c7bd7f3',
                        '908be626-8934-4093-a93f-1541d50ceb29'
                    ],
                    'avatar': 'https://dentaltech.com/media/user_avatars/example_img.jpg',
                    'permissions': {
                        'view.calender': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.patientDetail': True,
                        'create.patient': True,
                        'update.patient': True,
                        'delete.patient': False,
                        'view.procedures': True,
                        'create.procedure': True,
                        'update.procedure': True, 
                        'delete.procedure': True,
                        'view.treatments': True,
                        'create.treatment': True,
                        'update.treatment': True,
                        'delete.treatment': False,
                        'view.appointments': True,
                        'view.appointmentDetail': True,
                        'create.appointment': True,
                        'update.appointment': True,
                        'delete.appointment': True,
                        'send.whatsappMessage': False,
                        'view.visits': True,
                        'create.visit': True,
                        'view.inventory': True,
                        'create.inventory': True,
                        'update.inventory': True,
                        'delete.inventory': True,
                        'view.labs': True,
                        'create.lab': False,
                        'update.lab': False,
                        'delete.lab': False,
                        'view.labOrders': True,
                        'view.labOrderDetail': True,
                        'create.labOrder': False,
                        'update.labOrder': True,
                        'delete.labOrder': False,
                        'view.bills': True,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False,
                        'view.transactions': False,
                        'create.transaction': True,
                        'delete.transaction': False,
                        'view.invoices': True,
                        'create.invoice': True,
                        'update.invoice': False,
                        'delete.invoice': False,
                        'view.sterilizationLogs': True,
                        'create.sterilizationLog': True,
                        'update.sterilizationLog': True,
                        'delete.sterilizationLog': False,
                        'view.recalls': True,
                        'create.recall': True,
                        'update.recall': True,
                        'delete.recall': False,
                        'view.doctorSchedules': True,
                        # 'view.doctorScheduleDetail': True,
                        'view.settings': False,
                        'view.preferences': True,
                    }
                }
            }
        ),
        OpenApiExample(
            name='Error Response (400 Bad Request)',
            response_only=True,
            value={
                    'success': False,
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': 'Validation failed',
                        'fields': {
                            'name': 'This field is required.',
                            'email': 'Email address entered is invalid.'
                        }
                    }
            }
        ),
    ]
)


#Schema for users options serializer
users_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'roleChoices': [
                    {'value': 'admin', 'label': 'Admin'},
                    {'value': 'dentist', 'label': 'Dentist'},
                    {'value': 'receptionist', 'label': 'Receptionist'},
                    {'value': 'assistant', 'label': 'Assistant'},
                    {'value': 'accountant', 'label': 'Accountant'},
                ],
            }
        )
    ]
) 


#Schema for doctor schedules options serializer 
doctor_schedules_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'doctorChoices': [
                    {'doctorId': '8d9e0abc-7abb-4497-a2ed-19737c92a229', 'doctorName': 'Layla Hassan'},
                    {'doctorId': 'ec4ebe94-c8a6-45d5-8cc6-675cef7bbafe', 'doctorName': 'Ahmed Hassan'}, 
                    {'doctorId': '0078af5e-7b68-4c29-9c81-04c8665fee68', 'doctorName': 'Ghassan Mattar'}
                ],
                'weekDaysChoices': [
                    {'value': 0, 'label': 'Sunday'},
                    {'value': 1, 'label': 'Monday'},
                    {'value': 2, 'label': 'Tuesday'},
                    {'value': 3, 'label': 'Wednesday'},
                    {'value': 4, 'label': 'Thursday'},
                    {'value': 5, 'label': 'Friday'},
                    {'value': 6, 'label': 'Saturday'},
                ],
                'exceptionTypeChoices': [
                    {'value': 'off', 'label': 'Off'},
                    {'value': 'vacation', 'label': 'Vacation'},
                    {'value': 'conference', 'label': 'Conference'},
                ]
            }
        )
    ]
)


#Schema for retrieving login view schema
login_view_schema = get_login_schema()
