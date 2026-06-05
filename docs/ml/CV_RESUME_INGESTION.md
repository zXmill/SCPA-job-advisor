# CV/Resume Ingestion Design

## Objective
Allow users to upload a CV/resume file so the system can automatically extract skills, education, and experience, then enrich the user profile for better recommendations.

## In-Scope (Smoke)
- Authenticated `POST /api/profile/cv` endpoint in the gateway.
- Accept PDF and plain-text files.
- Extract raw text from PDF using `PyPDF2` (lightweight, no external binaries).
- Run extracted text through the existing skill-taxonomy canonicalizer (`_canonicalize_profile_skills`).
- Upsert extracted skills into `user_skills`.
- Record upload metadata (`cv_uploaded_at`, optional `cv_embedding` placeholder).
- Return extracted skills and match summary to the caller.

## Out-of-Scope (Future)
- DOCX support (requires `python-docx`).
- Image-based PDF OCR (requires `pytesseract` + Tesseract binary).
- LLM-based structured extraction (experience, education, projects).
- Actual vector embedding of CV text into `users.cv_embedding`.
- File storage to S3/cloud; smoke stores locally in `data/uploads/cv/`.
- Virus scanning.

## Architecture

```
Frontend profile page
        |
        v
POST /api/profile/cv  (multipart/form-data)
        |
        v
Gateway (FastAPI)
  - Validate auth
  - Validate file type (pdf, txt)
  - Validate file size (<= 5 MB)
  - Save file to disk
  - Extract text
  - Canonicalize skills
  - Upsert user_skills
  - Update users.cv_uploaded_at
  - Return JSON
```

## Database Changes
No new migrations needed. The `008_feature_extension_foundation.py` migration already created:
- `users.cv_uploaded_at` (DateTime, nullable)
- `users.cv_embedding` (ARRAY(Float), nullable)

## Dependencies
Add to `services/gateway/requirements.txt`:
- `PyPDF2>=3.0.0`

No new frontend dependencies needed; native `<input type="file">` is sufficient.

## API Contract

### Request
`POST /api/profile/cv`
- Header: `Authorization: Bearer <token>`
- Body: `multipart/form-data`
  - `file`: The CV file (`.pdf` or `.txt`)

### Response
```json
{
  "status": "ok",
  "extracted_skills": ["Python", "FastAPI", "PostgreSQL"],
  "skills_added": 3,
  "skills_ignored": 0,
  "filename": "cv_budi.pdf",
  "uploaded_at": "2026-05-26T00:15:00+07:00"
}
```

### Errors
- `400` — Unsupported file type, empty file, file too large.
- `401` — Missing or invalid token.
- `422` — Text extraction failed (corrupted PDF, etc.).

## Skill Extraction Strategy
1. Extract all text from the uploaded file.
2. Normalize whitespace and casing.
3. Tokenize and look for skill names from the existing `skills` taxonomy table.
4. Use the existing `_canonicalize_profile_skills` helper to map raw text tokens to canonical skills.
5. Upsert matched skills into `user_skills` with `proficiency_level='beginner'` (default; future work can infer level from text).

## Security Considerations
- File extension whitelist: `.pdf`, `.txt`.
- MIME type validation (not just extension).
- File size cap: 5 MB.
- Store files outside the web root (`data/uploads/cv/`).
- Use UUID-based filenames to prevent directory traversal and enumeration.
- Do not execute or render uploaded files.

## Frontend UX (Smoke)
- Add a "Unggah CV" section to the profile page.
- Show `<input type="file" accept=".pdf,.txt">`.
- After upload, display extracted skills as chips and allow the user to remove false positives before saving.
- For smoke, auto-save extracted skills immediately and show a confirmation toast.

## Test Plan
1. Upload a `.txt` file with known skills; assert the canonical skills are returned and persisted.
2. Upload a `.pdf` with embedded text; assert extraction and skill matching work.
3. Upload an unsupported type; assert `400`.
4. Upload an oversized file; assert `400`.
5. Upload a corrupted PDF; assert graceful `422` with user-friendly message.
