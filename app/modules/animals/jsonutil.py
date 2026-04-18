import json


def parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def dumps_json_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)
