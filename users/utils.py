
from users.models import User

#Dict for identifying category patterns 
category_patterns = {
    r'/treatment-plans/': 'treatment-plans',
    r'/visits/': 'visits', 
    r'/patients/': 'patients',
    r'/appointments/': 'appointments',
    r'/procedures/': 'procedures',
    r'/bills/': 'bills',
    r'/transactions/': 'transactions',
    r'invoices/': 'invoices',
    r'/inventory/': 'inventory',
    r'/lab-orders/': 'lab-orders',
    r'/labs/': 'labs',
    r'recalls': 'patient-recalls',
    r'sterilization/': 'sterilization-logs',
}

#Custom function for identifying permission category
def get_category_from_url(request):
    '''Helper function to extract permission category from URL path'''
    for pattern, category in category_patterns.items():
        if pattern in request.path:
            return category
    return None


#Helper functions for looking up user permissions
def _build_permissions_lookup(permissions_dict):
    '''Helper function to build a lookup dictionary for permissions
        grouped by by category and request method type.'''

    lookup = {}
    for category, permissions in permissions_dict.items():
        if category == 'sidebar':
            continue
        grouped = {}
        for perm in permissions:
            key = perm.split('.')[0]
            if key in grouped:
                #use list if more than one item is found
                if isinstance(grouped[key], str):
                    grouped[key] = [grouped[key], perm]
                else:
                    grouped[key].append(perm)
            else:
                grouped[key] = perm
        lookup[category] = grouped
    return lookup

    #Output would look like this:
        # {'patients': {
        #   'view': ['view.patients', 'view.patientDetail'],
        #   'create': 'create.patient',
        #   'update': 'update.patient',
        #   'delete': 'delete.patient'
        # },
        #
        # 'visits': {
        #   'view': 'view.visits', 'create': 'create.visit'
        # },
        #
        # 'appointments': {
        #   'view': ['view.appointments', 'view.appointmentDetail'],
        #   'create': 'create.appointment',
        #   'update': 'update.appointment',
        #   'delete': 'delete.appointment',
        #   'send': 'send.whatsappMessage'
        # },
        #
        # 'treatment-plans': {
        #   'view': 'view.treatments',
        #   'create': 'create.treatment',
        #   'update': 'update.treatment',
        #   'delete': 'delete.treatment'
        # },
        #
        # 'procedures': {
        #   'view': 'view.procedures',
        #   'create': 'create.procedure',
        #   'update': 'update.procedure',
        #   'delete': 'delete.procedure'
        # },
        #
        # 'inventory': {
        #   'view': 'view.inventory',
        #   'create': 'create.inventory',
        #   'update': 'update.inventory',
        #   'delete': 'delete.inventory'
        # },
        #
        # 'labs: {
        #   'view': 'view.labs',
        #   'create': 'create.labs',
        #   'update': 'update.labs',
        #   'delete': 'delete.labs'
        # },
        #
        # 'lab-orders: {
        #   'view': ['view.labOrders', 'view.labOrderDetail'],
        #   'create': 'create.labOrder',
        #   'update': 'update.labOrder',
        #   'delete': 'delete.labOrder'
        # },
        #
        # 'bills: {
        #   'view': 'view.bills',
        #   'create': 'create.bill',
        #   'update': 'update.bill',
        #   'delete': 'delete.bill'
        # },
        #
        # 'transactions: {
        #   'view': 'view.transactions',
        #   'create': 'create.transaction',
        #   'delete': 'delete.transaction'
        # },
        #
        # 'invoices: {
        #   'view': 'view.invoices',
        #   'create': 'create.invoice',
        #   'update': 'update.invoice',
        #   'delete': 'delete.invoice'
        # },
        #
        # 'sterilization-logs': {
        #   'view': 'view.sterilizationLogs',
        #   'create': 'create.sterilizationLog',
        #   'update': 'update.sterilizationLog',
        #   'delete': 'delete.sterilizationLog'
        # },
        #
        # 'patient-recalls': {
        #   'view': 'view.recalls',
        #   'create': 'create.recall',
        #   'update': 'update.recall',
        #   'delete': 'delete.recall'
        # },
        #
        # 'doctor-schedules': {
        #   'view': 'view.doctorSchedules'
        # },
        #}

#Get user permissions lookup dictionary 
USER_PERMISSIONS_LOOKUP = _build_permissions_lookup(User.USER_PERMISSIONS_DICT)

#Function to quickly determine required permission
def get_required_permission(category, request, view=None):
    '''
    Determines required permission based on category and request method.\n
    *important*: this function cannot be used with each of:
        * calender
        * doctor-schedules
        * send whatsapp message
        * settings and preferences
    '''

    req_method = request.method
    is_detail = bool(getattr(view, 'lookup_url_kwarg', None))
    perms = USER_PERMISSIONS_LOOKUP[category]

    if req_method == 'GET':
        if isinstance(perms['view'], list):
            return perms['view'][1 if is_detail else 0]
        return perms['view']
    elif req_method in ('PUT', 'PATCH'):
        return perms['update']
    elif req_method == 'POST':
        return perms['create']
    elif req_method == 'DELETE':
        return perms['delete']
    return None 

