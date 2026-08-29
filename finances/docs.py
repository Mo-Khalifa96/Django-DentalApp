from utils.swagger_utils import (extend_schema, extend_schema_serializer, extend_schema_field,
                                extend_schema_view, OpenApiExample)



#List bills schema 
list_bills_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            description='Response without snapshot fields for non-admin users.',
            response_only=True,
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                        'visitIds': [
                            'c3d4e5f6-3456-7890-cdef-3456789012cd',
                            'd4e5f6a7-4567-8901-defa-4567890123de',
                        ],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'description': 'Full mouth rehabilitation - Session 1',
                        'discount': '150.00',
                        'subtotal': '2350.00',
                        'total': '2200.00',
                        'currency': 'USD',
                        'status': 'partial',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'updatedAt': '2026-05-01T10:15:30.000Z',
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': None,
                        'visitIds': [
                            'e5f6a7b8-5678-9012-efab-5678901234ef',
                        ],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'description': 'Routine checkup and scaling',
                        'discount': '0.00',
                        'subtotal': '300.00',
                        'total': '300.00',
                        'currency': 'USD',
                        'status': 'unpaid',
                        'createdAt': '2026-05-01T09:00:00.000Z',
                        'updatedAt': '2026-05-01T09:00:00.000Z',
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/bills/?page=3',
                    'previous': 'https://dtbackend.site/api/bills/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.bills': False,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes additional details, snapshot fields, and isDeleted flag.',
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                        'treatmentTitle': 'Full Mouth Rehabilitation',
                        'visitIds': [
                            'c3d4e5f6-3456-7890-cdef-3456789012cd',
                            'd4e5f6a7-4567-8901-defa-4567890123de',
                        ],
                        'procedures': ['Root Canal Treatment', 'Dental Crown (Ceramic)'],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'description': 'Full mouth rehabilitation - Session 1',
                        'discount': '150.00',
                        'subtotal': '2350.00',
                        'total': '2200.00',
                        'currency': 'USD',
                        'status': 'partial',
                        'createdBy': 'Dr. Layla Hassan',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'updatedAt': '2026-05-01T10:15:30.000Z',
                        'isDeleted': False,
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': None,
                        'treatmentTitle': None,
                        'visitIds': [
                            'e5f6a7b8-5678-9012-efab-5678901234ef',
                        ],
                        'procedures': [],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'description': 'Routine checkup and scaling',
                        'discount': '0.00',
                        'subtotal': '300.00',
                        'total': '300.00',
                        'currency': 'USD',
                        'status': 'unpaid',
                        'createdBy': 'Dr. Layla Hassan',
                        'createdAt': '2026-05-01T09:00:00.000Z',
                        'updatedAt': '2026-05-01T09:00:00.000Z',
                        'isDeleted': False,
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/bills/?page=3',
                    'previous': 'https://dtbackend.site/api/bills/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.transactions': True,
                        'view.invoices': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': True,
                        'view.settings': True,
                        'view.bills': True,
                        'create.bill': True,
                        'update.bill': True,
                        'delete.bill': True
                    }
                }
            }
        ),
    ]
)

    
#Retrieve bills schema
retrieve_bills_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            response_only=True,
            description='Response without snapshot fields for non-admin users.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                    'visitIds': [
                        'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'd4e5f6a7-4567-8901-defa-4567890123de',
                    ],
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'description': 'Full mouth rehabilitation - Session 1',
                    'discount': '150.00',
                    'subtotal': '2350.00',
                    'total': '2200.00',
                    'currency': 'USD',
                    'status': 'partial',
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'updatedAt': '2026-05-01T10:15:30.000Z',
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.bills': False,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes snapshot fields, procedures, and isDeleted flag.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                    'treatmentTitle': 'Full Mouth Rehabilitation',
                    'visitIds': [
                        'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'd4e5f6a7-4567-8901-defa-4567890123de',
                    ],
                    'procedures': ['Root Canal Treatment', 'Dental Crown (Ceramic)'],
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'branchName': 'Main Branch',
                    'description': 'Full mouth rehabilitation - Session 1',
                    'discount': '150.00',
                    'subtotal': '2350.00',
                    'total': '2200.00',
                    'currency': 'USD',
                    'status': 'partial',
                    'createdBy': 'Dr. Layla Hassan',
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'updatedAt': '2026-05-01T10:15:30.000Z',
                    'isDeleted': False,
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.transactions': True,
                        'view.invoices': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': True,
                        'view.settings': True,
                        'view.bills': True,
                        'create.bill': True,
                        'update.bill': True,
                        'delete.bill': True
                    }
                }
            }
        ),
    ]
)


        # OpenApiExample(
        #     name='Create Bill Request',
        #     request_only=True,
        #     description='Payload for creating a new bill.',
        #     value={
        #         'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
        #         'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
        #         'visitIds': [
        #             'c3d4e5f6-3456-7890-cdef-3456789012cd',
        #         ],
        #         'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
        #         'description': 'Full mouth rehabilitation - Session 1',
        #         'discount': '150.00',
        #         'subtotal': '2350.00',
        #         'total': '2200.00',
        #         'currency': 'USD',
        #     }
        # ),


