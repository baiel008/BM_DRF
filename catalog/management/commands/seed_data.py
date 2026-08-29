import io
import os
import random
import re

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from PIL import Image

from catalog.models import Brand, Category, Product, ProductImage, WholesaleTier
from shops.models import Shop
from users.models import User


PASTEL = {
    "face": (243, 229, 235),
    "makeup": (252, 228, 214),
    "hair": (219, 229, 250),
    "perfume": (230, 236, 228),
}

# ключ -> изображение на Wikimedia Commons (реальные фото косметики)
IMAGE_MAP = {
    "cream": "File:Face Cream - Profile Img - 2016.jpg",
    "night_cream": "File:Person applies cream for skin from a jar closeup.jpg",
    "serum": "File:Woman applying serum on her face closeup.jpg",
    "toner": 'File:Cosmetics and hygiene products from company "Rituals" in a German warehouse (2023).jpg',
    "perfume_w": "File:Bottle of L'Aimant perfume - Coty -1927-1.jpg",
    "perfume_m": "File:Elizabeth Dimling, Cologne Bottle, 1935-1942, NGA 22785.jpg",
    "foundation": "File:Foundation (cosmetics).jpg",
    "lipstick": "File:Lipstick with veil (1308307).jpg",
    "mascara": "File:Mascara de pestañas.jpg",
    "day_cream": "File:Day cream 02.jpg",
    "shampoo": "File:Dove shampoo bottle in black background.jpg",
    "hair_mask": "File:Hair care products in liter bottles at a workplace of a hair salon, in front of a shelf with hair dyes No.2.jpg",
    "conditioner": "File:Hair shampoos, conditioners and other hair care products in liter bottles for use in hair salon.jpg",
}

# подстрока в названии товара -> ключ картинки
IMAGE_RULES = [
    ("гиалуронов", "cream"), ("Сыворотка", "serum"), ("ретинол", "night_cream"),
    ("Ночной крем", "night_cream"), ("Мист-тоник", "toner"), ("Мицеллярная", "toner"),
    ("Тканевая маска", "cream"), ("Парфюм женский", "perfume_w"), ("Парфюм мужской", "perfume_m"),
    ("Тональный", "foundation"), ("Помада", "lipstick"), ("Тушь", "mascara"),
    ("Крем дневной", "day_cream"), ("Крем от акне", "cream"), ("Шампунь", "shampoo"),
    ("Маска для волос", "hair_mask"), ("Бальзам", "conditioner"),
    ("Крем увлажняющий", "cream"), ("Крем", "cream"),
]

WIKI_API = "https://commons.wikimedia.org/w/api.php"
WIKI_UA = {"User-Agent": "BeautyMarketSeed/1.0 (contact: dev@beauty.kg)"}
SEEDED_DIR = os.path.join(settings.MEDIA_ROOT, "products", "seeded")


def _image_key_for(name):
    for substring, key in IMAGE_RULES:
        if substring in name:
            return key
    return None


