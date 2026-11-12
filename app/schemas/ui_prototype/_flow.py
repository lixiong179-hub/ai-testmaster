from pydantic import BaseModel


class FlowDataSaveRequest(BaseModel):
    project_id: int | None = None
    flow_data: dict
    screen_positions: dict | None = None


class FlowDataResponse(BaseModel):
    project_id: int
    flow_data: dict | None = None
    screen_positions: dict | None = None
    links: list[dict] | None = None
