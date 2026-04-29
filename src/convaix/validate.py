"""Schema v1.0 validator."""

VALID_ROLES = {"user", "assistant", "system"}
REQUIRED_CONV_FIELDS = {"id", "title", "source", "exported_at"}
REQUIRED_TURN_FIELDS = {"turn_number", "role", "content"}
REQUIRED_TOP_LEVEL = {"schema_version", "conversation", "turns", "statistics"}


class ValidationError(Exception):
    pass


def validate_conversation(data: dict) -> None:
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            raise ValidationError(f"Missing top-level field: {field}")

    if data["schema_version"] != "1.0":
        raise ValidationError(f"Unsupported schema_version: {data['schema_version']}")

    conv = data["conversation"]
    for field in REQUIRED_CONV_FIELDS:
        if field not in conv:
            raise ValidationError(f"Missing conversation field: {field}")

    turns = data["turns"]
    if not isinstance(turns, list):
        raise ValidationError("turns must be a list")

    for i, turn in enumerate(turns):
        for field in REQUIRED_TURN_FIELDS:
            if field not in turn:
                raise ValidationError(f"Turn {i + 1}: missing field: {field}")
        if turn["role"] not in VALID_ROLES:
            raise ValidationError(f"Turn {i + 1}: invalid role '{turn['role']}'")
