from django.apps import AppConfig


class WebConfig(AppConfig):
    name = "web"
    label = "revoid_web"  # unique label — avoids conflict with evennia.web
