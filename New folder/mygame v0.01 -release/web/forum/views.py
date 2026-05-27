"""
web/forum/views.py

Views:
    ForumIndexView   — /forums/
    CategoryView     — /forums/<slug>/
    ThreadView       — /forums/thread/<pk>/
    NewThreadView    — /forums/<slug>/new/
    EditPostView     — /forums/post/<pk>/edit/
    DeletePostView   — /forums/post/<pk>/delete/
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, FormView, View

from .forms import EditPostForm, NewThreadForm, ReplyForm
from .models import ForumCategory, ForumPost, ForumThread


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _author_name(user):
    """Best display name for the logged-in user."""
    try:
        chars = list(user.characters.all())
        if chars:
            return chars[0].db.rp_name or chars[0].key
    except Exception:
        pass
    return user.username


def _can_post(user, category):
    """Return True if this user may create threads / reply in category."""
    if category.staff_only_post:
        return user.is_authenticated and user.is_staff
    return user.is_authenticated


# ------------------------------------------------------------------ #
# Forum index
# ------------------------------------------------------------------ #

class ForumIndexView(ListView):
    template_name      = "website/forum/index.html"
    context_object_name = "categories"

    def get_queryset(self):
        return ForumCategory.objects.order_by("order")


# ------------------------------------------------------------------ #
# Category (thread list)
# ------------------------------------------------------------------ #

class CategoryView(DetailView):
    template_name      = "website/forum/category.html"
    context_object_name = "category"

    def get_object(self):
        return get_object_or_404(ForumCategory, slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        ctx      = super().get_context_data(**kwargs)
        category = ctx["category"]
        ctx["threads"]  = category.threads.order_by("-pinned", "-updated_at")
        ctx["can_post"] = _can_post(self.request.user, category)
        return ctx


# ------------------------------------------------------------------ #
# Thread (post list + reply)
# ------------------------------------------------------------------ #

class ThreadView(View):
    template_name = "website/forum/thread.html"

    def _get_thread(self, pk):
        return get_object_or_404(ForumThread, pk=pk)

    def _ctx(self, request, thread, form=None):
        from django.template.response import TemplateResponse
        can_post   = _can_post(request.user, thread.category)
        user_id    = request.user.id if request.user.is_authenticated else None
        posts      = thread.posts.filter(is_deleted=False)
        return TemplateResponse(request, self.template_name, {
            "thread":   thread,
            "posts":    posts,
            "form":     form or ReplyForm(),
            "can_post": can_post and not thread.locked,
            "user_id":  user_id,
            "is_staff": request.user.is_authenticated and request.user.is_staff,
        })

    def get(self, request, pk):
        thread = self._get_thread(pk)
        return self._ctx(request, thread)

    def post(self, request, pk):
        thread = self._get_thread(pk)

        if not request.user.is_authenticated:
            return redirect("login")

        if not _can_post(request.user, thread.category):
            messages.error(request, "You don't have permission to post here.")
            return redirect("forum-thread", pk=pk)

        if thread.locked and not request.user.is_staff:
            messages.error(request, "This thread is locked.")
            return redirect("forum-thread", pk=pk)

        form = ReplyForm(request.POST)
        if form.is_valid():
            ForumPost.objects.create(
                thread            = thread,
                author_account_id = request.user.id,
                author_name       = _author_name(request.user),
                body              = form.cleaned_data["body"].strip(),
            )
            # Touch thread.updated_at so it floats to the top
            ForumThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
            return redirect("forum-thread", pk=pk)

        return self._ctx(request, thread, form)


# ------------------------------------------------------------------ #
# New thread
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class NewThreadView(FormView):
    template_name = "website/forum/new_thread.html"
    form_class    = NewThreadForm

    def _get_category(self):
        return get_object_or_404(ForumCategory, slug=self.kwargs["slug"])

    def dispatch(self, request, *args, **kwargs):
        self.category = self._get_category()
        if not _can_post(request.user, self.category):
            messages.error(request, "You don't have permission to post in this category.")
            return redirect("forum-category", slug=self.category.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.category
        return ctx

    def form_valid(self, form):
        data   = form.cleaned_data
        thread = ForumThread.objects.create(
            category          = self.category,
            title             = data["title"].strip(),
            author_account_id = self.request.user.id,
            author_name       = _author_name(self.request.user),
        )
        ForumPost.objects.create(
            thread            = thread,
            author_account_id = self.request.user.id,
            author_name       = _author_name(self.request.user),
            body              = data["body"].strip(),
        )
        return redirect("forum-thread", pk=thread.pk)


# ------------------------------------------------------------------ #
# Edit post
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class EditPostView(View):
    template_name = "website/forum/edit_post.html"

    def _get_post(self, request, pk):
        post = get_object_or_404(ForumPost, pk=pk, is_deleted=False)
        if post.author_account_id != request.user.id and not request.user.is_staff:
            raise Http404
        return post

    def get(self, request, pk):
        from django.template.response import TemplateResponse
        post = self._get_post(request, pk)
        return TemplateResponse(request, self.template_name, {
            "post": post,
            "form": EditPostForm(initial={"body": post.body}),
        })

    def post(self, request, pk):
        post = self._get_post(request, pk)
        form = EditPostForm(request.POST)
        if form.is_valid():
            post.body      = form.cleaned_data["body"].strip()
            post.edited_at = timezone.now()
            post.save()
            return redirect("forum-thread", pk=post.thread_id)
        from django.template.response import TemplateResponse
        return TemplateResponse(request, self.template_name, {"post": post, "form": form})


# ------------------------------------------------------------------ #
# Delete post
# ------------------------------------------------------------------ #

@method_decorator(login_required, name="dispatch")
class DeletePostView(View):
    def post(self, request, pk):
        post = get_object_or_404(ForumPost, pk=pk, is_deleted=False)
        if post.author_account_id != request.user.id and not request.user.is_staff:
            raise Http404

        thread = post.thread

        # If this is the only post, delete the whole thread
        surviving = thread.posts.filter(is_deleted=False).count()
        if surviving <= 1:
            thread.delete()
            messages.success(request, "Thread deleted.")
            return redirect("forum-category", slug=thread.category.slug)

        post.is_deleted = True
        post.save()
        messages.success(request, "Post removed.")
        return redirect("forum-thread", pk=thread.pk)