#Schema for bills options serializer
bills_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description=(
                'Assign `branchId` to filter patient choices by branch, '
                'assign `doctorId` to filter patient choices by `dentist` user, '
                'and assign `patientId` to filter treatment and visit choices by patient.\n'
                'Empty query parameters return all choices across the system.'
            ),
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'patientChoices': [
                    {'patientId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3', 'name': 'Ahmed Khaled'},
                    {'patientId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4', 'name': 'Khaled Ahmed'},
                ],
                'patientTreatmentChoices': [
                    {'treatmentId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                    {'treatmentId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4'},
                ],
                'patientVisitChoices': [
                    {'visitId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                    {'visitId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4'},
                ],
            }
        )
    ]
) 



#List transactions schema 
list_transactions_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            description='Response without snapshot fields for non-admin users.',
            response_only=True,
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'visitId': 'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'date': '2026-04-24',
                        'amount': '250.00',
                        'currency': 'USD',
                        'method': 'Card',
                        'note': '',
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Khaled Ahmed',
                        'visitId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'date': '2026-05-01',
                        'amount': '300.00',
                        'currency': 'USD',
                        'method': 'Cash',
                        'note': '',
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 150,
                    'totalPages': 6,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/transactions/?page=3',
                    'previous': 'https://dtbackend.site/api/transactions/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.invoices': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.transactions': False,
                        'create.transaction': True,
                        'delete.transaction': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes additional details, snapshot fields, and isDeleted flag.',
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                        'billDescription': 'Full mouth rehabilitation - Session 1',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'visitId': 'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'treatmentTitle': 'Full Mouth Rehabilitation',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'date': '2026-04-24',
                        'amount': '250.00',
                        'currency': 'USD',
                        'method': 'Card',
                        'status': 'Completed',
                        'note': '',
                        'createdBy': 'Dr. Layla Hassan',
                        'isDeleted': False,
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da',
                        'billDescription': 'Routine checkup and scaling',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Khaled Ahmed',
                        'visitId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'treatmentTitle': None,
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'date': '2026-05-01',
                        'amount': '300.00',
                        'currency': 'USD',
                        'method': 'Cash',
                        'status': 'Refunded',
                        'note': '',
                        'createdBy': 'Dr. Layla Hassan',
                        'isDeleted': True,
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 150,
                    'totalPages': 6,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/transactions/?page=3',
                    'previous': 'https://dtbackend.site/api/transactions/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': True,
                        'view.invoices': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': True,
                        'view.transactions': True,
                        'create.transaction': True,
                        'delete.transaction': True
                    }
                }
            }
        ),
    ]
)


#Schema for transactions options serializer
transactions_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description=(
                'Assign `branchId` to filter bill and patient choices by branch, '
                'assign `doctorId` to filter bill and patient choices by `dentist` user, '
                'and assign `patientId` to filter visit choices by patient.\n'
                'Empty query parameters return all choices across the system.'
            ),
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'billChoices': [
                    {'billId': 'd4e5f6a7-4567-8901-defa-4567890123de'},
                    {'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da'}
                ],
                'patientChoices': [
                    {'patientId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3', 'name': 'Ahmed Khaled'},
                    {'patientId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4', 'name': 'Khaled Ahmed'},
                ],
                'patientVisitChoices': [
                    {'visitId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                    {'visitId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4'},
                ],
                'paymentMethodChoices': [
                    {'value': 'cash', 'label': 'Cash'},
                    {'value': 'card', 'label': 'Card'},
                    {'value': 'bank_transfer', 'label': 'Bank transfer'},
                    {'value': 'insurance', 'label': 'Insurance'},
                    {'value': 'mobile_wallent', 'label': 'Mobile wallet'}
                ],
            }
        )
    ]
) 



