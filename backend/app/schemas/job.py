"""Schemas for individual job representations."""

from pydantic import BaseModel, ConfigDict, Field


class JobRecordSchema(BaseModel):
    """Schema representing an extracted, normalized job record."""

    model_config = ConfigDict(frozen=True)

    company_name: str = Field(..., description="Normalized company name")
    job_role: str = Field(..., description="Job role or job title")
    number_of_people: int | str = Field(..., description="Employee count as an integer or 'N/A'")
    job_url: str | None = Field(None, description="Source job listing URL if discovered")
    status: str = Field("NEW", description="Listing status: NEW or EXISTING")
    is_new: bool = Field(True, description="Whether this job was newly discovered during this run")
