import datetime
from dateutil.relativedelta import relativedelta

def parse_natural_deadline(phrase: str, base_date: datetime.date = None) -> str:
    if not phrase:
        return "N/A"
        
    if not base_date:
        base_date = datetime.date.today()
    
    clean_phrase = phrase.strip().lower()

    if clean_phrase in ["today", "eod"]:
        return str(base_date)
    elif clean_phrase == "tomorrow":
        return str(base_date + datetime.timedelta(days=1))
    elif "end of this month" in clean_phrase:
        next_month = base_date.replace(day=28) + datetime.timedelta(days=4)
        return str(next_month - datetime.timedelta(days=next_month.day))
    
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for idx, day in enumerate(days_of_week):
        if day in clean_phrase:
            current_day = base_date.weekday()
            target_day = idx
            days_ahead = target_day - current_day
            if days_ahead <= 0 or "next" in clean_phrase:
                days_ahead += 7
            return str(base_date + datetime.timedelta(days=days_ahead))

    return phrase