#List invoices schema
list_invoices_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            description='Response without snapshot fields for non-admin users.',
            response_only=True,
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'invoiceNumber': 'INV-2026-0001',
                        'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'patientNationalId': '525400222211100',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'items': [
                            {
                                'code': None,
                                'description': 'Root canal',
                                'quantity': 1,
                                'unitPrice': '3500.00',
                                'total': '3500.00'
                            },
                            {
                                'code': 'D3330',
                                'description': 'Dental Bridge (3-unit)',
                                'quantity': 3,
                                'unitPrice': '520.00',
                                'total': '1560.00'
                            }
                        ],
                        'subtotal': '5060.00',
                        'tax': '50.00',
                        'discount': '210.00',
                        'total': '4900.00',
                        'currency': 'USD',
                        'status': 'issued',
                        'issuedAt': '2026-04-24T23:33:54.610Z',
                        'submittedAt': None,
                        'createdAt': '2026-04-24T23:33:54.610Z',
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'invoiceNumber': 'INV-2026-0002',
                        'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Khaled Ahmed',
                        'patientNationalId': '525400222211111',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'items': [
                            {
                                'code': None,
                                'description': 'Root canal',
                                'quantity': 1,
                                'unitPrice': '3500.00',
                                'total': '3500.00'
                            },
                        ],
                        'subtotal': '3500.00',
                        'tax': '0.00',
                        'discount': '150.00',
                        'total': '3350.00',
                        'currency': 'USD',
                        'status': 'submitted',
                        'issuedAt': None,
                        'submittedAt': '2026-04-24T23:33:54.610Z',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/invoices/?page=3',
                    'previous': 'https://dtbackend.site/api/invoices/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.invoices': False,
                        'create.invoice': True,
                        'update.invoice': False,
                        'delete.invoice': False
                    }
                }
            }
        ),        
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes additional details, snapshot fields, and isDeleted flag.',
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'invoiceNumber': 'INV-2026-0001',
                        'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                        'billDescription': 'Full mouth rehabilitation - Session 1',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'patientNationalId': '525400222211100',
                        'treatmentTitle': 'Full Mouth Rehabilitation',
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'items': [
                            {
                                'code': None,
                                'description': 'Root canal',
                                'quantity': 1,
                                'unitPrice': '3500.00',
                                'total': '3500.00'
                            },
                            {
                                'code': 'D3330',
                                'description': 'Dental Bridge (3-unit)',
                                'quantity': 3,
                                'unitPrice': '520.00',
                                'total': '1560.00'
                            }
                        ],
                        'subtotal': '5060.00',
                        'tax': '50.00',
                        'discount': '210.00',
                        'total': '4900.00',
                        'currency': 'USD',
                        'status': 'issued',
                        'issuedAt': '2026-04-24T23:33:54.610Z',
                        'submittedAt': None,
                        'createdBy': 'Dr. Layla Hassan',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'isDeleted': False,
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'invoiceNumber': 'INV-2026-0002',
                        'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da',
                        'billDescription': 'Routine checkup and root canal',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Khaled Ahmed',
                        'patientNationalId': '525400222211111',
                        'treatmentTitle': None,
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'items': [
                            {
                                'code': None,
                                'description': 'Root canal',
                                'quantity': 1,
                                'unitPrice': '3500.00',
                                'total': '3500.00'
                            },
                        ],
                        'subtotal': '3500.00',
                        'tax': '0.00',
                        'discount': '150.00',
                        'total': '3350.00',
                        'currency': 'USD',
                        'status': 'submitted',
                        'issuedAt': None,
                        'submittedAt': '2026-04-24T23:33:54.610Z',
                        'createdBy': 'Dr. Nour Hassan',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'isDeleted': False,
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                'links': {
                    'next': 'https://dtbackend.site/api/invoices/?page=3',
                    'previous': 'https://dtbackend.site/api/invoices/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': True,
                        'view.transactions': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': True,
                        'view.settings': True,
                        'view.invoices': True,
                        'create.invoice': True,
                        'update.invoice': True,
                        'delete.invoice': True
                    }
                }
            }
        ),
    ]
)


