import json
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from ..config import SKILLS_DIR
from ..services.llm_service import chat_completion_with_fallback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])


class ExecuteSkillRequest(BaseModel):
    context: dict
    model_override: str | None = None


class ImportGitRequest(BaseModel):
    url: str
    branch: str = "main"
    subpath: str = ""


class ImportUrlRequest(BaseModel):
    url: str


def _scan_skills() -> list[dict]:
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for item in sorted(SKILLS_DIR.iterdir()):
        if item.is_dir():
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                name = item.name
                description = ""
                for line in content.split("\n"):
                    if line.startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip("\"'")
                        break
                skills.append({
                    "name": name,
                    "description": description or f"Skill: {name}",
                    "path": str(item),
                    "icon": "🧩",
                    "type": "function",
                    "version": "1.0.0",
                    "tags": [name],
                })
    return skills


@router.get("")
async def list_skills():
    skills = _scan_skills()
    return {"skills": skills, "total": len(skills)}


@router.get("/{name}")
async def get_skill(name: str):
    skill_dir = SKILLS_DIR / name
    if not skill_dir.exists():
        raise HTTPException(404, f"Skill not found: {name}")
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        return {
            "name": name,
            "path": str(skill_dir),
            "content": content,
            "files": [str(p.relative_to(skill_dir)) for p in skill_dir.rglob("*") if p.is_file()],
        }
    return {"name": name, "path": str(skill_dir)}


@router.post("/{name}/execute")
async def execute_skill(name: str, req: ExecuteSkillRequest):
    skill_dir = SKILLS_DIR / name
    if not skill_dir.exists():
        raise HTTPException(404, f"Skill not found: {name}")

    skill_md = skill_dir / "SKILL.md"
    skill_instructions = ""
    if skill_md.exists():
        skill_instructions = skill_md.read_text(encoding="utf-8", errors="replace")[:2000]

    user_text = req.context.get("text", "") or json.dumps(req.context, ensure_ascii=False)
    prompt = f"""根据以下 Skill 说明执行任务：

Skill: {name}
说明: {skill_instructions}

用户输入:
{user_text}

请按照 Skill 说明完成任务并输出结果。"""

    result = chat_completion_with_fallback(
        chain_name="actor",
        system_prompt=f"You are executing the '{name}' skill. Follow the skill instructions precisely.",
        user_message=prompt,
    )

    output = result.get("content", "")
    return {
        "output": output,
        "skill_name": name,
        "model": result.get("model", ""),
        "critic_feedbacks": [],
    }


@router.post("/import/git")
async def import_skill_from_git(req: ImportGitRequest):
    return {
        "skill_name": req.url.split("/")[-1].replace(".git", ""),
        "trust_level": "unknown",
        "scan_result": {"risk_level": "low", "warnings": []},
        "message": "Git import is a stub - implement full git clone workflow",
    }


@router.post("/import/upload")
async def import_skill_from_zip(file: UploadFile = File(...)):
    return {
        "skill_name": Path(file.filename).stem.replace(".skill", "") if file.filename else "unknown",
        "trust_level": "unknown",
        "scan_result": {"risk_level": "low", "warnings": []},
        "message": "ZIP import is a stub - implement full zip extraction workflow",
    }


@router.post("/import/folder")
async def import_skill_from_folder(file: UploadFile = File(...)):
    return {
        "skill_name": "imported_skill",
        "trust_level": "unknown",
        "message": "Folder import stub",
    }


@router.post("/import/url")
async def import_skill_from_url(req: ImportUrlRequest):
    return {
        "skill_name": req.url.split("/")[-1],
        "trust_level": "unknown",
        "message": "URL import stub - implement full download workflow",
    }


@router.post("/preview/git")
async def preview_skill_git(req: ImportGitRequest):
    return {
        "skill_name": req.url.split("/")[-1].replace(".git", ""),
        "trust_level": "unknown",
        "config": {"name": "preview_skill", "description": "Preview", "type": "function"},
        "scan_result": {"risk_level": "low", "warnings": []},
        "files": ["SKILL.md"],
    }


@router.post("/preview/upload")
async def preview_skill_upload(file: UploadFile = File(...)):
    return {
        "skill_name": Path(file.filename).stem.replace(".skill", "") if file.filename else "preview",
        "trust_level": "unknown",
        "config": {"name": "preview_skill", "description": "Preview", "type": "function"},
        "scan_result": {"risk_level": "low", "warnings": []},
        "files": ["SKILL.md"],
    }


@router.delete("/{name}")
async def delete_skill(name: str):
    return {"ok": True, "message": f"Skill {name} deletion stub"}


@router.post("/reload")
async def reload_skills():
    skills = _scan_skills()
    return {"skills_loaded": len(skills)}