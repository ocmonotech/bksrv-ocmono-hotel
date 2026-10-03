def format_inr(amount: float) -> str:
    return f"₹{amount:,.2f}"


def round_currency(amount: float, places: int = 2) -> float:
    return round(float(amount), places)
