from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Use this as a base for all schemas, sets `from_attributes` to `True`."""

    model_config = ConfigDict(from_attributes=True)
