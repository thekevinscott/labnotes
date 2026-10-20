## Summary

`POST /experiments/{name}/notes` answers with the new note rendered as HTML, so the page can open it in place without a reload.

## Required changes

| Before | After |
| --- | --- |
| 201 with JSON `{"url": "/experiments/<name>?tab=notebooks&note=<file>#edit"}` | 201 with an HTML `<article class="note" data-note="<file>" ...>` fragment |

## Deprecations removed

None.

## Behavior changes without code changes

`PUT /experiments/{name}/notes/{note}` and `POST .../conflict` find the file by its path under the `files` pattern rather than through the index, so they work for a note created a moment ago. Reads still go through the index.

## Verification

`curl -si -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/experiments/<name>/notes` prints `201` and an `<article class="note"` element.
