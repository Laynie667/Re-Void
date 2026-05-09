from django.db import models


class NewsPost(models.Model):
    """A news/announcement post shown on the homepage."""

    title = models.CharField(max_length=200)
    date = models.DateField()
    body = models.TextField(
        help_text="Supports basic HTML (bold, italic, links, etc.)"
    )
    published = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this post without deleting it."
    )

    class Meta:
        app_label = "news"
        ordering = ["-date", "-pk"]
        verbose_name = "News Post"
        verbose_name_plural = "News Posts"

    def __str__(self):
        return f"{self.date} — {self.title}"
