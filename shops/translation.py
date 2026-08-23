from modeltranslation.translator import TranslationOptions, register

from .models import Shop


@register(Shop)
class ShopTranslationOptions(TranslationOptions):
    fields = ("name", "description")
