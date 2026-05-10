"""
web/forum/models.py

Forum models for Re:Void.

Tables:
    ForumCategory  — board sections (Announcements, General OOC, etc.)
    ForumThread    — individual threads within a category
    ForumPost      — replies within a thread
"""

from django.db import models


class ForumCategory(models.Model):
    name             = models.CharField(max_length=100)
    slug             = models.SlugField(unique=True)
    description      = models.CharField(max_length=300, blank=True)
    icon             = models.CharField(max_length=10, default="✦")
    staff_only_post  = models.BooleanField(
        default=False,
        help_text="Only staff may create threads or reply in this category.",
    )
    order            = models.PositiveIntegerField(default=0)

    class Meta:
        ordering        = ["order"]
        verbose_name    = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def thread_count(self):
        return self.threads.count()

    def post_count(self):
        return ForumPost.objects.filter(
            thread__category=self, is_deleted=False
        ).count()

    def latest_post(self):
        """Most recent post across all threads in this category."""
        return (
            ForumPost.objects
            .filter(thread__category=self, is_deleted=False)
            .order_by("-created_at")
            .first()
        )


class ForumThread(models.Model):
    category         = models.ForeignKey(
        ForumCategory, on_delete=models.CASCADE, related_name="threads"
    )
    title            = models.CharField(max_length=200)
    author_account_id = models.IntegerField()
    author_name      = models.CharField(max_length=80)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    pinned           = models.BooleanField(default=False)
    locked           = models.BooleanField(default=False)

    class Meta:
        ordering = ["-pinned", "-updated_at"]

    def __str__(self):
        return self.title

    def reply_count(self):
        """Number of posts after the first (the OP)."""
        count = self.posts.filter(is_deleted=False).count()
        return max(0, count - 1)

    def first_post(self):
        return self.posts.filter(is_deleted=False).order_by("created_at").first()

    def latest_post(self):
        return self.posts.filter(is_deleted=False).order_by("-created_at").first()


class ForumPost(models.Model):
    thread           = models.ForeignKey(
        ForumThread, on_delete=models.CASCADE, related_name="posts"
    )
    author_account_id = models.IntegerField()
    author_name      = models.CharField(max_length=80)
    body             = models.TextField()
    created_at       = models.DateTimeField(auto_now_add=True)
    edited_at        = models.DateTimeField(null=True, blank=True)
    is_deleted       = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Post by {self.author_name} in '{self.thread.title}'"
