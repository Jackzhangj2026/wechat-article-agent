"""图片生成 API：一键生成全部 / 单张生成 / 重生成 / 预览"""
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

import config
from db import get_db
from models import Article, Image
from services import comfyui_client, workflow_loader, vault_writer, size_presets

router = APIRouter(tags=["images"])


class GenerateSingleRequest(BaseModel):
    article_id: int
    prompt: str
    negative_prompt: str = "low quality, blurry, deformed, watermark, text, ugly"
    size_preset: str = "inline_4_3"
    seed: Optional[int] = None
    index: int = 1
    role: str = "inline"
    section: str = ""
    description: str = ""


class RegenerateRequest(BaseModel):
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    size_preset: Optional[str] = None
    seed: Optional[int] = None


@router.get("/api/comfyui/status")
async def comfyui_status():
    """ComfyUI 连接状态与工作流信息"""
    connected = await comfyui_client.check_connection()
    wf_info = workflow_loader.get_workflow_info()
    return {
        "comfyui_connected": connected,
        "workflow_loaded": wf_info["loaded"],
        "workflow_nodes": wf_info["nodes"],
        "workflow_error": wf_info["error"],
    }


@router.post("/api/articles/{article_id}/generate_all_images")
async def generate_all_images(article_id: int, db: Session = Depends(get_db)):
    """一键生成文章全部图片（封面 1 + 文中 3-5）"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if not article.image_plan:
        raise HTTPException(status_code=400, detail="文章无图片规划")

    # 检查工作流
    try:
        workflow_template = workflow_loader.load_workflow_template()
    except workflow_loader.WorkflowError as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = []
    for plan in article.image_plan:
        idx = plan["index"]
        role = plan["role"]
        size_preset = plan["size_preset"]
        prompt = plan["prompt"]
        negative_prompt = plan["negative_prompt"]
        size = size_presets.get_size(size_preset)
        file_prefix = f"article-{article_id}-{role}-{idx}"

        # 创建/更新图片记录
        img_record = db.query(Image).filter(
            Image.article_id == article_id, Image.index == idx
        ).first()
        if not img_record:
            img_record = Image(
                article_id=article_id, index=idx, role=role,
                section=plan.get("section", ""), description=plan.get("description", ""),
                prompt=prompt, negative_prompt=negative_prompt,
                size_preset=size_preset, width=size["width"], height=size["height"],
                status="generating",
            )
            db.add(img_record)
        else:
            img_record.status = "generating"
            img_record.error = ""
        db.commit()
        db.refresh(img_record)

        try:
            # 注入参数并提交
            workflow = workflow_loader.inject_params(
                workflow_template, prompt, negative_prompt, size_preset,
                seed=plan.get("seed"), filename_prefix=file_prefix,
            )
            prompt_id = await comfyui_client.submit_workflow(workflow)
            img_record.comfyui_prompt_id = prompt_id

            # 轮询结果
            output = await comfyui_client.poll_result(prompt_id)
            # 下载图片
            image_bytes = await comfyui_client.download_image(output["filename"], output["subfolder"])

            # 保存到知识库
            file_name = vault_writer.save_image(image_bytes, article_id, role, idx)
            img_record.file_path = file_name
            img_record.status = "done"
            # 提取 seed
            seed_val = workflow[workflow_loader._detect_nodes(workflow)["sampler"]]["inputs"].get("seed", 0)
            img_record.seed = int(seed_val)
            db.commit()
            results.append({"index": idx, "status": "done", "file_path": file_name})
        except Exception as e:
            img_record.status = "failed"
            img_record.error = str(e)
            db.commit()
            results.append({"index": idx, "status": "failed", "error": str(e)})

    return {"article_id": article_id, "results": results}


@router.post("/api/images/generate")
async def generate_single_image(req: GenerateSingleRequest, db: Session = Depends(get_db)):
    """单张图片生成"""
    article = db.query(Article).filter(Article.id == req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    try:
        workflow_template = workflow_loader.load_workflow_template()
    except workflow_loader.WorkflowError as e:
        raise HTTPException(status_code=500, detail=str(e))

    size = size_presets.get_size(req.size_preset)
    file_prefix = f"article-{req.article_id}-{req.role}-{req.index}"

    img_record = Image(
        article_id=req.article_id, index=req.index, role=req.role,
        section=req.section, description=req.description,
        prompt=req.prompt, negative_prompt=req.negative_prompt,
        size_preset=req.size_preset, width=size["width"], height=size["height"],
        status="generating",
    )
    db.add(img_record)
    db.commit()
    db.refresh(img_record)

    try:
        workflow = workflow_loader.inject_params(
            workflow_template, req.prompt, req.negative_prompt, req.size_preset,
            seed=req.seed, filename_prefix=file_prefix,
        )
        prompt_id = await comfyui_client.submit_workflow(workflow)
        img_record.comfyui_prompt_id = prompt_id
        output = await comfyui_client.poll_result(prompt_id)
        image_bytes = await comfyui_client.download_image(output["filename"], output["subfolder"])
        file_name = vault_writer.save_image(image_bytes, req.article_id, req.role, req.index)
        img_record.file_path = file_name
        img_record.status = "done"
        seed_val = workflow[workflow_loader._detect_nodes(workflow)["sampler"]]["inputs"].get("seed", 0)
        img_record.seed = int(seed_val)
        db.commit()
        return {"image_id": img_record.id, "file_path": file_name, "status": "done"}
    except Exception as e:
        img_record.status = "failed"
        img_record.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/images/{image_id}/regenerate")
async def regenerate_image(image_id: int, req: RegenerateRequest, db: Session = Depends(get_db)):
    """重新生成单张图片（保留旧图直到新图成功）"""
    img = db.query(Image).filter(Image.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")
    try:
        workflow_template = workflow_loader.load_workflow_template()
    except workflow_loader.WorkflowError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 应用新参数（未提供的用原值）
    prompt = req.prompt or img.prompt
    negative_prompt = req.negative_prompt or img.negative_prompt
    size_preset = req.size_preset or img.size_preset
    size = size_presets.get_size(size_preset)
    file_prefix = f"article-{img.article_id}-{img.role}-{img.index}"

    img.status = "generating"
    img.error = ""
    img.prompt = prompt
    img.negative_prompt = negative_prompt
    img.size_preset = size_preset
    img.width = size["width"]
    img.height = size["height"]
    db.commit()

    try:
        workflow = workflow_loader.inject_params(
            workflow_template, prompt, negative_prompt, size_preset,
            seed=req.seed, filename_prefix=file_prefix,
        )
        prompt_id = await comfyui_client.submit_workflow(workflow)
        img.comfyui_prompt_id = prompt_id
        output = await comfyui_client.poll_result(prompt_id)
        image_bytes = await comfyui_client.download_image(output["filename"], output["subfolder"])
        file_name = vault_writer.save_image(image_bytes, img.article_id, img.role, img.index)
        img.file_path = file_name
        img.status = "done"
        seed_val = workflow[workflow_loader._detect_nodes(workflow)["sampler"]]["inputs"].get("seed", 0)
        img.seed = int(seed_val)
        db.commit()
        return {"image_id": img.id, "file_path": file_name, "status": "done"}
    except Exception as e:
        img.status = "failed"
        img.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/images/{image_id}/preview")
def preview_image(image_id: int, db: Session = Depends(get_db)):
    """返回图片文件"""
    img = db.query(Image).filter(Image.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not img.file_path:
        raise HTTPException(status_code=404, detail="图片尚未生成")
    file_path = os.path.join(config.ARTICLE_ASSETS_DIR, img.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(file_path, media_type="image/png")


@router.get("/api/articles/{article_id}/images")
def list_article_images(article_id: int, db: Session = Depends(get_db)):
    """列出文章全部图片"""
    images = db.query(Image).filter(Image.article_id == article_id).order_by(Image.index).all()
    return {
        "images": [
            {
                "id": img.id, "index": img.index, "role": img.role,
                "section": img.section, "description": img.description,
                "prompt": img.prompt, "negative_prompt": img.negative_prompt,
                "size_preset": img.size_preset, "width": img.width, "height": img.height,
                "seed": img.seed, "file_path": img.file_path, "status": img.status, "error": img.error,
            }
            for img in images
        ]
    }
