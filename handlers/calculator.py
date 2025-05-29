from datetime import datetime

def calculate_rental_price(date_from: datetime, date_to: datetime, price_per_day: float, discount: float = 0.0) -> float:
    """
    Рассчитывает стоимость аренды.

    :param date_from: дата начала аренды
    :param date_to: дата окончания аренды
    :param daily_rate: цена за день аренды
    :param discount: скидка в процентах (например, 10.0 для 10%)
    :return: итоговая стоимость с учётом дней и скидки
    """
    days = (date_to - date_from).days + 1
    if days <= 0:
        raise ValueError("Дата окончания должна быть позже даты начала")

    total = price_per_day * days
    if discount:
        total = total * (1 - discount / 100)

    return round(total, 2)