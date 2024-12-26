import os

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import select

from ....deps import AsyncSessionDepends
from ....models._utils import RandomString, now
from ....models.file import File as MyFile
from ....models.user import UserDepends, get_user

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
router = APIRouter(dependencies=[Depends(get_user)])

@router.post("/upload/")
async def upload_single_file(session:AsyncSessionDepends,file: UploadFile = File(...),user = Depends(get_user) ):

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    start_time  =  now()
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    finish_time = now()
    id = RandomString()
    file_info = MyFile(filename=file.filename, user_id= user.id,created_at= start_time,updated_at=finish_time,path=file_path,id = id.unique_id)
    
    session.add(file_info)
    try:
        await session.commit()
        await session.refresh(file_info)
    except Exception as e:
        return {"error": str(e)}
    return ({"message": "upload sucessfully"})


@router.get("/showFiles/", response_model=list[MyFile])
async def list_files(session: AsyncSessionDepends,user = Depends(get_user)) -> list[MyFile]:
    result = await session.execute(select(MyFile).where(MyFile.user_id == user.id))
    files = list(result.scalars().all())
    return files
