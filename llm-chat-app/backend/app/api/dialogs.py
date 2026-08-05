"""Маршруты диалогов."""
from fastapi import APIRouter, Depends

from ..deps import current_user, owned_dialog
from ..schemas.auth import OkOut
from ..schemas.dialogs import DialogCreate, DialogOut, DialogPatch
from ..services import dialogs as dialog_service

router = APIRouter(prefix="/api", tags=["dialogs"])


@router.get("/dialogs", response_model=list[DialogOut])
def list_dialogs(user: dict = Depends(current_user)):
    return dialog_service.list_for_user(user["id"])


@router.post("/dialogs", response_model=DialogOut)
def create_dialog(body: DialogCreate, user: dict = Depends(current_user)):
    return dialog_service.create(user["id"], body.model_name)


@router.patch("/dialogs/{dialog_id}", response_model=DialogOut)
def patch_dialog(body: DialogPatch, dialog: dict = Depends(owned_dialog)):
    if body.title is not None:
        dialog_service.rename(dialog["id"], body.title)
    if body.model_name is not None:
        dialog_service.set_model(dialog["id"], body.model_name)
    return dialog_service.get(dialog["id"])


@router.delete("/dialogs/{dialog_id}", response_model=OkOut)
def delete_dialog(dialog: dict = Depends(owned_dialog)):
    dialog_service.delete(dialog["id"])
    return OkOut(ok=True)
