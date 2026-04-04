from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# ⚠️ 必须配置跨域，否则前端无法调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 默认端口
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "后端已启动 ✅"}

@app.post("/api/skill")
def run_skill(data: dict):
    query = data.get("query", "无指令")
    return {"result": f"🤖 AI 收到：{query}", "status": "success"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)