from fastapi import APIRouter, HTTPException, Depends
from database.schema import TafsiriConfigSchema
from bson.objectid import ObjectId
from database.database import get_mongo_collection, CONFIGS_COLLECTION
from urllib.parse import quote_plus
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

router = APIRouter()


def format_mongo_obj(obj):
    """
    Helper function to format MongoDB object
    """
    obj["_id"] = str(obj["_id"])
    return obj


@router.get("/get_configs", response_model=list[TafsiriConfigSchema])
async def get_configs(collection=Depends(lambda: get_mongo_collection(CONFIGS_COLLECTION))):
    """
    Get all configurations for the Tafsiri API
    """
    config_data = collection.find()
    return [format_mongo_obj(config) for config in config_data]


@router.post("/new_config", response_model=TafsiriConfigSchema)
async def create_new_config(config: TafsiriConfigSchema, collection=Depends(lambda: get_mongo_collection(CONFIGS_COLLECTION))):
    """
    Create a new configuration for the Tafsiri API
    """
    config_data = config.model_dump(exclude_unset=True)
    result = collection.insert_one(config_data)
    if result.inserted_id:
        return format_mongo_obj(config_data)
    raise HTTPException(
        status_code=400, detail="Configuration could not be created")


@router.get("/get_config/{config_id}", response_model=TafsiriConfigSchema)
async def get_config(config_id):
    """
    Get a specific configuration for the Tafsiri API
    """
    collection = get_mongo_collection(CONFIGS_COLLECTION)
    if collection is None:
        raise HTTPException(status_code=500, detail="Collection not found")
    try:
        config_id = ObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    config = collection.find_one({"_id": config_id})
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")

    # Convert ObjectId to string
    config["_id"] = str(config["_id"])

    return config


@router.put("/update_config/{config_id}", response_model=TafsiriConfigSchema)
async def update_config(config_id: str, updated_config: TafsiriConfigSchema, collection=Depends(lambda: get_mongo_collection(CONFIGS_COLLECTION))):
    """
    Update a specific configuration for the Tafsiri API
    """
    if collection is None:
        raise HTTPException(status_code=500, detail="Collection not found")

    try:
        config_id = ObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    config_data = collection.find_one({"_id": config_id})
    if config_data is None:
        raise HTTPException(status_code=404, detail="Config not found")

    updated_data = updated_config.model_dump(exclude_unset=True)
    result = collection.update_one({"_id": config_id}, {"$set": updated_data})

    if result.modified_count == 1:
        updated_config_data = collection.find_one({"_id": config_id})
        return format_mongo_obj(updated_config_data)

    raise HTTPException(
        status_code=400, detail="Configuration could not be updated")


@router.delete("/delete_config/{config_id}")
async def delete_config(config_id):
    """
    Delete a specific configuration for the Tafsiri API
    """
    collection = get_mongo_collection(CONFIGS_COLLECTION)
    if collection is None:
        raise HTTPException(status_code=500, detail="Collection not found")
    try:
        config_id = ObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")
    result = collection.delete_one({"_id": config_id})
    if result.deleted_count == 1:
        return {"message": "Config deleted successfully"}
    raise HTTPException(status_code=404, detail="Config not found")


class DBConnectionRequest(BaseModel):
    db_type: str = Field(...,
                         description="Type of the database (e.g., 'mysql', 'postgresql')")
    host_port: str = Field(..., description="Database host & port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")


@router.post("/test_db_connection")
async def test_db_connection(data: DBConnectionRequest):
    # Encode special characters in the password
    encoded_password = quote_plus(data.password)
    db_url = f"{data.db_type}://{data.username}:{encoded_password}@{data.host_port}/{data.database}"

    success, error_message = test_db(db_url)
    if success:
        return {"status": "Database connection successful"}
    else:
        raise HTTPException(status_code=500, detail=error_message)


def test_db(db_url):
    try:
        engine = create_engine(db_url)
        conn = engine.connect()
        conn.close()
        return True, None
    except OperationalError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
