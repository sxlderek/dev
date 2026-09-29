# Batch Processing Reference

## Workflow Pattern

When the user requests batch processing of documents in a directory:

1. **Create output directories**
   ```bash
   mkdir -p /path/to/source/sorted /path/to/source/failed
   ```

2. **Process each document**
   - Extract metadata (date, company, doc number, type)
   - Generate new filename using docren format
   - Move to `sorted/` on success, `failed/` on error

3. **Report summary**
   - List each file with its outcome
   - Show new filename for successful renames
   - Indicate reason for failures

## Extraction Strategy for Batch Mode

Prefer lightweight extraction methods:

1. **Filename-based extraction first** — many documents encode metadata in their original filenames
2. **Text extraction** — for text-based PDFs, use pymupdf
3. **OCR page 1 only** — for scanned documents, minimize OCR overhead
4. **Model inference** — only when extraction is ambiguous

## Example Session

```
User: run docren skill on all documents in aihome/docren. move renamed document to docren/sorted, move failed documents to docren/failed.

Agent:
1. Creates sorted/ and failed/ subdirectories
2. Processes each file:
   - DRAY0804a - price2008.XLS → 20040801 draytek 0804 price-list.xls
   - DRAYTEK(23.5).pdf → 20080101 draytek 23.5 price-list.pdf
   - ECS0804C - price2008.XLS → 20040801 ecs 0804 price-list.xls
   - EDGE-CORE(10.5).pdf → 20080101 edge-core 10.5 price-list.pdf
3. Reports: "All 4 documents successfully processed and moved to sorted/"
```

## Group Ownership Note

In NAS environments, ensure output directories inherit the correct group ownership (typically gid 100). Use `mkdir -p` which respects parent directory permissions, or explicitly set group with `chgrp` if needed.