#Retrieve invoices schema
retrieve_invoice_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            response_only=True,
            description='Response without snapshot fields for non-admin users.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'invoiceNumber': 'INV-2026-0001',
                    'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'patientNationalId': '525400222211100',
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'items': [
                        {
                            'code': None,
                            'description': 'Root canal',
                            'quantity': 1,
                            'unitPrice': '3500.00',
                            'total': '3500.00'
                        },
                        {
                            'code': 'D3330',
                            'description': 'Dental Bridge (3-unit)',
                            'quantity': 3,
                            'unitPrice': '520.00',
                            'total': '1560.00'
                        }
                    ],
                    'subtotal': '5060.00',
                    'tax': '50.00',
                    'discount': '210.00',
                    'total': '4900.00',
                    'currency': 'USD',
                    'status': 'issued',
                    'issuedAt': '2026-04-24T23:33:54.610Z',
                    'submittedAt': None,
                    'createdAt': '2026-04-24T23:33:54.610Z',
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.invoices': False,
                        'create.invoice': True,
                        'update.invoice': False,
                        'delete.invoice': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes snapshot fields, procedures, and isDeleted flag.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'invoiceNumber': 'INV-2026-0001',
                    'billId': 'd4e5f6a7-4567-8901-defa-4567890123de',
                    'billDescription': 'Full mouth rehabilitation - Session 1',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'patientNationalId': '525400222211100',
                    'treatmentTitle': 'Full Mouth Rehabilitation',
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'branchName': 'Main Branch',
                    'items': [
                        {
                            'code': None,
                            'description': 'Root canal',
                            'quantity': 1,
                            'unitPrice': '3500.00',
                            'total': '3500.00'
                        },
                        {
                            'code': 'D3330',
                            'description': 'Dental Bridge (3-unit)',
                            'quantity': 3,
                            'unitPrice': '520.00',
                            'total': '1560.00'
                        }
                    ],
                    'subtotal': '5060.00',
                    'tax': '50.00',
                    'discount': '210.00',
                    'total': '4900.00',
                    'currency': 'USD',
                    'status': 'issued',
                    'issuedAt': '2026-04-24T23:33:54.610Z',
                    'submittedAt': None,
                    'createdBy': 'Dr. Layla Hassan',
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'isDeleted': False,
                },
                'metadata': {
                    'userPermissions': {
                        'view.calendar': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': True,
                        'view.transactions': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': True,
                        'view.settings': True,
                        'view.invoices': True,
                        'create.invoice': True,
                        'update.invoice': True,
                        'delete.invoice': True
                    }
                }
            }
        ),
    ]
)


#Schema for invoices options serializer
invoices_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description=(
                'Assign `branchId` to filter bill and patient choices by branch, '
                'and assign `doctorId` to filter bill and patient choices by `dentist` user.'
                'Empty query parameters return all choices across the system.'
            ),
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'billChoices': [
                    {'billId': 'd4e5f6a7-4567-8901-defa-4567890123de'},
                    {'billId': 'd5f5f6b7-4567-8901-aeca-7912190321da'}
                ],
                'patientChoices': [
                    {'patientId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3', 'name': 'Ahmed Khaled'},
                    {'patientId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4', 'name': 'Khaled Ahmed'},
                ],
                'invoiceStatusChoices': [
                    {'value': 'issued', 'label': 'Issued'},
                    {'value': 'submitted', 'label': 'Submitted'},
                    {'value': 'accepted', 'label': 'Accepted'},
                    {'value': 'rejected', 'label': 'Rejected'},
                ],
                'taxCodeChoices': [
                    {'value': 'D0120', 'label': 'D0120'},
                    {'value': 'D0210', 'label': 'D0210'},
                    {'value': 'D0330', 'label': 'D0330'},
                    {'value': 'D#', 'label': 'D#'},
                    {'value': 'other', 'label': 'Other'},
                ]
            }
        )
    ]
) 


#Schema for insurance providers options serializer
insurance_providers_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'tierChoices': [
                    {'value': 'government', 'label': 'Government'},
                    {'value': 'universal', 'label': 'Universal'},
                    {'value': 'corporate', 'label': 'Corporate'},
                    {'value': 'direct', 'label': 'Direct'},
                ],
            }
        )
    ]
) 