from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default="default", description="会话标识")
    message: str = Field(..., description="用户输入消息")
    image_base64: Optional[str] = Field(None, description="可选的 Base64 图片")


class ChatResponse(BaseModel):
    session_id: str
    answer: str = Field(..., description="系统最终回复")
    thought_plan: Optional[str] = Field(None, description="可选的思考计划")
    image_paths: List[str] = Field(default_factory=list, description="相关图片路径")
    agent_reports: List[Dict[str, Any]] = Field(default_factory=list, description="三智能体协作结果")
    project_snapshot: Optional[Dict[str, Any]] = Field(None, description="项目总览与 Sprint 快照")


class ClearRequest(BaseModel):
    session_id: str = Field(default="default", description="会话标识")


class HealthResponse(BaseModel):
    status: str
    details: Dict[str, Any]


class DocumentItem(BaseModel):
    doc_id: str
    source_file: str
    doc_type: str
    document_count: int
    chunk_count: int
    ingest_time: str


class DocumentUploadResponse(BaseModel):
    status: str
    doc_id: Optional[str] = None
    document_count: Optional[int] = None
    chunk_count: Optional[int] = None
    message: Optional[str] = None


class ProfileResponse(BaseModel):
    name: str = ""
    preferred_style: str = ""
    interests: List[str] = []
    current_projects: List[str] = []
    current_goals: List[str] = []
    workflow_preferences: List[str] = []
    persona_notes: str = ""


class TaskItem(BaseModel):
    id: int
    content: str
    status: str
    priority: str = "medium"
    linked_goal: Optional[str] = None
    owner: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    status: str
