"""
web/mail/views.py

Website mailbox for the Ogram system.

Views:
    InboxView        — /mail/inbox/
    OutboxView       — /mail/outbox/
    ComposeView      — /mail/compose/
    MessageDetailView — /mail/<pk>/
    DeleteView       — /mail/<pk>/delete/
    StaffContactView — /contact/

All mail views require login. Staff contact is open to all.
"""

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, FormView, View
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.contrib import messages

from .models import OgramMessage
from .forms import ComposeForm, StaffContactForm


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _char_ids_for_account(account):
    """Return a list of ObjectDB pk values for all of account's characters."""
    try:
        return [c.id for c in account.characters.all()]
    except Exception:
        return []


def _resolve_recipient(name):
    """
    Look up a character by (rp_)name. Returns the ObjectDB instance or None.
    """
    try:
        from evennia import search_object
        results = search_object(
            name,
            typeclass="typeclasses.characters.Character",
        )
        if results:
            return results[0]
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ #
# Inbox
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class InboxView(ListView):
    template_name = "website/mail/inbox.html"
    context_object_name = "messages_list"
    paginate_by = 20

    def get_queryset(self):
        char_ids = _char_ids_for_account(self.request.user)
        return OgramMessage.objects.filter(
            recipient_object_id__in=char_ids,
            deleted_by_recipient=False,
        ).order_by("-sent_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        char_ids = _char_ids_for_account(self.request.user)
        ctx["unread_count"] = OgramMessage.objects.filter(
            recipient_object_id__in=char_ids,
            deleted_by_recipient=False,
            read_at__isnull=True,
        ).count()
        ctx["view_tab"] = "inbox"
        return ctx


# ------------------------------------------------------------------ #
# Outbox
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class OutboxView(ListView):
    template_name = "website/mail/outbox.html"
    context_object_name = "messages_list"
    paginate_by = 20

    def get_queryset(self):
        return OgramMessage.objects.filter(
            sender_account_id=self.request.user.id,
            deleted_by_sender=False,
        ).order_by("-sent_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["view_tab"] = "outbox"
        return ctx


# ------------------------------------------------------------------ #
# Message detail
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class MessageDetailView(DetailView):
    template_name = "website/mail/message_detail.html"
    context_object_name = "ogram"

    def get_object(self):
        pk = self.kwargs["pk"]
        user = self.request.user
        char_ids = _char_ids_for_account(user)

        msg = get_object_or_404(OgramMessage, pk=pk)

        # Check access: must be sender or recipient
        is_recipient = msg.recipient_object_id in char_ids
        is_sender    = msg.sender_account_id == user.id

        if not (is_recipient or is_sender):
            from django.http import Http404
            raise Http404

        # Mark as read if recipient is viewing
        if is_recipient and msg.read_at is None:
            msg.read_at = timezone.now()
            msg.save(update_fields=["read_at"])

        return msg

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        char_ids = _char_ids_for_account(user)
        msg = ctx["ogram"]
        ctx["is_recipient"] = msg.recipient_object_id in char_ids
        ctx["is_sender"]    = msg.sender_account_id == user.id
        return ctx


# ------------------------------------------------------------------ #
# Delete
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class DeleteMessageView(View):
    def post(self, request, pk):
        user = request.user
        char_ids = _char_ids_for_account(user)
        msg = get_object_or_404(OgramMessage, pk=pk)

        is_recipient = msg.recipient_object_id in char_ids
        is_sender    = msg.sender_account_id == user.id

        if not (is_recipient or is_sender):
            from django.http import Http404
            raise Http404

        if is_recipient:
            msg.deleted_by_recipient = True
        if is_sender:
            msg.deleted_by_sender = True
        msg.save()

        messages.success(request, "Ogram removed from your mailbox.")

        # Return to wherever the user came from
        next_url = request.POST.get("next", reverse("mail-inbox"))
        return redirect(next_url)


# ------------------------------------------------------------------ #
# Compose
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class ComposeView(FormView):
    template_name = "website/mail/compose.html"
    form_class    = ComposeForm
    success_url   = reverse_lazy("mail-outbox")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["view_tab"] = "compose"
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        user = self.request.user

        # Resolve recipient character
        target = _resolve_recipient(data["recipient"])
        if not target:
            form.add_error(
                "recipient",
                f"No character found named '{data['recipient']}'.",
            )
            return self.form_invalid(form)

        target_account = getattr(target, "account", None)

        # Get sender's first character (or fallback to account name)
        sender_chars = list(user.characters.all())
        if sender_chars:
            sender_char = sender_chars[0]
            sender_name = sender_char.db.rp_name or sender_char.key
            sender_object_id = sender_char.id
        else:
            sender_name = user.username
            sender_object_id = None

        msg = OgramMessage(
            sender_object_id     = sender_object_id,
            sender_name          = sender_name,
            sender_account_id    = user.id,
            anonymous            = data.get("anonymous", False),
            recipient_object_id  = target.id,
            recipient_name       = target.db.rp_name or target.key,
            recipient_account_id = target_account.id if target_account else None,
            msg_type             = data["msg_type"],
            affection_type       = data.get("affection_type", ""),
            messenger_gender     = data["messenger_gender"],
            subject              = data.get("subject", ""),
            body                 = data.get("body", "").strip(),
        )
        msg.save()

        messages.success(
            self.request,
            f"Your Ogram to {msg.recipient_name} has been sealed and queued for delivery.",
        )
        return super().form_valid(form)


# ------------------------------------------------------------------ #
# Staff contact
# ------------------------------------------------------------------ #

class StaffContactView(FormView):
    template_name = "website/mail/staff_contact.html"
    form_class    = StaffContactForm
    success_url   = reverse_lazy("contact-thanks")

    def form_valid(self, form):
        data = form.cleaned_data
        user = self.request.user if self.request.user.is_authenticated else None

        # Route to a designated staff account / character called "Staff"
        # Falls back to storing with recipient_name="Staff" if not found.
        staff_target = _resolve_recipient("Staff")
        staff_account = getattr(staff_target, "account", None) if staff_target else None

        # Try to find any staff account to use as fallback recipient
        if not staff_account:
            try:
                from evennia.accounts.models import AccountDB
                staff_account = AccountDB.objects.filter(
                    is_staff=True
                ).first()
            except Exception:
                pass

        msg = OgramMessage(
            sender_name          = data["name"],
            sender_email         = data.get("email", ""),
            sender_account_id    = user.id if user else None,
            anonymous            = False,
            recipient_name       = "Staff",
            recipient_account_id = staff_account.id if staff_account else None,
            msg_type             = "staff",
            subject              = data["subject"],
            body                 = data["body"],
        )
        msg.save()

        return super().form_valid(form)
