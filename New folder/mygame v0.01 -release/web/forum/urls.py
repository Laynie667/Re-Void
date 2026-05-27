"""
web/forum/urls.py
"""

from django.urls import path

from . import views

urlpatterns = [
    path("",                        views.ForumIndexView.as_view(),  name="forum-index"),
    path("<slug:slug>/",            views.CategoryView.as_view(),    name="forum-category"),
    path("<slug:slug>/new/",        views.NewThreadView.as_view(),   name="forum-new-thread"),
    path("thread/<int:pk>/",        views.ThreadView.as_view(),      name="forum-thread"),
    path("post/<int:pk>/edit/",     views.EditPostView.as_view(),    name="forum-edit-post"),
    path("post/<int:pk>/delete/",   views.DeletePostView.as_view(),  name="forum-delete-post"),
]
