from sqlalchemy.orm import Session

from price_monitor.config import Settings
from price_monitor.models import AppSetting
from price_monitor.search import SearchLocation

CITY_KEY = "default_city"
STATE_KEY = "default_state"


def get_default_location(session: Session, settings: Settings) -> SearchLocation:
    city = session.get(AppSetting, CITY_KEY)
    state = session.get(AppSetting, STATE_KEY)
    return SearchLocation(
        city.value if city else settings.default_city,
        (state.value if state else settings.default_state).upper(),
    )


def set_default_location(session: Session, city: str, state: str) -> SearchLocation:
    normalized_city = city.strip()
    normalized_state = state.strip().upper()
    for key, value in ((CITY_KEY, normalized_city), (STATE_KEY, normalized_state)):
        setting = session.get(AppSetting, key)
        if setting is None:
            session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
    session.commit()
    return SearchLocation(normalized_city, normalized_state)
