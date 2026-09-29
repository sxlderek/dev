# Auto-Description Extraction for ID OCR

## What This Is

When users send ID document images through API-based chat clients (Open WebUI, Cherry Studio, etc.), the Hermes system may auto-describe those images in the user message before the agent sees them. When those descriptions are detailed enough, you can extract structured OCR fields directly from the description text — skipping the SiliconFlow API call entirely.

## When It Worked (This Session)

On [DOB]1, two Chinese ID card images were uploaded. The system provided full-text descriptions including:

- Card type (Chinese Resident Identity Card)
- Name ([Name])
- DOB (1998 年 5 月 13 日)
- ID number (622722199805134626)
- Issuing authority (泾州县公安局)
- Validity period (2023.03.16-2033.03.16)
- Gender, ethnicity, address

All fields were extracted directly from the descriptions in ~1 second with no API cost.

## The Signal to Watch For

The user message contains a block like:

```
[The user attached an image. Here's what it contains:
<detailed description of the image contents>]
```

If that description includes text values for the required OCR fields, proceed with direct extraction.

## Decision Tree

```
User sends ID image
  ├─ System provides auto-description?
  │    ├─ Yes → Description has all required fields?
  │    │    ├─ Yes → Extract directly from description [FAST]
  │    │    └─ No  → Fall back to SiliconFlow API
  │    └─ No  → Use SiliconFlow API (standard path)
  └─ Image is blurry? → Always use SiliconFlow
```

## Risks

- Auto-descriptions can hallucinate details
- They may miss fields (e.g. description might say "an ID card" without reading the number)
- Description quality varies by image quality, document type, and system load
- This is a Hermes platform feature — may not exist in all environments

## Recommended Approach

Always check the auto-description first. If it has all fields, extract directly. If anything is missing or uncertain, immediately fall through to the standard SiliconFlow pipeline. This hybrid approach minimizes latency while maintaining accuracy.
