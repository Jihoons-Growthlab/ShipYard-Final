"""F02 날씨. 공급자 레지스트리(WEATHER_PROVIDER 이름). 없거나 실패·형식 오류면 SAMPLE + error. DB에 저장하지 않는다."""
from typing import Callable

from .. import config
from ..errors import validation

SAMPLES = {
    "울산": {"tempC": 17.6, "condition": "맑음", "humidity": 52, "windMs": 3.2},
    "거제": {"tempC": 18.9, "condition": "구름조금", "humidity": 61, "windMs": 4.1},
    "목포": {"tempC": 16.2, "condition": "흐림", "humidity": 70, "windMs": 5.0},
}
DEFAULT_REGION = "울산"

# 이름 → fn(region) -> {"obsDt","tempC","condition","humidity","windMs"}
PROVIDERS: dict[str, Callable[[str], dict]] = {}

_REQUIRED = {"tempC": (int, float), "condition": str, "humidity": (int, float), "windMs": (int, float)}


def _valid(data) -> bool:
    return isinstance(data, dict) and all(isinstance(data.get(k), t) and not isinstance(data.get(k), bool)
                                          for k, t in _REQUIRED.items())


def get_weather(region: str | None) -> dict:
    region = (region or "").strip() or DEFAULT_REGION
    if region not in SAMPLES:
        raise validation("region", "지원하지 않는 지역입니다.")
    name = config.weather_provider()
    if not name:
        error = "날씨 공급자가 설정되지 않아 샘플 데이터를 표시합니다."
    elif name not in PROVIDERS:
        error = f"알 수 없는 날씨 공급자({name})입니다."
    else:
        try:
            data = PROVIDERS[name](region)
            if _valid(data):
                return {"region": region, "source": "LIVE", "obsDt": data.get("obsDt"),
                        **{k: data[k] for k in _REQUIRED}, "error": None}
            error = "날씨 공급자 응답 형식이 올바르지 않습니다."
        except Exception as e:  # 공급자 실패는 샘플로 대체
            error = f"날씨 공급자 조회 실패: {type(e).__name__}"
    return {"region": region, "source": "SAMPLE", "obsDt": config.TODAY, **SAMPLES[region], "error": error}
