import io
import random

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from PIL import Image

from catalog.models import Brand, Category, Product, ProductImage, WholesaleTier
from shops.models import Shop
from users.models import User


def _placeholder(color, size=(600, 600)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    buf.seek(0)
    return ContentFile(buf.read(), name="placeholder.jpg")


class Command(BaseCommand):
    help = "Наполняет базу демо-данными: пользователи, категории, бренды, магазин, товары."

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

        seller, _ = User.objects.get_or_create(
            email="seller@beauty.kg",
            defaults={"first_name": "Анна", "last_name": "Петрова", "is_seller": True, "phone": "+996 (555) 444-55-66"},
        )
        seller.set_password("Seller123!")
        seller.is_seller = True
        seller.save()

        shop, _ = Shop.objects.get_or_create(
            owner=seller,
            defaults={
                "name": "Maison Beauté",
                "city": "Бишкек",
                "address": "пр. Чуй, 154",
                "phone": "+996 (555) 444-55-66",
                "email": "shop@maisonbeaute.kg",
                "description": "Бутик премиальной косметики и ухода. Опт для салонов и студий.",
            },
        )

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

        for name, parent_name, child_name, brand_name, price, old_price, stock, wholesale, min_qty, volume, color in data:
            category = leaf_cat(child_name)
            brand = Brand.objects.get(name=brand_name)
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "shop": shop,
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
                    "is_active": True,
                    "is_bestseller": random.random() > 0.6,
                },
            )
            if created:
                img = ProductImage.objects.create(
                    product=product,
                    image=_placeholder((random.randint(60, 200), random.randint(60, 200), random.randint(60, 200))),
                    alt=name,
                    is_main=True,
                )
                Product.objects.filter(pk=product.pk).update(views_count=random.randint(50, 500))
                if wholesale:
                    WholesaleTier.objects.get_or_create(product=product, min_qty=min_qty * 2, price=round(wholesale * 0.95))

        self.stdout.write(self.style.SUCCESS(f"Готово. Товаров: {Product.objects.count()}"))
