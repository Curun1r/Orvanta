"""Fictional salon fixtures used only by the dedicated demo workspace."""

CATEGORIES_AND_SERVICES = {
    'Hair': [
        ("Women's haircut", 450, 60),
        ("Men's haircut", 250, 30),
        ("Children's haircut", 180, 25),
        ('Hair coloring', 900, 120),
        ('Highlights', 1200, 150),
        ('Keratin hair treatment', 1800, 180),
        ('Hair styling', 350, 45),
        ('Braiding', 400, 60),
    ],
    'Nails': [
        ('Classic manicure', 350, 60),
        ('Machine manicure', 450, 75),
        ('Gel polish', 500, 90),
        ('Nail extensions', 900, 120),
        ('Classic pedicure', 500, 75),
        ('Machine pedicure', 650, 90),
    ],
    'Skin care': [
        ('Facial cleansing', 700, 90),
        ('Facial peel', 650, 60),
        ('Mesotherapy', 1400, 75),
        ('Beauty injections', 2500, 60),
        ('Facial massage', 500, 45),
    ],
    'Massage': [
        ('Back massage', 600, 60),
        ('Full body massage', 900, 90),
        ('Anti-cellulite massage', 750, 60),
        ('Lymphatic drainage massage', 800, 75),
        ('Head massage', 350, 30),
    ],
    'Brows and lashes': [
        ('Brow shaping', 250, 30),
        ('Brow tinting', 200, 20),
        ('Brow lamination', 600, 60),
        ('Lash extensions', 900, 120),
        ('Lash lamination', 700, 90),
        ('Permanent brow makeup', 2200, 150),
    ],
}

# Fictional English-language names for public screenshots.
CLIENT_NAMES = [
    'Emily Carter', 'Oliver Bennett', 'Charlotte Hughes', 'Amelia Brooks',
    'Henry Mitchell', 'Isla Thompson', 'George Parker', 'Mia Collins',
    'Arthur Reed', 'Grace Foster', 'Noah Walker', 'Lily Harrison',
    'Oscar Turner', 'Freya Edwards', 'Leo Richardson', 'Ava Cooper',
    'Jack Anderson', 'Ella Stevens', 'William Hayes', 'Evie Morris',
    'Thomas Clarke', 'Sophia Bailey', 'Charlie Robinson', 'Alice Green',
    'Jacob Ward', 'Florence Hill', 'Archie Lewis', 'Ruby Scott',
    'Joshua Adams', 'Matilda King', 'James Wright', 'Poppy Allen',
    'Lucas Wood', 'Daisy Young', 'Benjamin Hall',
]

# Independent fictional price lists, not exchange rates or converted amounts.
DEMO_PRICE_BOOKS = {
    'EUR': [55, 30, 20, 95, 120, 180, 45, 60,
            35, 45, 40, 65, 45, 55,
            70, 65, 100, 200, 55,
            55, 85, 65, 70, 35,
            20, 15, 45, 80, 55, 220],
    'USD': [60, 35, 25, 110, 140, 210, 50, 65,
            40, 50, 45, 75, 50, 65,
            80, 75, 120, 230, 60,
            65, 100, 75, 80, 40,
            25, 20, 55, 90, 65, 250],
}
