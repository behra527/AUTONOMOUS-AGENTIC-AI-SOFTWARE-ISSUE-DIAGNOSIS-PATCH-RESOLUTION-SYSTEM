from pydantic import BaseModel, Field


class TicketInput(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=10, max_length=8000)
    expected_behavior: str = Field(min_length=3, max_length=2000)
    actual_behavior: str = Field(min_length=3, max_length=2000)
    reproduction_steps: list[str] = Field(min_length=1, max_length=20)


class RepoInput(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=200)
    remote_url: str = Field(min_length=3, max_length=1000)


class AttachmentInput(BaseModel):
    filename: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_. -]{0,140}\.(txt|log)$')
    content: str = Field(min_length=1, max_length=32000)


class IndexInput(BaseModel):
    commit_sha: str = Field(pattern=r'^[0-9a-f]{40}$')


class InvestigationInput(IndexInput):
    repository_id: str


class Hypothesis(BaseModel):
    title: str = Field(max_length=300)
    explanation: str = Field(max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class Diagnosis(BaseModel):
    summary: str = Field(max_length=3000)
    hypotheses: list[Hypothesis] = Field(max_length=5)
    missing_information: list[str] = Field(max_length=10)
    limitations: list[str] = Field(max_length=10)
