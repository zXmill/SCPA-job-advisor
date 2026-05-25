# Certificate OCR Design

## Objective
Allow users to upload certificate images or PDFs so the system can extract the certificate name, issuer, and mapped skills, then enrich the user profile.

## In-Scope (Smoke)
- Authenticated `POST /api/profile/certificates` endpoint in the gateway.
- Accept PDF, PNG, JPG, JPEG files.
- Extract text from PDF using PyPDF2 (already available from P4-ADV-001).
- For images: attempt OCR with `pytesseract` if installed; otherwise gracefully fall back and store the file for later processing.
- Parse extracted text for certificate name and issuer using lightweight regex heuristics.
- Look up `certification_skills` table for known certificate-to-skill mappings.
- Insert a `user_certifications` record with extracted metadata and mapped skills.
- Optionally upsert mapped skills into `user_skills`.
- Return extracted metadata to the caller.

## Out-of-Scope (Future)
- Full image OCR requiring external Tesseract binary in environments where it is not pre-installed.
- LLM-based certificate parsing.
- Certificate verification against external issuers.
- PDFs with complex layouts or scanned image pages inside PDF.
- Front-end upload UI (smoke is backend-only; frontend wiring is a follow-up task).

## Architecture

```
Frontend profile page (future)
        |
        v
POST /api/profile/certificates  (multipart/form-data)
        |
        v
Gateway (FastAPI)
  - Validate auth
  - Validate file type (pdf, png, jpg, jpeg)
  - Validate file size (<= 5 MB)
  - Save file to disk
  - Extract text (PDF -> PyPDF2; image -> pytesseract if available)
  - Parse cert_name and issuer from text
  - Lookup certification_skills for mapped skills
  - Insert user_certifications record
  - Optionally upsert user_skills
  - Return JSON
```

## Database Schema
Already created by migration `008_feature_extension_foundation.py`:

- `user_certifications`
  - `id` BigInteger PK
  - `user_id` UUID FK -> users.id
  - `file_path` String(1000)
  - `cert_name` String(255)
  - `issuer` String(255)
  - `ocr_confidence` String(20) default 'medium'
  - `mapped_skills` ARRAY(Text) default '{}'
  - `status` String(32) default 'confirmed'
  - `created_at` DateTime default NOW()

- `certification_skills`
  - `id` BigInteger PK
  - `cert_name_regex` String(255)
  - `issuer` String(255)
  - `mapped_skills` ARRAY(Text)
  - `created_at` DateTime default NOW()

## Dependencies
Add to `services/gateway/requirements.txt`:
- `Pillow>=10.0` (already present via transitive deps; add explicitly for image handling)
- `pytesseract>=0.3.13` (optional; gate usage at runtime)

No new frontend dependencies needed.

## API Contract

### Request
`POST /api/profile/certificates`
- Header: `Authorization: Bearer <token>`
- Body: `multipart/form-data`
  - `file`: The certificate file (`.pdf`, `.png`, `.jpg`, `.jpeg`)

### Response (success)
```json
{
  "status": "ok",
  "cert_id": 42,
  "cert_name": "AWS Certified Solutions Architect",
  "issuer": "Amazon Web Services",
  "mapped_skills": ["Cloud Computing", "AWS", "Architecture"],
  "skills_added": 2,
  "ocr_confidence": "medium",
  "filename": "aws_cert.pdf",
  "ocr_available": true
}
```

### Response (image uploaded, OCR not available)
```json
{
  "status": "pending",
  "cert_id": 43,
  "cert_name": null,
  "issuer": null,
  "mapped_skills": [],
  "skills_added": 0,
  "ocr_confidence": "low",
  "filename": "cert.png",
  "ocr_available": false,
  "message": "Image stored but OCR requires tesseract. Install pytesseract and the Tesseract binary to enable image text extraction."
}
```

### Errors
- `400` — Unsupported file type, empty file, file too large.
- `401` — Missing or invalid token.
- `422` — Text extraction failed (corrupted PDF, etc.).

## Certificate Parsing Strategy
1. Extract all text from the uploaded file.
2. Heuristic cert name extraction: look for lines containing keywords like `certificate`, `certification`, `sertifikat`, `diploma`, `badge`, ` Credential`, then pick the longest/most capitalized candidate.
3. Heuristic issuer extraction: look for known issuer patterns near the top or bottom of the document, or URLs like `aws.amazon.com`, `google.com`, etc.
4. Match `cert_name` against `certification_skills.cert_name_regex` using substring/regex search.
5. If a match is found, use the corresponding `mapped_skills`.
6. Insert `user_certifications` record.
7. Optionally upsert mapped skills into `user_skills` (same logic as CV upload).

## Seed Data (Smoke)
Insert a few `certification_skills` rows so the lookup table is not empty:
- `AWS Certified` -> `["Cloud Computing", "AWS"]`
- `Google Cloud` -> `["Cloud Computing", "Google Cloud Platform"]`
- `Microsoft Azure` -> `["Cloud Computing", "Azure"]`
- `Python` -> `["Python"]`
- `SQL` -> `["SQL"]`

## Security Considerations
- Same as CV upload: file extension whitelist, MIME validation, 5 MB cap, UUID-based filenames, storage outside web root.
- Do not execute or render uploaded files.

## Test Plan
1. Upload a PDF certificate with known cert name; assert record created with correct mapped skills.
2. Upload an image when pytesseract is unavailable; assert `pending` status and file stored.
3. Upload an unsupported type; assert `400`.
4. Upload without auth; assert `401`.
