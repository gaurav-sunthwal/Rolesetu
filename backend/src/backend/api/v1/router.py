from fastapi import APIRouter

from backend.modules.applications.router import router as applications_router
from backend.modules.extension.router import router as extension_router
from backend.modules.inbox.router import router as inbox_router
from backend.modules.llm_keys.router import router as llm_keys_router
from backend.modules.matches.router import router as matches_router
from backend.modules.profiles.router import router as profiles_router
from backend.modules.resumes.router import router as resumes_router
from backend.modules.saved_answers.router import router as saved_answers_router
from backend.modules.tailoring.router import router as tailoring_router
from backend.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users_router)
api_router.include_router(llm_keys_router)
api_router.include_router(profiles_router)
api_router.include_router(saved_answers_router)
api_router.include_router(applications_router)
api_router.include_router(matches_router)
api_router.include_router(resumes_router)
api_router.include_router(extension_router)
api_router.include_router(tailoring_router)
api_router.include_router(inbox_router)
