from fastapi import FastAPI, UploadFile, File
import uvicorn
import os

app = FastAPI(title="Threat Reception API")

# Ensure the 'captures' directory exists
os.makedirs("captures", exist_ok=True)

@app.post("/upload-threat")
async def upload_threat(file: UploadFile = File(...)):
    file_path = os.path.join("captures", file.filename)
    
    # Read and save the file contents
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
        
    print(f"📥 Frame received from Vision Engine: {file.filename}")
    
    # ensure posix path format for the response if required by user example
    return {"status": "received", "path": file_path.replace("\\", "/")}

if __name__ == "__main__":
    print("Starting API server on port 8000...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
