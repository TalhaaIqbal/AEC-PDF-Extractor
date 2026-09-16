You are consolidating AEC information extracted from multiple pages
of the SAME architectural/engineering/construction document.

Rules:
- Keep only meaningful AEC information.
- Remove duplicates; merge repeated rooms/walls/doors/windows/levels
  /grids/dimensions/annotations/references when they clearly refer
  to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- Skip pages with "detection_status": "no_elements_detected" -
  they contributed nothing.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{final_schema}

PAGE RESULTS:

{page_results}