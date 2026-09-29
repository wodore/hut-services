from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Use this as a base for all schemas, sets `from_attributes` to `True`.

    `populate_by_name` allows constructing models by field name even when a
    field has an alias (e.g. `Field(..., alias="open")` can be set with
    `Schema(open=...)` as well as `Schema(alias_value=...)`).
    """

    model_config = ConfigDict(from_attributes=True, extra="allow", populate_by_name=True)
