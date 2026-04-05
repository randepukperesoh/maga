from pydantic import BaseModel, ConfigDict, Field


class DefectIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rod_id: str = Field(alias="rodId")
    defect_type: str = Field(alias="defectType")
    params: dict


class Defect(DefectIn):
    id: str
