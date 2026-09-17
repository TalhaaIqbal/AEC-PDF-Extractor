# AEC Drawing Intelligence Pipeline - Backend

FastAPI backend for processing AEC (Architecture, Engineering, Construction) drawings.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```bash
cp .env.example .env
```

5. Add your OpenAI API key to the `.env` file:
```
OPENAI_API_KEY=your_actual_api_key_here
OPENAI_MODEL=GPT-5.6o
```

## Running the Server

```bash
python main.py
```

The server will start on `http://localhost:8000`

## API Endpoints

- `POST /upload-pdf` - Upload a PDF file
- `POST /process/{session_id}` - Start processing the uploaded PDF
- `GET /status/{session_id}` - Get processing status
- `GET /result/{session_id}` - Get the processing result
- `GET /download/{session_id}/{file_type}` - Download processed files (json, markdown, zip)
- `DELETE /session/{session_id}` - Delete a session and clean up files

## API Documentation

Once the server is running, visit `http://localhost:8000/docs` for interactive API documentation.