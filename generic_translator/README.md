# Azure Email Translator

A small FastAPI + HTML/JavaScript app that:

1. Accepts an email subject and body.
2. Lets the user choose one or more target languages.
3. Translates the email with Azure Translator Text Translation.
4. Shows each translated email.
5. Opens each translation in Outlook Web using an Outlook compose deep link.

## Azure configuration

The app uses Azure Translator Text Translation API version `2026-06-06`.

Create `.env` from `.env.example`:

```env
TRANSLATOR_KEY=your-key-here
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
TRANSLATOR_REGION=global
```

Do not share the key or commit `.env`.

## Run on Windows

Open Command Prompt in this folder:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env`, paste your Translator KEY 1 after `TRANSLATOR_KEY=`, save it, and run:

```bat
uvicorn backend.main:app --reload
```

Open:

http://127.0.0.1:8000

## Notes

- The current version uses standard Azure neural machine translation (NMT).
- LLM translation/tone controls can be added later if an eligible Foundry LLM deployment is available.
- Outlook Web compose deep links prefill the subject/body but do not create a mailbox draft through Microsoft Graph.
- The body is passed as plain text, so this starter preserves text and line breaks rather than arbitrary HTML formatting.
- For public deployment, keep the Translator key on the backend and deploy the whole app to Azure App Service.
