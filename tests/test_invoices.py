import re
import uuid
import pytest
from decimal import Decimal
from django.urls import reverse
from time import sleep
from rest_framework import status
from finances.models import Invoice, InvoiceItem


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def invoice_factory(patient_factory):
    """
    Creates Invoice instances via the ORM. Always adds one InvoiceItem so
    the instance is realistic for retrieve/update tests.
    Override any field; pass add_items=False to skip item creation.
    """
    def _create(**overrides):
        patient   = overrides.pop('patient', None) or patient_factory()
        add_items = overrides.pop('add_items', True)
        defaults  = {
            'patient':  patient,
            'subtotal': Decimal('200.00'),
            'total':    Decimal('200.00'),
            'discount': Decimal('0.00'),
            'tax':      Decimal('0.00'),
            'status':   'issued',
        }
        defaults.update(overrides)
        invoice = Invoice.objects.create(**defaults)
        if add_items:
            InvoiceItem.objects.create(
                invoice=invoice,
                description='Test Item',
                unitPrice=Decimal('200.00'),
                total=Decimal('200.00'),
                quantity=1,
            )
        return invoice

    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _invoice_url(invoice_id):
    return reverse('retrieve_update_delete_invoice', kwargs={'id': invoice_id})

def _create_payload(patient, **overrides):
    """Minimal valid create payload with one item."""
    base = {
        'patientId': str(patient.id),
        'items':     [{'description': 'Checkup', 'unitPrice': '200.00', 'quantity': 1}],
        'subtotal':  '200.00',
        'currency':  '$',
        'branchId':  None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /invoices/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateInvoicesAPIView:
    LIST_URL = 'list_create_invoices'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_invoices_including_deleted(
        self, api_client, admin_user, invoice_factory
    ):
        """Admin get_queryset uses Invoice.all_objects."""
        invoice = invoice_factory()
        invoice.isDeleted = True
        invoice.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK
        assert str(invoice.id) in [str(i['id']) for i in response.data['data']]

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, invoice_factory
    ):
        invoice_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data

    def test_soft_deleted_invoices_hidden_from_non_admin(
        self, api_client, user_factory, invoice_factory, branch_factory
    ):
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        invoice = invoice_factory(branch=b)
        invoice.isDeleted = True
        invoice.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=accountant)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(invoice.id) not in [str(i['id']) for i in response.data['data']]

    def test_dentist_sees_own_patients_or_created_by_invoices(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        invoice_factory
    ):
        """Dentist filter: patient__doctor=user OR createdBy=user.name."""
        p_own   = patient_factory(doctor=dentist_user)
        p_other = patient_factory(doctor=other_dentist_user)
        inv_own   = invoice_factory(patient=p_own)
        inv_other = invoice_factory(patient=p_other)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(i['id']) for i in response.data['data']]
        assert str(inv_own.id) in ids
        assert str(inv_other.id) not in ids

    def test_receptionist_without_view_invoices_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist default permissions do not include 'view.invoices'."""
        api_client.force_authenticate(user=receptionist_user)
        assert api_client.get(reverse(self.LIST_URL)).status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self, api_client):
        assert api_client.get(reverse(self.LIST_URL)).status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_invoice(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Invoice.objects.filter(patient=patient).exists()

    def test_admin_create_auto_sets_status_to_issued_and_records_issued_at(
        self, api_client, admin_user, patient_factory
    ):
        """CreateInvoiceSerializer.validate(): admin → status='issued'. save() sets issuedAt."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        invoice = Invoice.objects.get(patient=patient)
        assert invoice.status == Invoice.InvoiceStatusChoices.ISSUED
        assert invoice.issuedAt is not None

    def test_non_admin_create_auto_sets_status_to_submitted(
        self, api_client, user_factory, patient_factory
    ):
        """CreateInvoiceSerializer.validate(): non-admin → status='submitted'. save() sets submittedAt."""
        accountant = user_factory(role='accountant')
        patient = patient_factory()
        api_client.force_authenticate(user=accountant)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        invoice = Invoice.objects.get(patient=patient)
        assert invoice.status == Invoice.InvoiceStatusChoices.SUBMITTED
        assert invoice.submittedAt is not None

    def test_create_auto_generates_invoice_number(
        self, api_client, admin_user, patient_factory
    ):
        """Invoice.save(): invoiceNumber = invoice-{YYYY}-{count zero-padded to 5 digits}."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        invoice = Invoice.objects.get(patient=patient)
        assert re.match(r'^INV-\d{4}-\d{5}$', invoice.invoiceNumber)

    def test_create_sets_snapshot_fields(
        self, api_client, admin_user, patient_factory, branch
    ):
        """Invoice.save(): patientName and branchName captured on creation."""
        patient = patient_factory(name='Invoice Patient')
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, branchId=str(branch.id)),
            format='json',
        )

        invoice = Invoice.objects.get(patient=patient)
        assert invoice.patientName == 'Invoice Patient'
        assert invoice.branchName == branch.name
        assert invoice.createdBy == admin_user.name

    def test_create_recalculates_subtotal_from_items(
        self, api_client, admin_user, patient_factory
    ):
        """validate(): subtotal is recalculated from sum of item totals, not the client value."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(
                patient,
                items=[{'unitPrice': '150.00', 'quantity': 2}],
                subtotal='999.00',    # wrong; validate() recalculates to 300
            ),
            format='json',
        )

        invoice = Invoice.objects.get(patient=patient)
        assert invoice.subtotal == Decimal('300.00')

    def test_create_with_discount_exceeding_subtotal_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, 
                            items=[{'description': 'Follow up', 'unitPrice': '100.00', 'quantity': 1}],
                            subtotal='100.00',
                            discount='150.00'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_items_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """items is required, allow_empty=False."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {**_create_payload(patient), 'items': []},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_branch_id_key_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """branchId is required=True; omitting the key entirely → 400."""
        patient = patient_factory()
        payload = _create_payload(patient)
        payload.pop('branchId')
        
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patient_auto_assigned_from_bill_when_no_patient_id(
        self, api_client, admin_user, bill_factory
    ):
        """validate(): if bill provided and no patientId → patient = bill.patient."""
        bill = bill_factory()
        payload = {
            'billId':   str(bill.id),
            'branchId': None,
            'items':    [{'description': 'Crown', 'unitPrice': '500.00', 'quantity': 1}],
            'subtotal': '500.00',
            'currency': '$',
            # no patientId
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        invoice = Invoice.objects.get(bill=bill)
        assert invoice.patient == bill.patient

    def test_user_with_create_invoice_permission_can_create(
        self, api_client, receptionist_user, patient_factory
    ):
        """receptionist has 'create.invoice' by default."""
        patient = patient_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_response_is_wrapped(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /invoices/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteInvoiceAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_invoice(
        self, api_client, admin_user, invoice_factory
    ):
        invoice = invoice_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_invoice_url(invoice.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['id'] == str(invoice.id)

    def test_retrieve_response_includes_metadata(
        self, api_client, admin_user, invoice_factory
    ):
        """RetrieveInvoiceSerializer inherits UserPermissionsMixin → metadata on GET."""
        invoice = invoice_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_invoice_url(invoice.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_admin_sees_snapshot_fields_non_admin_does_not(
        self, api_client, admin_user, user_factory, invoice_factory, branch_factory
    ):
        """InvoiceSerializer.get_fields() strips snapshot fields for non-admins."""
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        invoice = invoice_factory(branch=b, createdBy='Someone', branchName=b.name)

        api_client.force_authenticate(user=admin_user)
        admin_resp = api_client.get(_invoice_url(invoice.id))
        for field in ('billDescription', 'branchName', 'createdBy', 'isDeleted'):
            assert field in admin_resp.data['data'], f"Admin should see '{field}'"

        api_client.force_authenticate(user=accountant)
        acc_resp = api_client.get(_invoice_url(invoice.id))
        for field in ('billDescription', 'branchName', 'createdBy', 'isDeleted'):
            assert field not in acc_resp.data['data'], f"Non-admin must NOT see '{field}'"

    def test_admin_can_retrieve_soft_deleted_invoice(
        self, api_client, admin_user, invoice_factory
    ):
        """Admin get_queryset uses all_objects; soft-deleted invoices are visible."""
        invoice = invoice_factory()
        invoice.isDeleted = True
        invoice.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        assert api_client.get(_invoice_url(invoice.id)).status_code == status.HTTP_200_OK

    def test_non_admin_cannot_retrieve_soft_deleted_invoice(
        self, api_client, user_factory, invoice_factory, branch_factory
    ):
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        invoice = invoice_factory(branch=b)
        invoice.isDeleted = True
        invoice.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=accountant)
        assert api_client.get(_invoice_url(invoice.id)).status_code == status.HTTP_404_NOT_FOUND

    # ── UPDATE – PATCH (status only) ──────────────────────────────────────────

    def test_admin_can_patch_invoice_status(
        self, api_client, admin_user, invoice_factory
    ):
        invoice = invoice_factory(status='submitted')
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _invoice_url(invoice.id), {'status': 'accepted'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        invoice.refresh_from_db()
        assert invoice.status == Invoice.InvoiceStatusChoices.ACCEPTED

    def test_patch_status_issued_auto_sets_issued_at(
        self, api_client, admin_user, invoice_factory
    ):
        """UpdateInvoiceStatusSerializer.validate(): status=issued + no issuedAt → sets it."""
        invoice = invoice_factory(status='submitted')
        api_client.force_authenticate(user=admin_user)
        api_client.patch(_invoice_url(invoice.id), {'status': 'issued'}, format='json')

        invoice.refresh_from_db()
        assert invoice.issuedAt is not None

    def test_patch_status_submitted_sets_submitted_at_via_model_save(
        self, api_client, admin_user, invoice_factory
    ):
        """
        Invoice.save(): status == 'submitted' → submittedAt = now().
        """
        invoice = invoice_factory(status='issued')
        api_client.force_authenticate(user=admin_user)
        api_client.patch(_invoice_url(invoice.id), {'status': 'submitted'}, format='json')

        invoice.refresh_from_db()
        assert invoice.submittedAt is not None

    def test_patch_cannot_update_subtotal_or_items(
        self, api_client, admin_user, invoice_factory
    ):
        """UpdateInvoiceStatusSerializer only exposes status/issuedAt/submittedAt."""
        invoice = invoice_factory()
        original_subtotal = invoice.subtotal
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _invoice_url(invoice.id),
            {'status': 'accepted', 'subtotal': '999.00'},
            format='json',
        )

        invoice.refresh_from_db()
        assert invoice.subtotal == original_subtotal   # unchanged

    # ── UPDATE – PUT (full update) ─────────────────────────────────────────────

    def test_admin_can_full_update_invoice_via_put(
        self, api_client, admin_user, invoice_factory
    ):
        invoice = invoice_factory()
        payload = {
            'items':    [{'description': 'Crown', 'unitPrice': '500.00', 'quantity': 1}],
            'subtotal': '500.00',
            'currency': 'EGP',
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(_invoice_url(invoice.id), payload, format='json')

        assert response.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.subtotal == Decimal('500.00')
        assert invoice.currency == 'EGP'
        

    def test_put_replaces_all_invoice_items(
        self, api_client, admin_user, invoice_factory
    ):
        """UpdateInvoiceSerializer.update(): existing items deleted, new ones bulk-created."""
        invoice = invoice_factory()
        assert invoice.invoice_items.count() == 1   #one item from factory

        new_items = [
            {'description': 'Root Canal', 'unitPrice': '300.00', 'quantity': 1},
            {'description': 'Crown',      'unitPrice': '200.00', 'quantity': 1},
        ]
        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _invoice_url(invoice.id),
            {'items': new_items, 'subtotal': '500.00'},
            format='json',
        )

        invoice.refresh_from_db()
        assert invoice.invoice_items.count() == 2  #now two items after full update
        descriptions = set(invoice.invoice_items.values_list('description', flat=True))
        assert descriptions == {'Root Canal', 'Crown'}

    def test_submittedAt_is_updated_when_put_updates_status_with_submitted(
        self, api_client, admin_user, invoice_factory
    ):
        invoice = invoice_factory(status='submitted')
        submittedAt_before = invoice.submittedAt

        payload = {
            'items':    [{'description': 'Crown', 'unitPrice': '500.00', 'quantity': 1}],
            'subtotal': '500.00',
            'status': 'submitted',
            'currency': 'EGP',
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(_invoice_url(invoice.id), payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        invoice.refresh_from_db()
        submittedAt_after = invoice.submittedAt
        assert invoice.status == 'submitted'
        assert submittedAt_before != submittedAt_after
        
    def test_put_patient_bill_and_branch_are_read_only(
        self, api_client, admin_user, invoice_factory, patient_factory, bill_factory
    ):
        """UpdateInvoiceSerializer: billId, patientId, branchId all in read_only_fields."""
        invoice = invoice_factory()
        other_bill = bill_factory()
        other_patient = patient_factory()

        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _invoice_url(invoice.id),
            {   
                'billId': str(other_bill.id),
                'patientId': str(other_patient.id),
                'items':     [{'description': 'Test', 'unitPrice': '100.00', 'quantity': 1}],
                'subtotal':  '100.00',
            },
            format='json',
        )

        invoice.refresh_from_db()
        assert invoice.patient != other_patient  #unchanged

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_invoice(
        self, api_client, admin_user, invoice_factory
    ):
        invoice = invoice_factory()
        iid = invoice.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_invoice_url(iid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Invoice.objects.filter(id=iid).exists()
        assert not Invoice.all_objects.filter(id=iid).exists()

    def test_non_admin_with_delete_permission_soft_deletes_invoice(
        self, api_client, user_factory, invoice_factory, branch_factory
    ):
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        invoice = invoice_factory(branch=b)
        iid = invoice.id

        api_client.force_authenticate(user=accountant)
        response = api_client.delete(_invoice_url(iid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Invoice.objects.filter(id=iid).exists()
        deleted = Invoice.all_objects.get(id=iid)
        assert deleted.isDeleted is True

    def test_unauthenticated_cannot_delete(self, api_client, invoice_factory):
        invoice = invoice_factory()
        assert api_client.delete(_invoice_url(invoice.id)).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# GET  /invoices/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveInvoicesOptionsAPIView:
    """Plain generics.GenericAPIView + BranchToSerializerMixin. No ResponseMixin."""
    URL = 'invoices_options'

    def test_authenticated_user_gets_options_payload(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        for key in ('branchChoices', 'billChoices', 'patientChoices',
                    'invoiceStatusChoices', 'taxCodeChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert 'success' not in api_client.get(reverse(self.URL)).data

    def test_invoice_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['invoiceStatusChoices']}
        expected = {c.value for c in Invoice.InvoiceStatusChoices}
        assert returned == expected

    def test_tax_code_choices_are_non_empty_and_have_value_label(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        codes = response.data['taxCodeChoices']
        assert len(codes) > 0
        for c in codes:
            assert 'value' in c and 'label' in c

    def test_patient_choices_filtered_by_branch_id(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        p1 = patient_factory(branch=b1)
        p2 = patient_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p1.id) in patient_ids
        assert str(p2.id) not in patient_ids

    def test_invalid_doctor_id_returns_400(self, api_client, admin_user):
        """get_serializer_context validates doctorId must be dentist or admin."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        assert api_client.get(reverse(self.URL)).status_code == status.HTTP_401_UNAUTHORIZED