from typing import Optional, Dict, List
from pydantic import BaseModel


class FlowDataSaveRequest(BaseModel):
    project_id: Optional[int] = None
    flow_data: Dict
    screen_positions: Optional[Dict] = None


class FlowDataResponse(BaseModel):
    project_id: int
    flow_data: Optional[Dict] = None
    screen_positions: Optional[Dict] = None
    links: Optional[List[Dict]] = None