def _fetch_thumb(title):
    r = requests.get(
        WIKI_API,
        params={"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 720},
        headers=WIKI_UA,
        timeout=30,
    )
    for _, page in r.json().get("query", {}).get("pages", {}).items():
        info = page.get("imageinfo")
        if info:
            return info[0].get("thumburl")
    return None


def ensure_seeded_images():
    """Скачивает реальные фото с Wikimedia (один раз) в media/products/seeded."""
    os.makedirs(SEEDED_DIR, exist_ok=True)
    for key, title in IMAGE_MAP.items():
        path = os.path.join(SEEDED_DIR, f"{key}.jpg")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            continue
        url = _fetch_thumb(title)
        if not url:
            continue
        r = requests.get(url, headers=WIKI_UA, timeout=60)
        if r.status_code != 200:
            continue
        with open(path, "wb") as f:
            f.write(r.content)


def _placeholder(palette, size=(600, 600)):
    buf = io.BytesIO()
    Image.new("RGB", size, palette).save(buf, "JPEG")
    buf.seek(0)
    return ContentFile(buf.read(), name="product.jpg")


def _seeded_image(product_name, palette):
    """Возвращает реальное фото товара из кэша, либо заглушку."""
    key = _image_key_for(product_name)
    if key:
        path = os.path.join(SEEDED_DIR, f"{key}.jpg")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return ContentFile(f.read(), name=f"{key}.jpg")
    return _placeholder(palette)


class Command(BaseCommand):
    help = "Наполняет базу демо-данными: пользователи, категории, бренды, 3 магазина, товары."

    def _get_or_create_shop(self, email, defaults):
        seller, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": defaults["first_name"],
                "last_name": defaults["last_name"],
                "phone": defaults["phone"],
            },
        )
        seller.set_password("Seller123!")
        seller.is_seller = True
        seller.save()
        shop, _ = Shop.objects.get_or_create(owner=seller, defaults=defaults["shop"])
        return shop

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            email="admin@beauty.kg", defaults={"first_name": "Админ", "is_staff": True, "is_superuser": True}
        )
        admin.set_password("Admin123!")
        admin.save()

        buyer, _ = User.objects.get_or_create(
            email="buyer@beauty.kg", defaults={"first_name": "Айгуль", "last_name": "Сатыбалдиева", "phone": "+996 (700) 111-22-33"}
        )
        buyer.set_password("Buyer123!")
        buyer.save()

        shops = {
            "premium": self._get_or_create_shop(
                "seller@beauty.kg",
                {
                    "first_name": "Анна",
                    "last_name": "Петрова",
                    "phone": "+996 (555) 444-55-66",
                    "shop": {
                        "name": "Maison Beauté",
                        "city": "Бишкек",
                        "address": "пр. Чуй, 154",
                        "phone": "+996 (555) 444-55-66",
                        "email": "shop@maisonbeaute.kg",
                        "description": "Бутик премиальной косметики и ухода для лица. Опт для салонов и студий.",
                    },
                },
            ),
            "makeup": self._get_or_create_shop(
                "maski@beauty.kg",
                {
                    "first_name": "Гульмира",
                    "last_name": "Асанова",
                    "phone": "+996 (777) 222-33-44",
                    "shop": {
                        "name": "ColorLab",
                        "city": "Ош",
                        "address": "ул. Курманжан Датка, 88",
                        "phone": "+996 (777) 222-33-44",
                        "email": "shop@colorlab.kg",
                        "description": "Макияж и уход от масс-маркет до люкса. Быстрая доставка по стране.",
                    },
                },
            ),
            "hair": self._get_or_create_shop(
                "volokno@beauty.kg",
                {
                    "first_name": "Мария",
                    "last_name": "Ибрагимова",
                    "phone": "+996 (555) 908-11-22",
                    "shop": {
                        "name": "Hair Soul",
                        "city": "Бишкек",
                        "address": "ул. Киевская, 95",
                        "phone": "+996 (555) 908-11-22",
                        "email": "shop@hairsoul.kg",
                        "description": "Профессиональный уход за волосами и кожей головы. Бады и витамины для красоты.",
                    },
                },
            ),
        }

        cats = {}
        for parent_name, children in {
            "Уход за лицом": ["Кремы и сыворотки", "Тоники и мисты", "Маски"],
            "Макияж": ["Тональные средства", "Помады", "Тушь и подводки"],
            "Волосы": ["Шампуни", "Маски и бальзамы"],
            "Парфюмерия": ["Женская", "Мужская"],
        }.items():
            parent, _ = Category.objects.get_or_create(
                name=parent_name, parent=None, defaults={"icon": random.choice(["🌸", "💄", "🧴", "✨"]), "is_active": True}
            )
            cats[parent_name] = parent
            for child_name in children:
                Category.objects.get_or_create(name=child_name, parent=parent, defaults={"is_active": True})

        for brand_name in ["Lancôme", "Estée Lauder", "La Roche-Posay", "L'Oréal Paris", "Maybelline", "Yves Rocher", "Garnier"]:
            Brand.objects.get_or_create(name=brand_name, defaults={"is_active": True})

        def leaf_cat(name):
            return Category.objects.get(name=name)

        data = [
            ("Крем увлажняющий с гиалуроновой кислотой", "Уход за лицом", "Кремы и сыворотки", "La Roche-Posay", 2490, 3290, 7, 1490, 6, "50 мл", 42),
            ("Сыворотка с витамином C", "Уход за лицом", "Кремы и сыворотки", "Lancôme", 4890, None, 4, 2990, 4, "30 мл", 18),
            ("Ночной крем с ретинолом", "Уход за лицом", "Кремы и сыворотки", "Estée Lauder", 3990, 4590, 8, 2490, 5, "50 мл", 27),
            ("Мист-тоник с розовой водой", "Уход за лицом", "Тоники и мисты", "Yves Rocher", 890, 1190, 9, None, 0, "150 мл", 61),
            ("Тканевая маска увлажняющая", "Уход за лицом", "Маски", "Garnier", 199, None, 25, 120, 10, "25 г", 130),
            ("Тональный крем стойкий", "Макияж", "Тональные средства", "L'Oréal Paris", 1690, 1990, 6, None, 0, "30 мл", 22),
            ("Помада матовая", "Макияж", "Помады", "Maybelline", 990, None, 12, None, 0, "4.2 г", 84),
            ("Тушь объёмная", "Макияж", "Тушь и подводки", "Maybelline", 890, 1090, 10, None, 0, "10 мл", 93),
            ("Шампунь для объёма", "Волосы", "Шампуни", "L'Oréal Paris", 1290, None, 8, None, 0, "300 мл", 55),
            ("Маска для волос восстанавливающая", "Волосы", "Маски и бальзамы", "Estée Lauder", 2490, 2990, 6, None, 0, "250 мл", 31),
            ("Парфюм женский цветочный", "Парфюмерия", "Женская", "Lancôme", 8990, 9990, 5, 5990, 3, "50 мл", 12),
            ("Парфюм мужской древесный", "Парфюмерия", "Мужская", "L'Oréal Paris", 5990, None, 4, None, 0, "100 мл", 9),
            ("Крем от акне", "Уход за лицом", "Кремы и сыворотки", "La Roche-Posay", 1990, 2390, 9, 1290, 5, "40 мл", 47),
            ("Мицеллярная вода", "Уход за лицом", "Тоники и мисты", "Garnier", 499, 649, 18, 299, 6, "400 мл", 150),
        ]

        self.stdout.write(f"Создано пользователей: {User.objects.count()}, магазинов: {Shop.objects.count()}, категорий: {Category.objects.count()}")

        self.stdout.write("Загрузка реальных фото с Wikimedia Commons…")
        ensure_seeded_images()

        # (магазин, категория-родитель, подкатегория, бренд, название, розница, старая цена,
        #  остаток, опт, min_qty, объём, цвет, страна)
        data = [
            # Maison Beauté — премиальный уход за лицом и парфюм
            ("premium", "Уход за лицом", "Кремы и сыворотки", "La Roche-Posay", "Крем увлажняющий с гиалуроновой кислотой", 2490, 3290, 7, 1490, 6, "50 мл", "Белый", "Франция"),
            ("premium", "Уход за лицом", "Кремы и сыворотки", "Lancôme", "Сыворотка с витамином C", 4890, None, 4, 2990, 4, "30 мл", "Золотистый", "Франция"),
            ("premium", "Уход за лицом", "Кремы и сыворотки", "Estée Lauder", "Ночной крем с ретинолом", 3990, 4590, 8, 2490, 5, "50 мл", "Бежевый", "США"),
            ("premium", "Уход за лицом", "Маски", "La Roche-Posay", "Мист-тоник с розовой водой", 890, 1190, 9, None, 0, "150 мл", "Розовый", "Франция"),
            ("premium", "Парфюмерия", "Женская", "Lancôme", "Парфюм женский цветочный", 8990, 9990, 5, 5990, 3, "50 мл", "Прозрачный", "Франция"),
            # ColorLab — макияж и уход масс-маркет / средний сегмент
            ("makeup", "Макияж", "Тональные средства", "L'Oréal Paris", "Тональный крем стойкий", 1690, 1990, 6, None, 0, "30 мл", "Слоновая кость", "Франция"),
            ("makeup", "Макияж", "Помады", "Maybelline", "Помада матовая", 990, None, 12, None, 0, "4.2 г", "Красный", "США"),
            ("makeup", "Макияж", "Тушь и подводки", "Maybelline", "Тушь объёмная", 890, 1090, 10, None, 0, "10 мл", "Чёрный", "США"),
            ("makeup", "Уход за лицом", "Тоники и мисты", "Garnier", "Мицеллярная вода с розовой водой", 499, 649, 18, 299, 6, "400 мл", "Прозрачный", "Франция"),
            ("makeup", "Уход за лицом", "Кремы и сыворотки", "Yves Rocher", "Крем дневной антиоксидантный", 1290, 1490, 8, None, 0, "50 мл", "Белый", "Франция"),
            # Hair Soul — волосы, уход, бьюти-бад
            ("hair", "Волосы", "Шампуни", "L'Oréal Paris", "Шампунь для объёма", 1290, None, 8, None, 0, "300 мл", "Прозрачный", "Франция"),
            ("hair", "Волосы", "Маски и бальзамы", "Estée Lauder", "Маска для волос восстанавливающая", 2490, 2990, 6, None, 0, "250 мл", "Белый", "США"),
            ("hair", "Волосы", "Шампуни", "Yves Rocher", "Шампунь увлажняющий с каратой", 990, 1190, 10, 599, 5, "250 мл", "Прозрачный", "Франция"),
            ("hair", "Волосы", "Маски и бальзамы", "Garnier", "Бальзам-уход для сухих волос", 699, 850, 14, None, 0, "200 мл", "Белый", "Франция"),
            ("hair", "Парфюмерия", "Мужская", "L'Oréal Paris", "Парфюм мужской древесный", 5990, None, 4, None, 0, "100 мл", "Тёмно-синий", "Франция"),
        ]

        for key, parent_name, child_name, brand_name, name, price, old_price, stock, wholesale, min_qty, volume, color, country in data:
            category = leaf_cat(child_name)
            brand = Brand.objects.get(name=brand_name)
            product, created = Product.objects.get_or_create(
                name=name, shop=shops[key],
                defaults={
                    "category": category,
                    "brand": brand,
                    "description": f"{name}. Оригинальная продукция {brand_name}. Идеально для ежедневного ухода и профессионального использования.",
                    "price": price,
                    "old_price": old_price,
                    "wholesale_price": wholesale,
                    "wholesale_min_qty": min_qty,
                    "stock": stock,
                    "volume": volume,
                    "color": color,
                    "country": country,
                    "is_active": True,
                    "is_bestseller": price > 3500,
                },
            )
            if created:
                palette = {"Уход за лицом": "face", "Макияж": "makeup", "Волосы": "hair", "Парфюмерия": "perfume"}.get(parent_name, "face")
                img = ProductImage.objects.create(
                    product=product,
                    image=_seeded_image(name, palette),
                    alt=name,
                    is_main=True,
                )
                Product.objects.filter(pk=product.pk).update(views_count=random.randint(50, 500))
                if wholesale:
                    WholesaleTier.objects.get_or_create(product=product, min_qty=min_qty * 2, price=round(wholesale * 0.95))

        self.stdout.write(self.style.SUCCESS(f"Готово. Товаров: {Product.objects.count()}"))
